"""Smoke tests to verify package structure and imports."""

import padelf


def test_version_exists():
    assert hasattr(padelf, "__version__")
    assert isinstance(padelf.__version__, str)


def test_list_datasets_returns_list():
    result = padelf.list_datasets()
    assert isinstance(result, list)


def test_get_dataset_is_callable():
    assert callable(padelf.get_dataset)
