from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.app.knowledge.knowledge_graph import AIKnowledgeGraph
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine


class CognitiveEngine:
    """Translate user goals into structured task plans.

    The cognitive layer uses light heuristics today and can later be replaced
    with an LLM-based planner. It also consults behavior patterns and the
    knowledge graph for better task shaping.
    """

    def __init__(
        self,
        behavior_engine: BehaviorIntelligenceEngine,
        knowledge_graph: AIKnowledgeGraph,
    ) -> None:
        self.behavior_engine = behavior_engine
        self.knowledge_graph = knowledge_graph

    def parse_goal(self, goal_text: str) -> Dict[str, Any]:
        """Extract high-level intent hints from the goal text."""
        normalized_goal = goal_text.strip().lower()
        keywords = normalized_goal.replace(",", " ").split()
        goal_type = self._infer_goal_type(normalized_goal)

        return {
            "goal": goal_text.strip(),
            "goal_type": goal_type,
            "keywords": keywords,
            "time_horizon": "weekly" if "week" in keywords else "general",
        }

    def decompose_goal(self, goal_text: str) -> Dict[str, Any]:
        """Break a high-level goal into structured tasks."""
        goal_metadata = self.parse_goal(goal_text)
        base_tasks = self._generate_goal_tasks(goal_metadata)

        # Use knowledge graph context when related tasks already exist for this goal area.
        related_tasks = []
        for keyword in goal_metadata["keywords"][:3]:
            related_tasks.extend(self.knowledge_graph.get_related_tasks(keyword))

        deduplicated_tasks = self._merge_related_task_hints(base_tasks, related_tasks)
        prioritized_tasks = self.prioritize_goal_tasks(deduplicated_tasks)

        return {
            "goal": goal_text.strip(),
            "goal_type": goal_metadata["goal_type"],
            "tasks": prioritized_tasks,
        }

    def prioritize_goal_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prioritize goal-derived tasks using behavior preferences when available."""
        preferred_task_types = {
            str(task_type).lower()
            for task_type in getattr(self.behavior_engine, "user_patterns", {}).get(
                "preferred_task_types",
                [],
            )
        }

        prioritized: List[Dict[str, Any]] = []
        for task in tasks:
            task_copy = dict(task)
            boost = 1 if str(task_copy.get("type", "")).lower() in preferred_task_types else 0
            task_copy["priority"] = min(10, int(task_copy.get("priority", 5)) + boost)
            prioritized.append(task_copy)

        return sorted(prioritized, key=lambda item: int(item["priority"]), reverse=True)

    def track_goal_progress(self, goal_id: str) -> Dict[str, Any]:
        """Return a lightweight progress snapshot for a goal in the knowledge graph."""
        goal_node = self.knowledge_graph.graph.nodes.get(goal_id, {})
        related_tasks = self.knowledge_graph.get_related_tasks(goal_id)
        completed_tasks = [task for task in related_tasks if task.get("completed")]
        total_tasks = len(related_tasks)

        return {
            "goal_id": goal_id,
            "goal": goal_node.get("label"),
            "total_tasks": total_tasks,
            "completed_tasks": len(completed_tasks),
            "progress": round((len(completed_tasks) / total_tasks) * 100, 2) if total_tasks else 0.0,
        }

    def _infer_goal_type(self, normalized_goal: str) -> str:
        if "paper" in normalized_goal or "write" in normalized_goal:
            return "writing"
        if "research" in normalized_goal:
            return "research"
        if "study" in normalized_goal or "learn" in normalized_goal:
            return "learning"
        return "general"

    def _generate_goal_tasks(self, goal_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        goal_text = str(goal_metadata["goal"]).lower()

        if "paper" in goal_text:
            return [
                {"title": "Literature review", "type": "research", "priority": 8},
                {"title": "Write introduction", "type": "writing", "priority": 9},
                {"title": "Draft methodology", "type": "writing", "priority": 8},
            ]
        if "research" in goal_text:
            return [
                {"title": "Collect source materials", "type": "research", "priority": 8},
                {"title": "Summarize findings", "type": "analysis", "priority": 7},
                {"title": "Draft conclusions", "type": "writing", "priority": 7},
            ]

        return [
            {"title": "Define sub-goals", "type": "planning", "priority": 7},
            {"title": "Execute main work block", "type": goal_metadata["goal_type"], "priority": 8},
            {"title": "Review completion criteria", "type": "review", "priority": 6},
        ]

    def _merge_related_task_hints(
        self,
        base_tasks: List[Dict[str, Any]],
        related_tasks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        known_titles = {task["title"].lower() for task in base_tasks}
        merged_tasks = list(base_tasks)

        for task in related_tasks:
            title = str(task.get("label") or task.get("title") or "").strip()
            if title and title.lower() not in known_titles:
                merged_tasks.append(
                    {
                        "title": title,
                        "type": str(task.get("task_type") or "general"),
                        "priority": int(task.get("priority") or 5),
                    }
                )
                known_titles.add(title.lower())

        return merged_tasks
