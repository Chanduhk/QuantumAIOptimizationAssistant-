"""Orchestrator package - central request-driven AI coordination.

Import directly from submodules:
    from backend.app.orchestrator.ai_orchestrator import AIOrchestrator
    from backend.app.orchestrator.ai_brain import AIBrain
    from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain

Or use lazy convenience imports:
    from backend.app.orchestrator import AIOrchestrator, AIBrain, ExecutiveCognitiveBrain
"""

__all__ = ["AIOrchestrator", "AIBrain", "ExecutiveCognitiveBrain"]


def __getattr__(name: str):
    if name == "AIOrchestrator":
        from backend.app.orchestrator.ai_orchestrator import AIOrchestrator

        return AIOrchestrator
    if name == "AIBrain":
        from backend.app.orchestrator.ai_brain import AIBrain

        return AIBrain
    if name == "ExecutiveCognitiveBrain":
        from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain

        return ExecutiveCognitiveBrain
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
