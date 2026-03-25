"""Core dataset loading logic."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

CONFIGS_DIR = Path(__file__).parent / "configs"


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
    raise NotImplementedError(
        f"Loader for '{name}' is not yet implemented. Coming in Day 2."
    )
