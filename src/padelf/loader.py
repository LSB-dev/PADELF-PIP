"""Core dataset loading logic for the padelf package.

This module implements the full pipeline from dataset config to standardized
pandas DataFrame:

    Config YAML  -->  Download & Cache  -->  Parse (generic or custom)  -->  Standardize  -->  Output

Architecture
------------
Each dataset is defined by a YAML config file in ``src/padelf/configs/``.
The loader reads the config, downloads the raw data file (with local caching),
parses it into a DataFrame, and applies standardization (UTC index, unit
conversion, gap interpolation, optional resampling).

Parsing paths
~~~~~~~~~~~~~
There are two parsing paths:

1. **Generic path** (default): reads a CSV file using parameters from the config
   (separator, decimal, datetime column, load column). Handles single-column
   loads and ``__aggregate_all__`` multi-column aggregation.

2. **Custom parser path**: for datasets with non-standard formats (wide tables,
   special column layouts). Activated by setting ``custom_parser: "<name>"``
   in the dataset config. Custom parsers are registered in ``_CUSTOM_PARSERS``.

Currently registered custom parsers:

- ``gefcom12``: Parses GEFCOM12 wide hourly format (year/month/day + h1..h24
  columns + optional zone columns). Melts to long format and groups by datetime.
- ``eld``: Parses ELD (ElectricityLoadDiagrams20112014) semicolon-delimited CSV
  with European decimal format. 370 client columns, Portuguese local time.
- ``vea``: Parses VEA wide format (5359 rows x 35136 time columns). Transposes
  to long format, builds DateTimeIndex from known start time, converts
  Europe/Berlin to UTC.

Aggregation
~~~~~~~~~~~
Datasets with many individual load columns (ELD: 370 clients, VEA: 5359 sites)
use ``load_column: "__aggregate_all__"`` in their config. By default, all
numeric columns are summed into a single ``consumption_kW`` column. Pass
``aggregate=False`` to ``get_dataset()`` to retain individual columns.

Adding a new dataset
~~~~~~~~~~~~~~~~~~~~
1. Create a YAML config in ``src/padelf/configs/`` (copy ``_template.yaml``).
2. If the file format is a standard CSV: fill in config fields, no code needed.
3. If the format is non-standard: write a custom parser function with signature
   ``(file_path: Path, config: dict, aggregate: bool) -> pd.DataFrame``,
   then register it in ``_CUSTOM_PARSERS``.
4. Add a smoke test in ``tests/test_smoke.py``.

See Also
--------
padelf.utils : Unit conversion, gap interpolation, resampling utilities.
"""

from __future__ import annotations

import re
import warnings
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
    """Load a dataset configuration YAML by case-insensitive name.

    Scans ``src/padelf/configs/`` for YAML files (excluding those starting
    with ``_``). Matches the given name case-insensitively against filenames.

    Args:
        name: Dataset identifier (e.g. ``"OPSD"``).

    Returns:
        Parsed YAML config as a dictionary.

    Raises:
        ValueError: If no config matches the given name.
    """
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
    """Download a file to the local cache directory.

    If the file already exists in cache, the download is skipped.
    Uses streaming to handle large files.

    Args:
        url: Direct download URL.
        cache_dir: Local directory for cached files.
        filename: Target filename in cache.

    Returns:
        Path to the cached file.

    Raises:
        requests.HTTPError: If the download fails.
    """
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
    """Extract a single member from a ZIP archive.

    Args:
        zip_path: Path to the ZIP file.
        inner_path: Path of the target file inside the archive.
        cache_dir: Directory to extract into.

    Returns:
        Path to the extracted file.

    Raises:
        ValueError: If ``inner_path`` is not found in the archive.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        if inner_path not in zf.namelist():
            raise ValueError(f"'{inner_path}' not found in archive '{zip_path.name}'.")
        extracted = zf.extract(inner_path, path=cache_dir)
    return Path(extracted)


def _infer_resolution_minutes(index: pd.DatetimeIndex, fallback: Optional[int]) -> int:
    """Infer temporal resolution in minutes from a DateTimeIndex.

    Uses ``pd.infer_freq`` first, then falls back to the mode of consecutive
    differences. If ``fallback`` is provided, it is returned directly.

    Args:
        index: DateTimeIndex to analyze.
        fallback: If not None, returned without inference.

    Returns:
        Resolution in minutes.

    Raises:
        ValueError: If the index has fewer than 2 rows and no fallback.
    """
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


def _parse_gefcom12(
    file_path: Path,
    config: dict,
    aggregate: bool = True,
) -> pd.DataFrame:
    """Parse GEFCOM12 wide hourly format into a long-format DataFrame.

    The GEFCOM12 CSV has columns: year, month, day, h1..h24, and optionally
    zone1..zone20. This parser melts the hourly columns into rows, constructs
    datetime values, and optionally sums zone columns into a ``zone21``
    aggregate.

    Args:
        file_path: Path to the CSV file.
        config: Dataset config (used for separator, encoding, skip_rows).
        aggregate: Unused for GEFCOM12 (kept for interface consistency).

    Returns:
        DataFrame with ``datetime`` column and zone/load value columns.
        Not yet indexed -- ``_build_dataframe`` handles indexing.
    """
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


def _parse_eld(file_path: Path, config: dict, aggregate: bool = True) -> pd.DataFrame:
    """Parse ELD (ElectricityLoadDiagrams20112014) into a numeric DataFrame.

    The ELD file is semicolon-delimited with European decimal format (commas).
    The first column is a datetime index in Portuguese local time. The
    remaining 370 columns represent individual client load profiles in kW.

    This parser reads and coerces all columns to numeric. Timezone conversion
    and aggregation are handled downstream by ``_build_dataframe``.

    Args:
        file_path: Path to the extracted ``LD2011_2014.txt`` file.
        config: Dataset config (used for separator, decimal, encoding).
        aggregate: Unused here (aggregation handled by ``_build_dataframe``
            via ``__aggregate_all__``).

    Returns:
        DataFrame with DateTimeIndex (Portuguese local time) and 370 numeric
        columns. Not yet UTC-converted -- ``_build_dataframe`` handles this.
    """
    df = pd.read_csv(
        file_path,
        sep=config.get("separator", config.get("csv_separator", ";")),
        decimal=config.get("decimal", config.get("csv_decimal", ",")),
        index_col=0,
        parse_dates=True,
        encoding=config.get("encoding", "utf-8"),
        skiprows=config.get("skip_rows", 0),
        na_values=config.get("na_values", []),
    )
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df.apply(pd.to_numeric, errors="coerce")
    return df


def _parse_vea(file_path: Path, config: dict, aggregate: bool = True) -> pd.DataFrame:
    """Parse VEA wide-format industrial load profiles.

    The VEA file has one row per industrial site (5359 total) and one column
    per 15-minute timestep (``time0`` through ``time35135``), covering the
    full year 2016 (leap year). Values are in kW.

    Unlike other custom parsers, this one fully handles output construction:
    it builds the UTC DateTimeIndex from the known start time and returns
    a ready-to-use DataFrame. The ``_build_dataframe`` function skips its
    normal datetime/aggregation logic for this parser.

    Args:
        file_path: Path to ``load_profiles_tabsep.csv``.
        config: Dataset config (used for start_datetime, source_timezone).
        aggregate: If True (default), returns a single ``consumption_kW``
            column summed across all 5359 sites. If False, returns all
            individual site columns plus ``consumption_kW`` (warning: ~188M
            cells, high memory usage).

    Returns:
        DataFrame with UTC DateTimeIndex and ``consumption_kW`` column.
        If ``aggregate=False``, also includes ``site_<id>`` columns.
    """
    raw = pd.read_csv(
        file_path,
        sep="\t",
        decimal=".",
        encoding=config.get("encoding", "utf-8"),
        skiprows=config.get("skip_rows", 0),
        na_values=config.get("na_values", []),
    )

    time_cols = [col for col in raw.columns if str(col).startswith("time")]
    if not time_cols:
        raise ValueError("VEA parser could not find time0..timeN columns.")

    start_datetime = config.get("start_datetime", "2016-01-01 00:00:00")
    source_tz = config.get("timezone", config.get("source_timezone", "Europe/Berlin"))
    index = pd.date_range(
        start=start_datetime,
        periods=len(time_cols),
        freq="15min",
        tz=source_tz,
    ).tz_convert("UTC")

    if aggregate:
        aggregated = raw[time_cols].sum(axis=0)
        out = pd.DataFrame({"consumption_kW": aggregated.to_numpy()}, index=index)
        out.index.name = "datetime"
        return out

    warnings.warn(
        "VEA aggregate=False returns all site profiles and can require substantial memory.",
        RuntimeWarning,
        stacklevel=2,
    )
    site_profiles = raw[time_cols].transpose().copy()
    if "id" in raw.columns:
        site_profiles.columns = [f"site_{site_id}" for site_id in raw["id"].tolist()]
    site_profiles.index = index
    site_profiles.index.name = "datetime"
    site_profiles["consumption_kW"] = site_profiles.sum(axis=1)
    return site_profiles


# ---------------------------------------------------------------------------
# Custom parser registry
#
# To add a new custom parser:
# 1. Write a function with signature:
#        def _parse_<name>(file_path: Path, config: dict, aggregate: bool = True) -> pd.DataFrame
# 2. Register it here: _CUSTOM_PARSERS["<name>"] = _parse_<name>
# 3. Set custom_parser: "<name>" in the dataset's YAML config.
#
# If the parser fully handles datetime indexing and aggregation (like VEA),
# add its name to the parser_handles_output check in _build_dataframe.
# ---------------------------------------------------------------------------
_CUSTOM_PARSERS = {
    "gefcom12": _parse_gefcom12,
    "eld": _parse_eld,
    "vea": _parse_vea,
}


def _build_dataframe(file_path: Path, config: dict, aggregate: bool = True) -> pd.DataFrame:
    """Read a raw data file and transform it into a standardized DataFrame.

    This is the central parsing dispatcher. It either delegates to a custom
    parser (if ``custom_parser`` is set in the config) or uses the generic
    CSV reading path.

    After parsing, it:
    1. Builds or extracts a datetime column and converts to UTC.
    2. Selects or aggregates load columns into ``consumption_kW``.
    3. Removes NaT indices, sorts, deduplicates.
    4. Reindexes to an equidistant DateTimeIndex.

    Custom parsers that fully handle their own output (e.g. ``vea``) are
    listed in the ``parser_handles_output`` check. For these, steps 1-2
    are skipped since the parser already returns a UTC-indexed DataFrame
    with ``consumption_kW``.

    Args:
        file_path: Path to the extracted/downloaded data file.
        config: Parsed YAML config dictionary.
        aggregate: If True, multi-column datasets return only ``consumption_kW``.
            If False, individual columns are preserved.

    Returns:
        DataFrame with UTC DateTimeIndex and ``consumption_kW`` column.
    """
    custom_parser = config.get("custom_parser")
    parser_handles_output = False
    if custom_parser:
        parser = _CUSTOM_PARSERS.get(custom_parser)
        if parser is None:
            available = ", ".join(sorted(_CUSTOM_PARSERS))
            raise ValueError(
                f"Unknown custom parser '{custom_parser}'. Available parsers: {available}"
            )
        df = parser(file_path, config, aggregate=aggregate)
        parser_handles_output = custom_parser in {"vea"}
    else:
        file_format = config["file_format"]
        separator = config.get("separator", config.get("csv_separator", ","))
        if file_format not in {"csv", "zip"}:
            raise ValueError(f"Unsupported file format '{file_format}'.")
        df = pd.read_csv(
            file_path,
            sep=separator,
            decimal=config.get("decimal", config.get("csv_decimal", ".")),
            encoding=config.get("encoding", "utf-8"),
            skiprows=config.get("skip_rows", 0),
            na_values=config.get("na_values", []),
        )

    datetime_column = config.get("datetime_column")
    datetime_format = config.get("datetime_format", "iso")
    if isinstance(df.index, pd.DatetimeIndex):
        datetimes = pd.Series(df.index, index=df.index)
    else:
        if datetime_column is None:
            raise ValueError("Missing 'datetime_column' in dataset config.")
        if isinstance(datetime_column, list):
            dt_raw = df[datetime_column].astype(str).agg(" ".join, axis=1)
        else:
            dt_raw = df[datetime_column]
        parse_format = None if datetime_format == "iso" else datetime_format
        datetimes = pd.to_datetime(dt_raw, format=parse_format, errors="coerce")

    source_tz = config.get("timezone", config.get("source_timezone", "UTC"))
    if datetimes.dt.tz is None:
        datetimes = datetimes.dt.tz_localize(
            source_tz,
            ambiguous="NaT",
            nonexistent="NaT",
        )
    else:
        datetimes = datetimes.dt.tz_convert(source_tz)
    datetimes = datetimes.dt.tz_convert("UTC")

    if parser_handles_output:
        out = df.copy()
    else:
        load_column = config.get("load_column", config.get("consumption_column"))
        if load_column == "__aggregate_all__":
            numeric_cols = list(df.select_dtypes(include="number").columns)
            out = df[numeric_cols].copy()
            out["consumption_kW"] = out[numeric_cols].sum(axis=1)
            if aggregate:
                out = out[["consumption_kW"]]
        else:
            if load_column is None:
                raise ValueError("Missing 'consumption_column' or 'load_column' in dataset config.")
            keep_columns = [load_column]
            additional_columns = config.get("additional_columns", [])
            keep_columns.extend(additional_columns)
            keep_columns = [col for col in keep_columns if col in df.columns]

            out = df[keep_columns].copy()
            out = out.rename(columns={load_column: "consumption_kW"})
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
    resolution: str | None = None,
    consumption_unit: str = "kW",
    interpolate_limit: str = "2h",
    cache_dir: str | None = None,
    aggregate: bool = True,
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
        aggregate: If ``True`` (default), datasets using
            ``load_column: "__aggregate_all__"`` return only ``consumption_kW``.
            If ``False``, original numeric columns are kept alongside
            ``consumption_kW``.

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
    cache = cache / name
    cache.mkdir(parents=True, exist_ok=True)

    url = config.get("download_url", config.get("url"))
    if not url:
        raise ValueError(f"Dataset '{name}' has no download URL configured.")
    filename = config.get("download_filename", url.split("/")[-1])
    raw_path = _download_file(url, cache, filename)

    if config["file_format"] == "zip" or raw_path.suffix == ".zip":
        inner = config.get("zip_inner_path", config.get("inner_file", ""))
        data_path = _extract_zip(raw_path, inner, cache)
    else:
        data_path = raw_path

    df = _build_dataframe(data_path, config, aggregate=aggregate)

    from_unit = config.get("consumption_unit", config.get("unit", "kW"))
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
