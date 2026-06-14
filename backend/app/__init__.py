"""Main application package.

Core application modules and their public APIs:

Cognitive Layer:
    from backend.app.cognitive import CognitiveEngine
    from backend.app.cognitive.behavior_analyzer import BehaviorAnalyzer

Knowledge & Memory:
    from backend.app.knowledge import AIKnowledgeGraph
    from backend.app.memory import VectorMemorySystem, MemoryManager

Engines & Orchestration:
    from backend.app.orchestrator import AIOrchestrator
    from backend.app.engines import DecisionEngine, PlanningEngine

Services:
    from backend.app.services import BehaviorIntelligenceEngine

Models & Data:
    from backend.app.models import Task, BehaviorData

**IMPORT GUIDELINES:**
- Do NOT import modules here (prevents cascading imports)
- Users should import directly from subpackages
- All imports must be fully-qualified: from backend.app.X import Y
- Never use relative imports across package boundaries

See ARCHITECTURE.md for complete guidelines.
"""

__all__ = []
