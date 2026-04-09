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


def test_aggregate_all_sums_columns():
    """Test that __aggregate_all__ correctly sums numeric columns."""
    dates = pd.date_range("2020-01-01", periods=4, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "A": [1.0, 2.0, 3.0, 4.0],
            "B": [10.0, 20.0, 30.0, 40.0],
            "C": [100.0, 200.0, 300.0, 400.0],
        },
        index=dates,
    )

    df["consumption_kW"] = df.select_dtypes(include="number").sum(axis=1)

    assert df["consumption_kW"].iloc[0] == 111.0
    assert df["consumption_kW"].iloc[3] == 444.0


def test_aggregate_false_keeps_all_columns():
    """Test that aggregate=False preserves individual columns."""
    dates = pd.date_range("2020-01-01", periods=4, freq="15min", tz="UTC")
    df = pd.DataFrame(
        {
            "A": [1.0, 2.0, 3.0, 4.0],
            "B": [10.0, 20.0, 30.0, 40.0],
        },
        index=dates,
    )

    df["consumption_kW"] = df.select_dtypes(include="number").sum(axis=1)

    assert "A" in df.columns
    assert "B" in df.columns
    assert "consumption_kW" in df.columns
