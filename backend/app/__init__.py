"""SIH 2026 PS 26071 - Backend Application Package."""

import os
# Ensure OpenMP runtime duplicate error is suppressed on macOS when both Torch and XGBoost link OpenMP
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Pre-import xgboost so its OpenMP runtime initializes first cleanly on macOS
try:
    import xgboost  # noqa: F401
except ImportError:
    pass

__version__ = "0.1.0"
