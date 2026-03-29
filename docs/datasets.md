# Available Datasets

## Direct Download (ready to use)

| Dataset | Abbreviation | Domain | Resolution | Region |
|---------|-------------|--------|------------|--------|
| Open Power System Data | OPSD | System | 60 min | Europe (32 countries) |
| Individual Household Power Consumption | IHPC | Household | 1 min | France |
| Global Energy Forecasting Competition 2012 | GEFCOM12 | System | 60 min | US |

## API Access Required (coming soon)

These datasets require registration or API keys. Configs are included
with instructions, but `get_dataset()` will raise `NotImplementedError`.

| Dataset | Abbreviation | Domain | Resolution | Region |
|---------|-------------|--------|------------|--------|
| ENTSO-E Transparency Platform | ENTSO-E | System | 60 min | Europe |
| ISO New England | ISO-NE | System | 60 min | US (New England) |
| New York ISO | NYISO | System | 5 min | US (New York) |
| Australian Energy Market Operator | AEMO | System | 60 min | Australia |
| RTE France | RTE-France | System | 30 min | France |
| Pecan Street Dataport | Pecan Street | Household | 15 min | US (Texas) |

## Adding a New Dataset

1. Copy `src/padelf/configs/_template.yaml` to `src/padelf/configs/YOUR_DATASET.yaml`
2. Fill in the required fields (download URL, column mappings, units)
3. Test with `padelf.get_dataset("YOUR_DATASET")`
4. Submit a pull request
