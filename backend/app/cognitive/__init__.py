"""Cognitive package - goal parsing and task decomposition.

Import directly from submodules:
    from backend.app.cognitive.behavior_analyzer import BehaviorAnalyzer
    from backend.app.cognitive.cognitive_engine import CognitiveEngine

Or use convenience imports:
    from backend.app.cognitive import CognitiveEngine
"""

from backend.app.cognitive.cognitive_engine import CognitiveEngine  # noqa: F401

__all__ = ["CognitiveEngine"]
