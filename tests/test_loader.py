import pandas as pd
import pytest

import padelf


@pytest.mark.slow
class TestOPSD:
    def test_loads_dataframe(self):
        df = padelf.get_dataset("OPSD")
        assert isinstance(df, pd.DataFrame)

    def test_has_datetime_index(self):
        df = padelf.get_dataset("OPSD")
        assert isinstance(df.index, pd.DatetimeIndex)
        assert str(df.index.tz) == "UTC"

    def test_has_consumption_column(self):
        df = padelf.get_dataset("OPSD")
        assert "consumption_kW" in df.columns

    def test_consumption_unit_is_kw(self):
        df = padelf.get_dataset("OPSD")
        # OPSD original is MW, so kW values should be ~1000x larger
        assert df["consumption_kW"].median() > 1000

    def test_equidistant_index(self):
        df = padelf.get_dataset("OPSD")
        diffs = df.index.to_series().diff().dropna()
        assert diffs.nunique() == 1


@pytest.mark.slow
class TestIHPC:
    def test_loads_dataframe(self):
        df = padelf.get_dataset("IHPC")
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 2_000_000

    def test_has_datetime_index_utc(self):
        df = padelf.get_dataset("IHPC")
        assert isinstance(df.index, pd.DatetimeIndex)
        assert str(df.index.tz) == "UTC"

    def test_consumption_in_kw(self):
        df = padelf.get_dataset("IHPC")
        assert "consumption_kW" in df.columns
        # Household power: typically 0-10 kW
        assert df["consumption_kW"].median() < 10


@pytest.mark.slow
class TestListDatasets:
    def test_lists_configured_datasets(self):
        datasets = padelf.list_datasets()
        assert "OPSD" in datasets
        assert "IHPC" in datasets
