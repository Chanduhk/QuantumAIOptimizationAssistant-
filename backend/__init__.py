"""Backend package initialization.

This package provides the Quantum Life AI backend services including:
- AI orchestration and brain
- Behavior analysis and learning
- Knowledge graph and memory management
- Task scheduling and optimization
- FastAPI REST API layer

For import guidelines and architecture documentation, see ARCHITECTURE.md

**IMPORTANT:** Do NOT import application modules here. This prevents:
- Unnecessary dependencies when importing the backend package
- Test isolation problems
- Circular import issues at startup
- Heavy startup cost for simple utilities

Users should import directly from subpackages:
    from backend.app.cognitive import CognitiveEngine
    from backend.app.memory import MemoryManager
    from backend.app.orchestrator import AIOrchestrator
"""

__version__ = "1.0.0"
__author__ = "Quantum Life AI Team"

__all__ = [
    "__version__",
    "__author__",
]
