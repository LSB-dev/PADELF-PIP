![A simle logo](images/logo_padelf_pip.png)

# padelf


**Easy Pandas DataFrame-Access to publicly available electric load forecasting datasets**

[![PyPI version](https://img.shields.io/pypi/v/padelf)](https://pypi.org/project/padelf/)
[![Python](https://img.shields.io/pypi/pyversions/padelf)](https://pypi.org/project/padelf/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`padelf` provides a minimal Python API to download, cache, and standardize
electric load forecasting datasets for research. Every dataset is returned as a
pandas DataFrame with a UTC DateTimeIndex and a standardized `consumption_kW`
column.

## Installation

```bash
pip install padelf
```

## Quick Start

```python
import padelf

# See what's available
padelf.list_datasets()
# ['AEMO', 'ENTSO-E', 'GEFCOM12', 'IHPC', 'ISO-NE', 'NYISO', 'OPSD', 'Pecan-Street', 'RTE-France']

# Load a dataset — one line, sensible defaults
df = padelf.get_dataset("OPSD")
print(df.head())
```

**Output:**

```
                                                     consumption_kW  DE_solar_generation_actual  DE_wind_onshore_generation_actual
datetime
2015-01-01 00:00:00+00:00       41209.0                        NaN                            7568.0
2015-01-01 01:00:00+00:00       40029.0                        NaN                            7666.0
2015-01-01 02:00:00+00:00       38891.0                        NaN                            7637.0
```

## What You Get

Every call to `get_dataset()` returns a DataFrame with:

- **DateTimeIndex** — UTC timezone, equidistant at the dataset's native resolution
- **`consumption_kW`** — Load/consumption column, unit-converted to kilowatts
- **Additional columns** — As available in the original dataset (e.g., temperature, solar generation)

## Optional Parameters

```python
df = padelf.get_dataset(
        "OPSD",
        resolution="15min",       # Resample to 15-minute intervals
        consumption_unit="MW",    # Keep original MW units
        interpolate_limit="4h",   # Fill gaps up to 4 hours
        cache_dir="/tmp/padelf",  # Custom cache location
)
```

## Available Datasets

| Dataset                                | Abbreviation | Resolution | Region    | Status  |
| -------------------------------------- | ------------ | ---------- | --------- | ------- |
| Open Power System Data                 | OPSD         | 60 min     | Europe    | Ready   |
| Individual Household Power Consumption | IHPC         | 1 min      | France    | Ready   |
| GEFCom 2012                            | GEFCOM12     | 60 min     | US        | Ready*  |
| ENTSO-E Transparency                   | ENTSO-E      | 60 min     | Europe    | Planned |
| ISO New England                        | ISO-NE       | 60 min     | US        | Planned |
| NYISO                                  | NYISO        | 5 min      | US        | Planned |
| AEMO                                   | AEMO         | 60 min     | Australia | Planned |
| RTE France                             | RTE-France   | 30 min     | France    | Planned |
| Pecan Street                           | Pecan Street | 15 min     | US        | Planned |

*\* GEFCOM12: Dropbox source may be intermittently unavailable.*



![a logo banner](images/logo_footer_pip.PNG)

## Documentation

Full documentation: [https://lsb-dev.github.io/padelf-pip/](https://lsb-dev.github.io/padelf-pip/)

## Original Catalog

![A simle logo](images/logo_padelf_repo.png)

To explore more datasets, check out the original [PADELF Repository](https://github.com/LSB-dev/Publicly-Available-Datasets-For-Electric-Load-Forecasting/).

## Citation

If you use `padelf` in your research, please cite the underlying dataset catalog:

```bibtex
@inproceedings{baur2024datasets,
    title     = {Publicly Available Datasets For Electric Load Forecasting -- An Overview},
    author    = {Baur, Lukas and Chandramouli, Vignesh and Sauer, Alexander},
    booktitle = {6th Conference on Production Systems and Logistics (CPSL 2024)},
    year      = {2024},
    doi       = {10.15488/17659}
}
```

## License

MIT
