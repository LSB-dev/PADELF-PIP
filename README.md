# padelf

Load publicly available electric load forecasting datasets as pandas DataFrames.

## Installation

```bash
pip install padelf
```

For local development:

```bash
pip install -e ".[dev,docs]"
```

## Quick Start

```python
import padelf

# List available dataset identifiers
print(padelf.list_datasets())

# Load a dataset into a pandas DataFrame
df = padelf.get_dataset("ENTSO-E")
print(df.head())
```

## Documentation

Project documentation is generated with MkDocs and mkdocstrings:

- https://github.com/LSB-dev/padelf-pip/tree/main/docs

## Reference

PADELF paper (Baur et al., CPSL 2024):

- https://doi.org/10.15488/17659

## Status

This package is currently in alpha. APIs and dataset coverage may evolve.