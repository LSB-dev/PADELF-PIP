# Extending padelf: Loader Developer Guide

This document explains how the padelf loader pipeline works and how to add new datasets. It is intended for developers who want to contribute new loaders or modify existing ones.

## Loader Pipeline Overview

Every call to `padelf.get_dataset("XYZ")` follows the same pipeline:

```
1. Config Lookup       YAML file in src/padelf/configs/XYZ.yaml
        │
        ▼
2. Download & Cache    Raw file downloaded to ~/.cache/padelf/ (skipped if cached)
        │
        ▼
3. Extract             If ZIP: extract inner_file from archive
        │
        ▼
4. Parse               Generic CSV path  OR  custom parser
        │
        ▼
5. Standardize         UTC DateTimeIndex, consumption_kW column, dedup, equidistant reindex
        │
        ▼
6. Post-process        Unit conversion, gap interpolation (default ≤2h), optional resampling
        │
        ▼
7. Return              pandas DataFrame
```

## Parsing Paths

The parser in `loader.py` has two paths. Which one is used depends on whether the dataset config contains a `custom_parser` field.

### Generic Path

Used when no `custom_parser` is set. Reads a CSV file using config parameters:

- `csv_separator` (or `separator`): column delimiter
- `csv_decimal` (or `decimal`): decimal character
- `datetime_column`: name or index of the datetime column
- `datetime_format`: strftime format string, or `"iso"` for automatic parsing
- `source_timezone`: timezone of the raw timestamps (converted to UTC)
- `load_column` (or `consumption_column`): name of the consumption column, renamed to `consumption_kW`
- `additional_columns`: list of extra columns to keep in the output

If `load_column` is set to `"__aggregate_all__"`, all numeric columns are summed into `consumption_kW`. When the user passes `aggregate=False`, individual columns are preserved alongside the sum.

### Custom Parser Path

Used when the config contains `custom_parser: "<name>"`. The parser function is looked up in the `_CUSTOM_PARSERS` registry in `loader.py`.

Every custom parser has the same signature:

```python
def _parse_<name>(file_path: Path, config: dict, aggregate: bool = True) -> pd.DataFrame:
```

There are two levels of custom parsers:

**Partial parsers** (e.g. `gefcom12`, `eld`): return a DataFrame that still needs datetime indexing and column selection by `_build_dataframe`. The parser handles only the non-standard CSV reading.

**Full parsers** (e.g. `vea`): return a complete DataFrame with UTC DateTimeIndex and `consumption_kW` already set. These are listed in the `parser_handles_output` check in `_build_dataframe`, which skips its normal datetime/aggregation logic.

### Currently Registered Parsers

| Name | Dataset | Type | What it does |
|---|---|---|---|
| `gefcom12` | GEFCom 2012 | Partial | Melts wide hourly format (year/month/day + h1..h24) to long format |
| `eld` | ElectricityLoadDiagrams20112014 | Partial | Reads semicolon CSV with European decimal commas, 370 client columns |
| `vea` | 5359 VEA Industrial Profiles | Full | Transposes wide format (5359 rows x 35136 time columns), builds DateTimeIndex from known start time |

## How to Add a New Dataset

### Step 1: Create the Config

Copy `src/padelf/configs/_template.yaml` to `src/padelf/configs/MyDataset.yaml`. Fill in the fields. At minimum you need:

```yaml
name: "My Dataset"
abbreviation: "MyDataset"
url: "https://example.com/data.csv"
file_format: "csv"           # or "zip"

datetime_column: "timestamp"
datetime_format: "%Y-%m-%d %H:%M:%S"
source_timezone: "UTC"

load_column: "power_kw"
unit: "kW"

resolution_minutes: 60
requires_api: false
```

If the file is a ZIP, also set:

```yaml
file_format: "zip"
inner_file: "data.csv"       # filename inside the archive
```

### Step 2: Decide if You Need a Custom Parser

You do NOT need a custom parser if:
- The file is a standard CSV with a datetime column and a load column
- The generic `pd.read_csv` with separator/decimal/encoding config is sufficient

You DO need a custom parser if:
- The file uses wide format (e.g. one column per hour, or one column per timestep)
- Datetime is split across multiple columns (e.g. year + month + day + hour)
- The file requires transposing, melting, or other structural transformation

### Step 3: Write a Custom Parser (if needed)

Add a function in `loader.py` following this pattern:

```python
def _parse_mydataset(file_path: Path, config: dict, aggregate: bool = True) -> pd.DataFrame:
    """Parse MyDataset format into a DataFrame."""
    # Read the raw file
    raw = pd.read_csv(file_path, ...)
    
    # Transform into standard long format
    # ...
    
    return df
```

Then register it:

```python
_CUSTOM_PARSERS = {
    "gefcom12": _parse_gefcom12,
    "eld": _parse_eld,
    "vea": _parse_vea,
    "mydataset": _parse_mydataset,   # <-- add here
}
```

And set it in the config:

```yaml
custom_parser: "mydataset"
```

#### Partial vs. Full Parser

If your parser returns a DataFrame that still needs datetime indexing and column selection, it is a **partial parser**. No further changes needed -- `_build_dataframe` handles the rest using `datetime_column`, `source_timezone`, and `load_column` from the config.

If your parser returns a complete DataFrame with a UTC DateTimeIndex and `consumption_kW` already set, it is a **full parser**. Add its name to the `parser_handles_output` check in `_build_dataframe`:

```python
parser_handles_output = custom_parser in {"vea", "mydataset"}
```

This tells `_build_dataframe` to skip datetime conversion and column selection.

### Step 4: Add a Smoke Test

In `tests/test_smoke.py`:

```python
@pytest.mark.slow
def test_mydataset_loads():
    df = padelf.get_dataset("MyDataset")
    assert "consumption_kW" in df.columns
    assert df.index.tz is not None
    assert len(df) > 0
```

### Step 5: Update the README

Add a row to the "Available Datasets" table in `README.md`.

### Step 6: Run Tests

```bash
pytest tests/ -v
pytest tests/ -v -m slow    # includes download tests
```

## Config Reference

Full list of supported config fields:

| Field | Required | Description |
|---|---|---|
| `name` | yes | Human-readable dataset name |
| `abbreviation` | yes | Short identifier (used as config filename) |
| `url` | yes | Direct download URL |
| `file_format` | yes | `"csv"` or `"zip"` |
| `inner_file` | if zip | Filename inside ZIP archive |
| `csv_separator` | no | Column delimiter (default: `","`) |
| `csv_decimal` | no | Decimal character (default: `"."`) |
| `encoding` | no | File encoding (default: `"utf-8"`) |
| `skip_rows` | no | Number of header rows to skip (default: `0`) |
| `na_values` | no | List of strings to treat as NaN |
| `datetime_column` | generic path | Column name or index for datetime |
| `datetime_format` | no | strftime format or `"iso"` (default: `"iso"`) |
| `source_timezone` | no | Timezone of raw timestamps (default: `"UTC"`) |
| `load_column` | generic path | Consumption column name, or `"__aggregate_all__"` |
| `additional_columns` | no | List of extra columns to keep |
| `unit` | no | Unit of raw values: `"kW"`, `"MW"`, `"kWh"`, `"MWh"` (default: `"kW"`) |
| `resolution_minutes` | no | Temporal resolution in minutes (auto-inferred if omitted) |
| `custom_parser` | no | Name of registered custom parser |
| `requires_api` | no | If `true`, `get_dataset()` raises `NotImplementedError` |
| `domain` | no | `"S"` (system), `"R"` (residential), `"I"` (industrial) |
| `region` | no | Geographic region |
| `spanned_years` | no | Year range (e.g. `"2011-2014"`) |
| `duration_months` | no | Duration in months |
| `start_datetime` | full parsers | Start time for generated DateTimeIndex |
| `num_timesteps` | full parsers | Number of timesteps for generated DateTimeIndex |

## Standardized Output Contract

Every call to `get_dataset()` returns a DataFrame that satisfies:

1. **Index**: `pd.DatetimeIndex` with `tz=UTC`, equidistant at the dataset's native resolution (or resampled if `resolution` is specified).
2. **`consumption_kW` column**: float values in kilowatts (or the unit specified by `consumption_unit`).
3. **No duplicate timestamps**: enforced by `_build_dataframe`.
4. **Gaps interpolated**: up to 2 hours by default (configurable via `interpolate_limit`).