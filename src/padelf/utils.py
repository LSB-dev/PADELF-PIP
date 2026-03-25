"""Utility functions for unit conversion, interpolation, and resampling."""

from __future__ import annotations

import pandas as pd
from pandas.tseries.frequencies import to_offset


def _infer_freq_delta(index: pd.DatetimeIndex) -> pd.Timedelta:
    """Infer a DateTimeIndex frequency as a Timedelta."""
    freq = pd.infer_freq(index)
    if freq:
        return pd.Timedelta(to_offset(freq).nanos, unit="ns")

    diffs = index.to_series().diff().dropna()
    if diffs.empty:
        raise ValueError("Cannot infer frequency from index with fewer than 2 timestamps.")
    return pd.Timedelta(diffs.mode().iloc[0])


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
    if from_unit == to_unit:
        return series

    time_hours = resolution_minutes / 60
    conversions = {
        ("MW", "kW"): lambda s: s * 1000,
        ("kW", "MW"): lambda s: s / 1000,
        ("kWh", "kW"): lambda s: s / time_hours,
        ("MWh", "kW"): lambda s: (s * 1000) / time_hours,
        ("MWh", "MW"): lambda s: s / time_hours,
        ("kW", "kWh"): lambda s: s * time_hours,
    }

    try:
        return conversions[(from_unit, to_unit)](series)
    except KeyError as exc:
        raise ValueError(f"Unsupported conversion: {from_unit} -> {to_unit}") from exc


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
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a pandas DateTimeIndex.")

    limit_timedelta = pd.Timedelta(limit)
    freq_timedelta = _infer_freq_delta(df.index)
    max_gap_periods = limit_timedelta / freq_timedelta
    return df.interpolate(
        method="linear",
        limit=int(max_gap_periods),
        limit_area="inside",
    )


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
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a pandas DateTimeIndex.")

    current_delta = _infer_freq_delta(df.index)
    target_delta = pd.Timedelta(target_resolution)

    if target_delta >= current_delta:
        return df.resample(target_resolution).mean()
    return df.resample(target_resolution).interpolate()
