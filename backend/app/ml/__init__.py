"""ML package - machine learning models and feature engineering.

Import directly from submodules:
    from backend.app.ml.feature_store import FeatureStore
    from backend.app.ml.model_registry import ModelRegistry

Or use convenience imports:
    from backend.app.ml import FeatureStore
"""

from backend.app.ml.feature_store import FeatureStore  # noqa: F401

__all__ = ["FeatureStore"]
