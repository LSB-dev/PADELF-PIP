# padelf

Load publicly available electric load forecasting datasets as pandas DataFrames.

## Quick Start

```python
import padelf

# See available datasets
padelf.list_datasets()

# Load a dataset
df = padelf.get_dataset("ENTSO-E")
print(df.head())
```

## Installation

```bash
pip install padelf
```
