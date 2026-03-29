# Getting Started

## Installation

```bash
pip install padelf
```

For development:

```bash
pip install padelf[dev,docs]
```

## Basic Usage

### List Available Datasets

```python
import padelf

datasets = padelf.list_datasets()
print(datasets)
```

### Load a Dataset

```python
df = padelf.get_dataset("OPSD")
```

This returns a `pandas.DataFrame` with:

- A **DateTimeIndex** in UTC
- An equidistant time series at the dataset's native resolution
- A **`consumption_kW`** column with standardized units
- Additional columns as available in the original data

### Optional Parameters

```python
df = padelf.get_dataset(
    "OPSD",
    resolution="15min",       # Resample to 15-minute intervals
    consumption_unit="MW",    # Keep original MW instead of converting to kW
    interpolate_limit="4h",   # Interpolate gaps up to 4 hours
    cache_dir="/tmp/padelf",  # Custom cache directory
)
```

### Caching

Downloaded files are cached locally in `~/.cache/padelf/` by default.
Subsequent calls to `get_dataset()` use the cached files.
To force a re-download, delete the cache directory.
