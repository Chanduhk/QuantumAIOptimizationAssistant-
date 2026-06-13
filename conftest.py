"""Pytest configuration for entire workspace.

This module ensures that:
1. Project root is on sys.path for all tests
2. Backend package is importable as 'backend.app.X'
3. Both absolute and relative imports work consistently
4. Tests can be run from any directory
"""
import sys
from pathlib import Path

# Add project root to path so 'backend' package is discoverable
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    """Pytest hook: configure before test collection."""
    # Verify that backend package can be imported
    try:
        import backend  # noqa: F401
    except ImportError as e:
        raise ImportError(
            f"Cannot import 'backend' package. "
            f"Project root: {PROJECT_ROOT}\n"
            f"sys.path: {sys.path}"
        ) from e


def pytest_collection_modifyitems(config, items):
    """Pytest hook: add markers based on test location."""
    for item in items:
        # Add 'unit' marker to tests in tests/ directory
        if "tests/" in str(item.fspath):
            item.add_marker("unit")
        # Add 'integration' marker to backend test modules
        if "backend/tests" in str(item.fspath):
            item.add_marker("integration")
