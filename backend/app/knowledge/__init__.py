"""Knowledge graph package for task and goal relationships.

Import directly from submodules:
    from backend.app.knowledge.knowledge_graph import AIKnowledgeGraph

Or use convenience imports:
    from backend.app.knowledge import AIKnowledgeGraph, DependencyGraph, GoalGraph
"""

from backend.app.knowledge.dependency_graph import DependencyGraph  # noqa: F401
from backend.app.knowledge.goal_graph import GoalGraph  # noqa: F401
from backend.app.knowledge.knowledge_graph import AIKnowledgeGraph  # noqa: F401

__all__ = ["AIKnowledgeGraph", "DependencyGraph", "GoalGraph"]
