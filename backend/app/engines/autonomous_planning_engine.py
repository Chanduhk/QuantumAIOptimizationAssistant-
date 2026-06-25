from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from backend.app.domain.autonomous_planning_model import (
    AutonomousPlan,
    ContingencyPlan,
    PlanMilestone,
    PlanObjective,
    PlanTask,
    RecoveryPlan,
)


class AutonomousPlanningEngine:
    """Deterministic recommendation-only planning agent."""

    def __init__(
        self,
        strategic_planning_engine: Any | None = None,
        goal_intelligence_engine: Any | None = None,
        dependency_intelligence_engine: Any | None = None,
        future_simulation_engine: Any | None = None,
        personal_knowledge_engine: Any | None = None,
    ) -> None:
        self.strategic_planning_engine = strategic_planning_engine
        self.goal_intelligence_engine = goal_intelligence_engine
        self.dependency_intelligence_engine = dependency_intelligence_engine
        self.future_simulation_engine = future_simulation_engine
        self.personal_knowledge_engine = personal_knowledge_engine
        self.latest_plan: AutonomousPlan | None = None
        self.latest_next_best_action: Dict[str, Any] | None = None
        self.latest_recovery_plan: RecoveryPlan | None = None
        self.latest_contingency_plans: List[ContingencyPlan] = []

    def decompose_goal(
        self,
        goal: Dict[str, Any],
        *,
        behavior_patterns: Dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> AutonomousPlan:
        """Convert a goal dictionary into objectives, milestones, and recommended tasks."""
        goal = self._dict(goal, "goal")
        if behavior_patterns is None:
            behavior_patterns = {}
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        created_at = created_at or datetime.utcnow()
        goal_id = self._text(goal.get("goal_id", goal.get("id", "goal")), "goal_id")
        title = self._text(goal.get("title", goal_id), "title")
        priority = self._positive_int(goal.get("priority", 1), "priority")
        objective = PlanObjective(
            objective_id=f"objective-{goal_id}",
            title=title,
            priority=priority,
            goal_id=goal_id,
            success_criteria=[
                f"Advance {title}",
                "Resolve blockers",
                "Create measurable progress",
            ],
            metadata=goal,
        )
        milestone_titles = self._milestone_titles(goal)
        milestones = [
            PlanMilestone(
                milestone_id=f"{objective.objective_id}-milestone-{index}",
                objective_id=objective.objective_id,
                title=milestone_title,
                sequence=index,
                progress=self._bounded(self._safe_float(goal.get("progress"), 0.0) if index == 1 else 0.0, 0.0, 100.0),
            )
            for index, milestone_title in enumerate(milestone_titles, start=1)
        ]
        tasks = self._tasks_from_milestones(milestones, priority)
        scores = self.score_plan(
            tasks=[asdict(task) for task in tasks],
            goal_health={"progress": goal.get("progress", 0.0), "risk_score": goal.get("risk_score", 0.0)},
            dependency_state={},
            simulation_results=[],
        )
        plan = AutonomousPlan(
            plan_id=f"autonomous-{goal_id}-{created_at.strftime('%Y%m%d')}",
            objective=objective,
            milestones=milestones,
            tasks=tasks,
            reasoning=f"{title} was decomposed into ordered milestones and executable recommended tasks.",
            created_at=created_at,
            **scores,
        )
        self.latest_plan = plan
        return plan

    def determine_next_best_action(
        self,
        *,
        goal_health: Dict[str, Any] | None = None,
        dependency_state: Dict[str, Any] | None = None,
        simulation_results: List[Dict[str, Any]] | None = None,
        optimization_results: Dict[str, Any] | None = None,
        knowledge_graph: Any | None = None,
    ) -> Dict[str, Any]:
        """Recommend the highest-value next action without executing it."""
        goal_health = self._dict({} if goal_health is None else goal_health, "goal_health")
        dependency_state = self._dict({} if dependency_state is None else dependency_state, "dependency_state")
        simulation_results = self._list([] if simulation_results is None else simulation_results, "simulation_results")
        optimization_results = self._dict({} if optimization_results is None else optimization_results, "optimization_results")
        blocked = self._blocked_count(dependency_state)
        risk_score = self._safe_float(goal_health.get("risk_score"), self._max_simulation_risk(simulation_results))
        progress = self._safe_float(goal_health.get("progress"), 0.0)
        selected_future = optimization_results.get("selected_future", {})
        action = "Advance the highest-alignment unblocked task"
        if blocked > 0:
            action = "Unblock the highest-impact dependency"
        elif risk_score >= 60.0:
            action = "Execute recovery action for the at-risk goal"
        elif progress < 25.0:
            action = "Create first measurable progress on the primary goal"
        elif isinstance(selected_future, dict) and selected_future.get("scenario_name"):
            action = f"Follow selected future: {selected_future['scenario_name']}"
        knowledge_bonus = 0.05 if self._knowledge_has_nodes(knowledge_graph) else 0.0
        confidence = self._bounded((0.62 + knowledge_bonus + max(0.0, 100.0 - risk_score) / 500.0), 0.0, 1.0)
        result = {
            "recommended_action": action,
            "confidence": round(confidence, 4),
            "reasoning": self._next_action_reason(blocked, risk_score, progress),
        }
        self.latest_next_best_action = result
        return result

    def analyze_progress_gaps(
        self,
        plan: AutonomousPlan | Dict[str, Any] | None = None,
        *,
        goal_health: Dict[str, Any] | None = None,
        dependency_state: Dict[str, Any] | None = None,
        simulation_results: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Detect missing tasks, missing milestones, stalled goals, blockers, and risky plans."""
        plan_obj = self._plan(plan) if plan is not None else self.latest_plan
        goal_health = self._dict({} if goal_health is None else goal_health, "goal_health")
        dependency_state = self._dict({} if dependency_state is None else dependency_state, "dependency_state")
        simulation_results = self._list([] if simulation_results is None else simulation_results, "simulation_results")
        missing_milestones = plan_obj is None or len(plan_obj.milestones) == 0
        missing_tasks = plan_obj is None or len(plan_obj.tasks) == 0
        blocked_dependencies = self._blocked_count(dependency_state)
        risk_score = max(self._safe_float(goal_health.get("risk_score"), 0.0), self._max_simulation_risk(simulation_results))
        stalled = self._safe_float(goal_health.get("progress"), 100.0) < 10.0 and risk_score >= 40.0
        gaps = []
        if missing_milestones:
            gaps.append("missing_milestones")
        if missing_tasks:
            gaps.append("missing_tasks")
        if stalled:
            gaps.append("stalled_goal")
        if blocked_dependencies:
            gaps.append("blocked_dependencies")
        if risk_score >= 60.0:
            gaps.append("risk_heavy_plan")
        return {
            "missing_milestones": bool(missing_milestones),
            "missing_tasks": bool(missing_tasks),
            "stalled_goals": bool(stalled),
            "blocked_dependencies": blocked_dependencies,
            "risk_heavy_plan": risk_score >= 60.0,
            "gaps": sorted(gaps),
        }

    def create_recovery_plan(
        self,
        *,
        goal_health: Dict[str, Any] | None = None,
        simulation_result: Dict[str, Any] | None = None,
        dependency_state: Dict[str, Any] | None = None,
    ) -> RecoveryPlan:
        """Generate a non-executing recovery plan for at-risk progress."""
        goal_health = self._dict({} if goal_health is None else goal_health, "goal_health")
        simulation_result = self._dict({} if simulation_result is None else simulation_result, "simulation_result")
        dependency_state = self._dict({} if dependency_state is None else dependency_state, "dependency_state")
        blocked = self._blocked_count(dependency_state)
        risk_score = max(
            self._safe_float(goal_health.get("risk_score"), 0.0),
            self._safe_float(simulation_result.get("risk_score"), 0.0),
        )
        actions = ["Reconfirm goal outcome", "Select one next measurable action"]
        trigger = "goal_at_risk" if risk_score >= 50.0 else "progress_recovery"
        if blocked:
            actions.insert(0, "Unblock critical dependency")
            trigger = "dependency_blockage"
        if self._safe_float(simulation_result.get("success_probability"), 1.0) < 0.5:
            actions.append("Reduce scope until success probability improves")
            trigger = "simulation_failure"
        recovery = RecoveryPlan(
            recovery_plan_id=f"recovery-{trigger}",
            trigger=trigger,
            actions=actions,
            priority=1 if risk_score >= 50.0 or blocked else 2,
            expected_impact=self._bounded(45.0 + blocked * 15.0 + risk_score * 0.25, 0.0, 100.0),
            reasoning="Recovery focuses on blockers, scope control, and measurable progress.",
        )
        self.latest_recovery_plan = recovery
        return recovery

    def create_contingency_plans(
        self,
        plan: AutonomousPlan | Dict[str, Any] | None = None,
    ) -> List[ContingencyPlan]:
        """Generate Plan A, Plan B, and Plan C recommendation alternatives."""
        plan_obj = self._plan(plan) if plan is not None else self.latest_plan
        base_risk = self._safe_float(getattr(plan_obj, "risk_score", 25.0), 25.0)
        contingencies = [
            ContingencyPlan(
                contingency_plan_id="contingency-plan-a",
                scenario="Normal execution",
                actions=["Execute roadmap in recommended order", "Review progress weekly"],
                risk_score=base_risk,
                confidence_score=80.0,
            ),
            ContingencyPlan(
                contingency_plan_id="contingency-plan-b",
                scenario="Reduced capacity",
                actions=["Protect highest-alignment tasks", "Defer low-impact work"],
                risk_score=min(100.0, base_risk + 15.0),
                confidence_score=72.0,
            ),
            ContingencyPlan(
                contingency_plan_id="contingency-plan-c",
                scenario="Dependency failure",
                actions=["Switch to unblocked parallel work", "Create dependency recovery plan"],
                risk_score=min(100.0, base_risk + 25.0),
                confidence_score=68.0,
            ),
        ]
        self.latest_contingency_plans = contingencies
        return contingencies

    def generate_roadmaps(
        self,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> Dict[str, Any]:
        """Generate 7-, 30-, and 90-day roadmaps using StrategicPlanningEngine when available."""
        if behavior_patterns is None:
            behavior_patterns = {}
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        if self.strategic_planning_engine is None:
            return {"7_day": None, "30_day": None, "90_day": None}
        return {
            "7_day": asdict(self.strategic_planning_engine.generate_7_day_plan(tasks, behavior_patterns, now=now)),
            "30_day": asdict(self.strategic_planning_engine.generate_30_day_plan(tasks, behavior_patterns, now=now)),
            "90_day": asdict(self.strategic_planning_engine.generate_90_day_plan(tasks, behavior_patterns, now=now)),
        }

    def score_plan(
        self,
        *,
        tasks: List[Dict[str, Any]],
        goal_health: Dict[str, Any] | None = None,
        dependency_state: Dict[str, Any] | None = None,
        simulation_results: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, float]:
        """Compute bounded quality scores for a plan."""
        tasks = self._list(tasks, "tasks")
        if any(not isinstance(task, dict) for task in tasks):
            raise ValueError("tasks entries must be dictionaries.")
        goal_health = self._dict({} if goal_health is None else goal_health, "goal_health")
        dependency_state = self._dict({} if dependency_state is None else dependency_state, "dependency_state")
        simulation_results = self._list([] if simulation_results is None else simulation_results, "simulation_results")
        blocked = sum(1 for task in tasks if task.get("blocked")) + self._blocked_count(dependency_state)
        task_count = max(1, len(tasks))
        risk_score = self._bounded(max(self._safe_float(goal_health.get("risk_score"), 0.0), self._max_simulation_risk(simulation_results)) + blocked * 8.0, 0.0, 100.0)
        feasibility = self._bounded(100.0 - (blocked / task_count * 55.0) - risk_score * 0.25, 0.0, 100.0)
        dependency_score = self._bounded(100.0 - blocked * 20.0, 0.0, 100.0)
        progress = self._safe_float(goal_health.get("progress"), 50.0)
        goal_alignment = self._bounded(55.0 + progress * 0.25 + min(20.0, task_count * 2.0), 0.0, 100.0)
        overall = self._bounded((feasibility * 0.3) + (dependency_score * 0.25) + ((100.0 - risk_score) * 0.2) + (goal_alignment * 0.25), 0.0, 100.0)
        return {
            "feasibility_score": round(feasibility, 2),
            "dependency_score": round(dependency_score, 2),
            "risk_score": round(risk_score, 2),
            "goal_alignment_score": round(goal_alignment, 2),
            "overall_plan_score": round(overall, 2),
        }

    def explain_plan(self, plan: AutonomousPlan | Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Generate deterministic human-readable plan reasoning."""
        plan_obj = self._plan(plan) if plan is not None else self.latest_plan
        if plan_obj is None:
            return {
                "title": "No autonomous plan available",
                "summary": "No plan has been generated yet.",
                "reasoning": [],
            }
        blocked_count = sum(1 for task in plan_obj.tasks if task.blocked)
        return {
            "title": f"Plan for {plan_obj.objective.title}",
            "summary": plan_obj.reasoning,
            "reasoning": [
                f"Why this task: tasks are ordered by milestone sequence and priority.",
                f"Why now: the plan targets measurable progress with score {plan_obj.overall_plan_score:.2f}.",
                f"Why this order: milestones progress from setup to execution to review.",
                f"Why recovery: {blocked_count} blocked tasks and risk score {plan_obj.risk_score:.2f} determine recovery urgency.",
            ],
        }

    def summarize_autonomous_planning(self) -> Dict[str, Any] | None:
        """Return optional orchestrator-ready autonomous planning outputs."""
        if (
            self.latest_plan is None
            and self.latest_next_best_action is None
            and self.latest_recovery_plan is None
            and not self.latest_contingency_plans
        ):
            return None
        outputs: Dict[str, Any] = {}
        if self.latest_plan is not None:
            outputs["autonomous_plan_summary"] = {
                "plan_id": self.latest_plan.plan_id,
                "objective_id": self.latest_plan.objective.objective_id,
                "milestone_count": len(self.latest_plan.milestones),
                "task_count": len(self.latest_plan.tasks),
                "overall_plan_score": self.latest_plan.overall_plan_score,
                "risk_score": self.latest_plan.risk_score,
            }
        if self.latest_next_best_action is not None:
            outputs["next_best_action"] = dict(self.latest_next_best_action)
        if self.latest_recovery_plan is not None:
            outputs["recovery_plan_summary"] = asdict(self.latest_recovery_plan)
        if self.latest_contingency_plans:
            outputs["contingency_plan_summary"] = [asdict(plan) for plan in self.latest_contingency_plans]
        return outputs

    def _milestone_titles(self, goal: Dict[str, Any]) -> List[str]:
        raw_milestones = goal.get("milestones")
        if isinstance(raw_milestones, list) and raw_milestones:
            titles = []
            for item in raw_milestones:
                if isinstance(item, dict):
                    titles.append(self._text(item.get("title", item.get("milestone_id", "Milestone")), "milestone title"))
                elif isinstance(item, str):
                    titles.append(self._text(item, "milestone title"))
                else:
                    raise ValueError("milestones must contain dictionaries or strings.")
            return titles[:5]
        title = self._text(goal.get("title", "Goal"), "title")
        return [f"Clarify {title}", f"Execute {title}", f"Review {title}"]

    def _tasks_from_milestones(self, milestones: List[PlanMilestone], priority: int) -> List[PlanTask]:
        tasks: List[PlanTask] = []
        sequence = 1
        for milestone in milestones:
            for suffix in ("Define next action", "Complete execution step"):
                tasks.append(
                    PlanTask(
                        task_id=f"{milestone.milestone_id}-task-{len(tasks) + 1}",
                        milestone_id=milestone.milestone_id,
                        title=f"{suffix}: {milestone.title}",
                        sequence=sequence,
                        estimated_duration=1.0,
                        priority=priority,
                        reasoning="Generated from goal decomposition.",
                    )
                )
                sequence += 1
        return tasks

    def _plan(self, plan: AutonomousPlan | Dict[str, Any]) -> AutonomousPlan:
        return plan if isinstance(plan, AutonomousPlan) else AutonomousPlan(**self._dict(plan, "plan"))

    def _next_action_reason(self, blocked: int, risk_score: float, progress: float) -> str:
        if blocked:
            return "Blocked dependencies currently limit forward progress."
        if risk_score >= 60.0:
            return "Risk is high enough that recovery should precede expansion."
        if progress < 25.0:
            return "The goal needs early measurable momentum."
        return "The recommendation balances goal progress, risk, and available evidence."

    def _blocked_count(self, dependency_state: Dict[str, Any]) -> int:
        blocked = dependency_state.get("blocked_tasks", [])
        if isinstance(blocked, list):
            return len(blocked)
        return int(self._safe_float(blocked, 0.0))

    def _max_simulation_risk(self, simulation_results: List[Dict[str, Any]]) -> float:
        risks = []
        for result in simulation_results:
            if not isinstance(result, dict):
                raise ValueError("simulation_results entries must be dictionaries.")
            risks.append(self._safe_float(result.get("risk_score"), 0.0))
        return max(risks, default=0.0)

    def _knowledge_has_nodes(self, knowledge_graph: Any) -> bool:
        graph = knowledge_graph or getattr(self.personal_knowledge_engine, "graph", None)
        nodes = getattr(graph, "nodes", {})
        return bool(nodes)

    def _dict(self, value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        return dict(value)

    def _list(self, value: Any, field_name: str) -> List[Any]:
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list.")
        return list(value)

    def _text(self, value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value.strip()

    def _positive_int(self, value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be a positive integer.")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a positive integer.") from None
        if not math.isfinite(number) or not number.is_integer() or number <= 0:
            raise ValueError(f"{field_name} must be a positive integer.")
        return int(number)

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        return number

    def _bounded(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
