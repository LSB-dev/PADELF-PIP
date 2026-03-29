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


class TestApiDatasets:
    """Test that API-requiring datasets raise NotImplementedError."""

    @pytest.mark.parametrize("name", [
        "ENTSO-E", "ISO-NE", "NYISO", "AEMO", "RTE-France", "Pecan-Street"
    ])
    def test_api_dataset_raises(self, name):
        with pytest.raises(NotImplementedError, match="requires API access"):
            padelf.get_dataset(name)


class TestListAllDatasets:
    def test_lists_all_nine_datasets(self):
        datasets = padelf.list_datasets()
        assert len(datasets) == 9
        # Direct download datasets
        assert "OPSD" in datasets
        assert "IHPC" in datasets
        assert "GEFCOM12" in datasets
        # API datasets
        assert "ENTSO-E" in datasets
        assert "ISO-NE" in datasets


class TestGetDatasetErrors:
    def test_unknown_dataset_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unknown dataset"):
            padelf.get_dataset("NONEXISTENT")

    def test_case_insensitive_lookup(self):
        """Verify that dataset names are case-insensitive."""
        datasets = padelf.list_datasets()
        if "OPSD" in datasets:
            # This should not raise ValueError (may raise other errors in non-network env)
            try:
                padelf.get_dataset("opsd")
            except (ConnectionError, OSError):
                pass  # Network issues OK, but no ValueError means lookup worked


@pytest.mark.slow
class TestResampling:
    def test_opsd_resample_to_daily(self):
        df = padelf.get_dataset("OPSD", resolution="D")
        diffs = df.index.to_series().diff().dropna()
        assert diffs.iloc[0] == pd.Timedelta("1D")

    def test_opsd_custom_unit(self):
        df = padelf.get_dataset("OPSD", consumption_unit="MW")
        # OPSD original is MW, so requesting MW should give original values
        assert df["consumption_kW"].median() < 100_000  # MW range, not kW
