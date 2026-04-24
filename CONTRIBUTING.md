# ✍ Contributing to padelf

## Getting Started

Thank you for contributing to padelf. See README.md for a project overview.

## Development Setup

1. Clone the repo.
2. Create a virtual environment: `python -m venv .venv && source .venv/bin/activate`
3. Install in editable mode with dev dependencies: `pip install -e ".[dev]"`
4. Run tests: `pytest tests/`
5. Build locally: `python -m build && twine check dist/*`

## How to Contribute

### Adding a New Dataset Loader

See the Adding a New Loader section in README.md for step-by-step instructions.

### Implementing an API Placeholder

See the API Placeholder Pattern section in README.md for details on converting placeholders to working loaders.

### Bug Reports

Use GitHub Issues. Include: dataset abbreviation, full error traceback, Python version, and `padelf` version (`padelf.__version__`).

### Feature Requests

Use GitHub Issues with the label "enhancement". Describe the use case.

## Code Guidelines

**Python style**: Follow PEP 8. Use type hints. Use Google-style docstrings (these are auto-rendered by mkdocstrings in the documentation site).

**Standardized output contract**: Every loader must return a pandas DataFrame with a `consumption_kW` column (float, in kilowatts) and an equidistant UTC DateTimeIndex. Do not deviate from this contract -- downstream users depend on it.

**Config files**: Loader configs in `src/padelf/configs/` are YAML files. Use `_template.yaml` as the starting point. Keep configs declarative -- complex logic belongs in `loader.py`, not in YAML.

**Tests**: Add a smoke test for every new loader. Test files live in `tests/`. Run the full suite with `pytest tests/` before opening a PR.

**Documentation**: Docstrings are auto-rendered via mkdocstrings. If you add a new public function or class, ensure it has a Google-style docstring. Update `mkdocs.yml` if adding new documentation pages.

## Pull Request Guidelines

Keep PRs focused on a single change. Tests must pass. Reference the related GitHub Issue if applicable.


# 📬 Backlog
Here, the upcoming tasks are kept as an overview:

### [PRIO 1]
- Datasets: add missing datasets

### [PRIO 2]
- Improve Cache: instead of using the original dataset format, always store the pandas df as pickle-file. This way, loading the dataset each time is much faster, instead of parsing csv file. 
- Improve Cache: When downloading the file, make sure to not mix up files in one folder. Currently, the .cache folder stores all files. Instead, use subfolder .cache/<dadasetname> for each dataset individually
- add native language support, as suggested in [this paper](https://doi.org/10.1016/j.jss.2011.11.010) (H4)

