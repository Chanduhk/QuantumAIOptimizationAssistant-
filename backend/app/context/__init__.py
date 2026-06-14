"""Context package - unified system state management.

Import directly from submodules:
    from backend.app.context.context_builder import ContextBuilder, ContextState
    from backend.app.context.context_engine import ContextEngine

Or use convenience imports:
    from backend.app.context import ContextEngine
"""

from backend.app.context.context_engine import ContextEngine  # noqa: F401

__all__ = ["ContextEngine"]
