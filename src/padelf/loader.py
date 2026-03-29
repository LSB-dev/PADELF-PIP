"""Core dataset loading logic."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import yaml
from pandas.tseries.frequencies import to_offset

from padelf.utils import convert_unit, interpolate_gaps, resample_data

CONFIGS_DIR = Path(__file__).parent / "configs"


def _load_config(name: str) -> dict:
    """Load dataset configuration YAML by case-insensitive name."""
    configs = {
        p.stem.lower(): p
        for p in CONFIGS_DIR.glob("*.yaml")
        if not p.stem.startswith("_")
    }
    selected = configs.get(name.lower())
    if selected is None:
        available = ", ".join(sorted(p.stem for p in configs.values()))
        raise ValueError(f"Unknown dataset '{name}'. Available datasets: {available}")

    with selected.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _download_file(url: str, cache_dir: Path, filename: str) -> Path:
    """Download a file into cache and return local path."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    target_path = cache_dir / filename
    if target_path.exists():
        return target_path

    print(f"Downloading {filename}...")
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with target_path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)

    print(f"Cached at {target_path}")
    return target_path


def _extract_zip(zip_path: Path, inner_path: str, cache_dir: Path) -> Path:
    """Extract a single member from a zip archive into cache directory."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        if inner_path not in zf.namelist():
            raise ValueError(f"'{inner_path}' not found in archive '{zip_path.name}'.")
        extracted = zf.extract(inner_path, path=cache_dir)
    return Path(extracted)


def _infer_resolution_minutes(index: pd.DatetimeIndex, fallback: Optional[int]) -> int:
    """Infer dataset resolution in minutes from DateTimeIndex."""
    if fallback is not None:
        return int(fallback)
    freq = pd.infer_freq(index)
    if freq:
        freq_delta = pd.Timedelta(to_offset(freq).nanos, unit="ns")
        return int(freq_delta.total_seconds() // 60)

    diffs = index.to_series().diff().dropna()
    if diffs.empty:
        raise ValueError("Unable to infer resolution from index with fewer than 2 rows.")
    return int(diffs.mode().iloc[0].total_seconds() // 60)


def _parse_gefcom12(file_path: Path, config: dict) -> pd.DataFrame:
    """Parse GEFCOM12 wide hourly format into a long timestamped DataFrame."""
    df = pd.read_csv(
        file_path,
        sep=config.get("separator", ","),
        encoding=config.get("encoding", "utf-8"),
        skiprows=config.get("skip_rows", 0),
        na_values=config.get("na_values", []),
    )

    col_map = {str(col).strip().lower(): col for col in df.columns}
    year_col = col_map.get("year")
    month_col = col_map.get("month")
    day_col = col_map.get("day")
    if year_col is None or month_col is None or day_col is None:
        raise ValueError("GEFCOM12 parser requires year/month/day columns.")

    hour_cols: list[str] = []
    hour_lookup: dict[str, int] = {}
    for col in df.columns:
        match = re.fullmatch(r"h\s*([1-9]|1\d|2[0-4])", str(col).strip().lower())
        if match:
            hour_cols.append(col)
            hour_lookup[col] = int(match.group(1)) - 1
    if not hour_cols:
        raise ValueError("GEFCOM12 parser could not find h1..h24 columns.")

    zone_cols = []
    zone_pattern = re.compile(r"zone[_\s-]?(\d+)$", re.IGNORECASE)
    for col in df.columns:
        zmatch = zone_pattern.fullmatch(str(col).strip())
        if zmatch:
            zone_cols.append((int(zmatch.group(1)), col))

    long_df = df.melt(
        id_vars=[year_col, month_col, day_col] + [c for _, c in zone_cols],
        value_vars=hour_cols,
        var_name="_hour_col",
        value_name="_hourly_value",
    )
    long_df["_hour"] = long_df["_hour_col"].map(hour_lookup)
    long_df["datetime"] = pd.to_datetime(
        {
            "year": long_df[year_col],
            "month": long_df[month_col],
            "day": long_df[day_col],
        },
        errors="coerce",
    ) + pd.to_timedelta(long_df["_hour"], unit="h")

    for _, zone_col in zone_cols:
        long_df[zone_col] = pd.to_numeric(long_df[zone_col], errors="coerce")

    result_cols = ["datetime"]
    if zone_cols:
        ordered_zone_cols = [c for _, c in sorted(zone_cols, key=lambda item: item[0])]
        long_df["zone21"] = long_df[[c for n, c in zone_cols if 1 <= n <= 20]].sum(axis=1)
        result_cols.extend(ordered_zone_cols)
        result_cols.append("zone21")
    else:
        # Fallback for unexpected file variants: keep hourly value as aggregate load.
        long_df["zone21"] = pd.to_numeric(long_df["_hourly_value"], errors="coerce")
        result_cols.append("zone21")

    result = long_df[result_cols]
    numeric_cols = [c for c in result.columns if c != "datetime"]
    result = result.groupby("datetime", as_index=False)[numeric_cols].mean()
    return result


def _build_dataframe(file_path: Path, config: dict) -> pd.DataFrame:
    """Read raw file and transform it into a normalized DataFrame."""
    custom_parser = config.get("custom_parser")
    if custom_parser == "gefcom12":
        df = _parse_gefcom12(file_path, config)
    else:
        file_format = config["file_format"]
        separator = config.get("separator", ",")
        if file_format not in {"csv", "zip"}:
            raise ValueError(f"Unsupported file format '{file_format}'.")
        df = pd.read_csv(
            file_path,
            sep=separator,
            encoding=config.get("encoding", "utf-8"),
            skiprows=config.get("skip_rows", 0),
            na_values=config.get("na_values", []),
        )

    datetime_column = config["datetime_column"]
    datetime_format = config["datetime_format"]
    if isinstance(datetime_column, list):
        dt_raw = df[datetime_column].astype(str).agg(" ".join, axis=1)
    else:
        dt_raw = df[datetime_column]

    parse_format = None if datetime_format == "iso" else datetime_format
    datetimes = pd.to_datetime(dt_raw, format=parse_format, errors="coerce")

    source_tz = config["timezone"]
    if getattr(datetimes.dt, "tz", None) is None:
        datetimes = datetimes.dt.tz_localize(
            source_tz,
            ambiguous="NaT",
            nonexistent="NaT",
        )
    else:
        datetimes = datetimes.dt.tz_convert(source_tz)
    datetimes = datetimes.dt.tz_convert("UTC")

    consumption_column = config["consumption_column"]
    keep_columns = [consumption_column]
    additional_columns = config.get("additional_columns", [])
    keep_columns.extend(additional_columns)
    keep_columns = [col for col in keep_columns if col in df.columns]

    out = df[keep_columns].copy()
    out = out.rename(columns={consumption_column: "consumption_kW"})
    out["consumption_kW"] = pd.to_numeric(out["consumption_kW"], errors="coerce")
    out.index = datetimes
    out.index.name = "datetime"

    out = out[out.index.notna()]
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="first")]

    if not isinstance(out.index, pd.DatetimeIndex):
        raise ValueError("Parsed index must be a pandas DateTimeIndex.")

    res_minutes = _infer_resolution_minutes(out.index, config.get("resolution_minutes"))
    regular_index = pd.date_range(
        start=out.index.min(),
        end=out.index.max(),
        freq=f"{res_minutes}min",
        tz="UTC",
    )
    out = out.reindex(regular_index)
    out.index.name = "datetime"
    return out


def list_datasets() -> list[str]:
    """List all available dataset identifiers.

    Returns:
        A list of dataset name strings that can be passed to ``get_dataset()``.

    Example:
        >>> import padelf
        >>> padelf.list_datasets()
        ['ENTSO-E', 'ISO-NE', ...]
    """
    configs = sorted(
        p.stem for p in CONFIGS_DIR.glob("*.yaml") if not p.stem.startswith("_")
    )
    return configs


def get_dataset(
    name: str,
    *,
    resolution: Optional[str] = None,
    consumption_unit: str = "kW",
    interpolate_limit: str = "2h",
    cache_dir: Optional[str] = None,
) -> pd.DataFrame:
    """Load a dataset and return it as a pandas DataFrame.

    Args:
        name: Dataset identifier (e.g. ``"ENTSO-E"``). Case-insensitive.
            Use ``list_datasets()`` to see available options.
        resolution: Target temporal resolution for resampling (e.g. ``"15min"``,
            ``"1h"``). If ``None`` (default), the original resolution is kept.
        consumption_unit: Target unit for the consumption column.
            Supported: ``"kW"``, ``"MW"``, ``"kWh"``. Default: ``"kW"``.
        interpolate_limit: Maximum gap size to interpolate. Gaps larger than
            this are left as NaN. Default: ``"2h"``.
        cache_dir: Directory for caching downloaded files. If ``None``,
            defaults to ``~/.cache/padelf/``.

    Returns:
        A DataFrame with:
        - **DateTimeIndex** in UTC, equidistant at the dataset's native resolution
          (or ``resolution`` if specified).
        - **consumption_kW** column (or equivalent, unit-converted).
        - Additional columns as available in the original dataset.

    Raises:
        ValueError: If ``name`` does not match any known dataset.
        ConnectionError: If the dataset cannot be downloaded.

    Example:
        >>> import padelf
        >>> df = padelf.get_dataset("ENTSO-E")
        >>> df.index
        DatetimeIndex([...], dtype='datetime64[ns, UTC]', freq='h')
        >>> df.columns
        Index(['consumption_kW', ...])
    """
    config = _load_config(name)
    
    # Check if dataset requires API access
    if config.get("requires_api", False):
        config_path = CONFIGS_DIR / f"{name}.yaml"
        raise NotImplementedError(
            f"Dataset '{name}' requires API access or registration. "
            f"Direct download is not yet supported. "
            f"See the dataset config at {config_path} for access instructions."
        )
    
    cache = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "padelf"
    cache.mkdir(parents=True, exist_ok=True)

    url = config["download_url"]
    filename = config.get("download_filename", url.split("/")[-1])
    raw_path = _download_file(url, cache, filename)

    if config["file_format"] == "zip" or raw_path.suffix == ".zip":
        inner = config.get("zip_inner_path", "")
        data_path = _extract_zip(raw_path, inner, cache)
    else:
        data_path = raw_path

    df = _build_dataframe(data_path, config)

    from_unit = config.get("consumption_unit", "kW")
    res_minutes = config.get("resolution_minutes", 60)
    if from_unit != consumption_unit:
        df["consumption_kW"] = convert_unit(
            df["consumption_kW"],
            from_unit,
            consumption_unit,
            res_minutes,
        )

    df = interpolate_gaps(df, limit=interpolate_limit)

    if resolution is not None:
        df = resample_data(df, resolution)

    return df
