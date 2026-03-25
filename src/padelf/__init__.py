"""
padelf - Load publicly available electric load forecasting datasets as pandas DataFrames.
"""

from padelf.loader import get_dataset, list_datasets

__version__ = "0.1.0"
__all__ = ["get_dataset", "list_datasets", "__version__"]
