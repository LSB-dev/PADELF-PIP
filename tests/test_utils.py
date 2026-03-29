import numpy as np
import pandas as pd
import pytest

from padelf.utils import convert_unit, interpolate_gaps


class TestConvertUnit:
    def test_mw_to_kw(self):
        s = pd.Series([1.0, 2.0, 3.0])
        result = convert_unit(s, "MW", "kW", 60)
        assert result.tolist() == [1000.0, 2000.0, 3000.0]

    def test_kwh_to_kw(self):
        s = pd.Series([1.0])
        result = convert_unit(s, "kWh", "kW", 60)
        assert result.tolist() == [1.0]

    def test_kwh_to_kw_15min(self):
        s = pd.Series([1.0])
        result = convert_unit(s, "kWh", "kW", 15)
        assert result.tolist() == [4.0]

    def test_same_unit_noop(self):
        s = pd.Series([42.0])
        result = convert_unit(s, "kW", "kW", 60)
        assert result.tolist() == [42.0]

    def test_unsupported_raises(self):
        s = pd.Series([1.0])
        with pytest.raises(ValueError):
            convert_unit(s, "Wh", "kW", 60)


class TestInterpolateGaps:
    def test_small_gap_filled(self):
        idx = pd.date_range("2020-01-01", periods=5, freq="h", tz="UTC")
        df = pd.DataFrame({"val": [1.0, np.nan, 3.0, 4.0, 5.0]}, index=idx)
        result = interpolate_gaps(df, limit="2h")
        assert not result["val"].isna().any()

    def test_large_gap_stays_nan(self):
        idx = pd.date_range("2020-01-01", periods=10, freq="h", tz="UTC")
        values = [1.0] + [np.nan] * 8 + [10.0]
        df = pd.DataFrame({"val": values}, index=idx)
        result = interpolate_gaps(df, limit="2h")
        assert result["val"].isna().any()


class TestResampleData:
    def test_downsample_hourly_to_daily(self):
        from padelf.utils import resample_data
        idx = pd.date_range("2020-01-01", periods=48, freq="h", tz="UTC")
        df = pd.DataFrame({"val": range(48)}, index=idx)
        result = resample_data(df, "1D")
        assert len(result) == 2

    def test_upsample_hourly_to_30min(self):
        from padelf.utils import resample_data
        idx = pd.date_range("2020-01-01", periods=4, freq="h", tz="UTC")
        df = pd.DataFrame({"val": [10.0, 20.0, 30.0, 40.0]}, index=idx)
        result = resample_data(df, "30min")
        assert len(result) >= 7  # 4 hours = 7 or 8 half-hour periods


class TestConvertUnitEdgeCases:
    def test_mwh_to_kw(self):
        s = pd.Series([1.0])
        result = convert_unit(s, "MWh", "kW", 60)
        assert result.tolist() == [1000.0]  # 1 MWh/h = 1 MW = 1000 kW

    def test_kw_to_kwh(self):
        s = pd.Series([4.0])
        result = convert_unit(s, "kW", "kWh", 15)
        assert result.tolist() == [1.0]  # 4 kW * 0.25h = 1 kWh

    def test_empty_series(self):
        s = pd.Series([], dtype=float)
        result = convert_unit(s, "MW", "kW", 60)
        assert len(result) == 0
