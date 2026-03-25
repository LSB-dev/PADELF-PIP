"""Utility functions for unit conversion, interpolation, and resampling."""

from __future__ import annotations

import pandas as pd


def convert_unit(
    series: pd.Series,
    from_unit: str,
    to_unit: str,
    resolution_minutes: int,
) -> pd.Series:
    """Convert a consumption series between energy/power units.

    Handles conversions between kW, MW, kWh, MWh based on the
    temporal resolution of the data.

    Args:
        series: The consumption data to convert.
        from_unit: Source unit (e.g. ``"kWh"``, ``"MW"``).
        to_unit: Target unit (e.g. ``"kW"``).
        resolution_minutes: Time step in minutes (needed for energy <-> power).

    Returns:
        Converted series in the target unit.

    Raises:
        ValueError: If the conversion is not supported.
    """
    raise NotImplementedError


def interpolate_gaps(
    df: pd.DataFrame,
    limit: str = "2h",
) -> pd.DataFrame:
    """Interpolate small gaps in the DataFrame, leave large gaps as NaN.

    Args:
        df: DataFrame with DateTimeIndex.
        limit: Maximum gap duration to interpolate (e.g. ``"2h"``, ``"30min"``).

    Returns:
        DataFrame with small gaps filled via linear interpolation.
    """
    raise NotImplementedError


def resample_data(
    df: pd.DataFrame,
    target_resolution: str,
) -> pd.DataFrame:
    """Resample a DataFrame to a different temporal resolution.

    Args:
        df: DataFrame with equidistant DateTimeIndex.
        target_resolution: Target resolution string (e.g. ``"15min"``, ``"1h"``).

    Returns:
        Resampled DataFrame.
    """
    raise NotImplementedError
