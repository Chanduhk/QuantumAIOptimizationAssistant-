from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.app.memory.vector_memory import VectorMemorySystem


class ContextEngine:
    """Assemble decision-ready AI context from behavior, memory, and live task input."""

    def __init__(self, memory_system: VectorMemorySystem) -> None:
        self.memory_system = memory_system

    def build_context(
        self,
        user_id: int,
        behavior_patterns: Dict[str, Any],
        current_tasks: List[Dict[str, Any]],
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        current_hour = datetime.now().hour
        memory_context = self.memory_system.retrieve_context(user_id=user_id)
        semantic_matches = (
            self.memory_system.search_similar_tasks(query, limit=5, user_id=user_id)
            if query else []
        )

        return {
            "user_id": user_id,
            "current_hour": current_hour,
            "time_of_day_segment": self._time_segment(current_hour),
            "behavior_patterns": behavior_patterns,
            "current_tasks": current_tasks,
            "memory_context": memory_context,
            "semantic_matches": semantic_matches,
        }

    def _time_segment(self, hour: int) -> str:
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 22:
            return "evening"
        return "night"
