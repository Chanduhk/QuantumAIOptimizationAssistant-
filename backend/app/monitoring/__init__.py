"""Monitoring package - system health and performance monitoring.

Import directly from submodules:
    from backend.app.monitoring.ai_monitor import AIMonitor

Or use convenience imports:
    from backend.app.monitoring import AIMonitor
"""

from backend.app.monitoring.ai_monitor import AIMonitor  # noqa: F401

__all__ = ["AIMonitor"]
