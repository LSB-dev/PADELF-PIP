# padelf

**Load publicly available electric load forecasting datasets as pandas DataFrames.**

`padelf` provides a simple Python API to download, cache, and standardize
electric load forecasting datasets for research. Every dataset is returned
as a pandas DataFrame with a UTC DateTimeIndex and a standardized
`consumption_kW` column.

## Features

- One-line dataset loading: `padelf.get_dataset("OPSD")`
- Automatic unit conversion (MW, kWh, MWh → kW)
- Gap interpolation for small missing periods
- Optional resampling to any temporal resolution
- Local file caching (no repeated downloads)

## Quick Example

```python
import padelf

# List available datasets
padelf.list_datasets()
# ['AEMO', 'ENTSO-E', 'GEFCOM12', 'IHPC', 'ISO-NE', 'NYISO', 'OPSD', 'Pecan-Street', 'RTE-France']

# Load a dataset
df = padelf.get_dataset("OPSD")
print(df.head())
```

## Citation

If you use `padelf` in your research, please cite the underlying dataset catalog:

> Baur, L., Chandramouli, V., & Sauer, A. (2024). Publicly Available Datasets
> For Electric Load Forecasting -- An Overview. *6th Conference on Production
> Systems and Logistics (CPSL 2024)*.
> [DOI: 10.15488/17659](https://doi.org/10.15488/17659)
