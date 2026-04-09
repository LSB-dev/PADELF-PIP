![A simple logo](images/logo_padelf_pip.png)

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
# ['AEMO', 'ELD', 'ENTSO-E', 'GEFCOM12', 'IHPC', 'ISO-NE', 'NYISO', 'OPSD', 'Pecan-Street', 'RTE-France', 'VEA']

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
| ElectricityLoadDiagrams20112014        | ELD          | 15 min     | Portugal  | Ready   |
| 5359 industrial VEA load profiles      | VEA          | 15 min     | Germany   | Ready   |
| GEFCom 2012                            | GEFCOM12     | 60 min     | US        | Planned |
| ENTSO-E Transparency                   | ENTSO-E      | 60 min     | Europe    | Planned |
| ISO New England                        | ISO-NE       | 60 min     | US        | Planned |
| NYISO                                  | NYISO        | 5 min      | US        | Planned |
| AEMO                                   | AEMO         | 60 min     | Australia | Planned |
| RTE France                             | RTE-France   | 30 min     | France    | Planned |
| Pecan Street                           | Pecan Street | 15 min     | US        | Planned |





![a logo banner](images/logo_footer_pip.PNG)

### Repository Structure

The project uses a src layout with per-dataset YAML configs:

```
.
├── README.md
├── pyproject.toml                # Build config (hatchling backend)
├── mkdocs.yml                    # Documentation site config
├── LICENSE
├── src/padelf/
│   ├── __init__.py               # Public API: list_datasets(), get_dataset()
│   ├── loader.py                 # Core loader logic: download, cache, parse, standardize
│   ├── utils.py                  # Unit conversion, gap interpolation, resampling
│   └── configs/
│       ├── _template.yaml        # Template for new loader configs
│       ├── OPSD.yaml             # Ready
│       ├── IHPC.yaml             # Ready
│       ├── ELD.yaml              # Ready
│       ├── VEA.yaml              # Ready
│       ├── GEFCOM12.yaml         # Ready (source URL intermittent)
│       ├── ENTSO-E.yaml          # API placeholder
│       ├── ISO-NE.yaml           # API placeholder
│       ├── NYISO.yaml            # API placeholder
│       ├── AEMO.yaml             # API placeholder
│       ├── RTE-France.yaml       # API placeholder
│       └── Pecan-Street.yaml     # API placeholder
├── docs/                         # mkdocs source files
│   ├── index.md
│   ├── getting-started.md
│   ├── api.md
│   └── datasets.md
└── tests/
    ├── test_loader.py
    ├── test_utils.py
    └── test_smoke.py
```

### How It Works

The loader architecture follows a per-dataset config pattern. Each YAML file in `src/padelf/configs/` defines a dataset's download URL, file format, column mappings, unit, and preprocessing parameters. When `get_dataset()` is called, `loader.py` reads the corresponding config, downloads the file (or uses a local cache), parses it, and applies standardization via `utils.py`: the load column is renamed to `consumption_kW` with automatic unit conversion (MW, kWh, MWh to kW), the index is converted to an equidistant UTC DateTimeIndex, gaps up to 2 hours are interpolated by default, and optional resampling is applied if requested. Datasets flagged with `requires_api: true` in their config raise `NotImplementedError` with a descriptive message -- these are placeholders for future implementation.

### Adding a New Loader

1. Copy `src/padelf/configs/_template.yaml` to a new file named after the dataset abbreviation (e.g., `MyDataset.yaml`).
2. Fill in the config fields: `url` (direct download link), `file_format` (csv, zip, xlsx), `load_column` (name of the consumption column in the raw data), `unit` (kW, MW, kWh, or MWh), `datetime_column`, `datetime_format`, and any other relevant parameters. See existing configs like `OPSD.yaml` for reference.
3. If the dataset requires custom parsing logic beyond what the generic loader handles, extend `loader.py` with a dataset-specific branch.
4. Add a smoke test in `tests/test_smoke.py` that calls `padelf.get_dataset("MyDataset")` and checks the output has a `consumption_kW` column and a UTC DateTimeIndex.
5. Update the "Available Datasets" table in this README.
6. Run all tests: `pytest tests/`
7. Open a pull request.

### API Placeholder Pattern

Six datasets (ENTSO-E, ISO-NE, NYISO, AEMO, RTE-France, Pecan-Street) are currently configured as API placeholders. Their YAML configs exist with `requires_api: true`, and calling `get_dataset()` on them raises `NotImplementedError`. To convert a placeholder into a working loader, remove the `requires_api` flag and either provide a direct download URL or implement API-specific download logic in `loader.py`. Note that ENTSO-E and ISO-NE have direct CSV downloads available and could be implemented as file-based loaders without API integration.

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
