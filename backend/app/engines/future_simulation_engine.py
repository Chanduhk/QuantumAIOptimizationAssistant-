from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from backend.app.domain.simulation_model import SimulationResult, SimulationScenario


class FutureSimulationEngine:
    """Deterministic future-state simulator for goals, dependencies, workload, and strategy."""

    BASELINE = "baseline"
    ACCELERATED = "accelerated"
    DELAYED = "delayed"
    DEPENDENCY_FAILURE = "dependency_failure"
    WORKLOAD_EXPANSION = "workload_expansion"

    def __init__(
        self,
        goal_intelligence_engine: Any | None = None,
        dependency_intelligence_engine: Any | None = None,
        strategic_planning_engine: Any | None = None,
    ) -> None:
        self.goal_intelligence_engine = goal_intelligence_engine
        self.dependency_intelligence_engine = dependency_intelligence_engine
        self.strategic_planning_engine = strategic_planning_engine
        self.simulation_results: List[SimulationResult] = []

    def create_scenario(
        self,
        scenario_name: str,
        horizon_days: int,
        *,
        goal_ids: List[str] | None = None,
        task_ids: List[str] | None = None,
        assumptions: Dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> SimulationScenario:
        """Create a deterministic scenario from caller inputs."""
        if assumptions is None:
            assumptions = {}
        if not isinstance(assumptions, dict):
            raise ValueError("assumptions must be a dictionary.")
        scenario_type = self._scenario_type(assumptions)
        created_at = created_at or datetime.utcnow()
        scenario_id = f"simulation-{scenario_type}-{horizon_days}-{created_at.strftime('%Y%m%d')}"
        return SimulationScenario(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            horizon_days=horizon_days,
            goal_ids=goal_ids or [],
            task_ids=task_ids or [],
            assumptions=dict(assumptions),
            created_at=created_at,
        )

    def simulate_baseline(
        self,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        horizon_days: int = 30,
        now: datetime | None = None,
    ) -> SimulationResult:
        """Simulate the current trajectory."""
        scenario = self.create_scenario(
            "Baseline",
            horizon_days,
            assumptions={"scenario_type": self.BASELINE},
            created_at=now,
        )
        return self.simulate_scenario(scenario, tasks, behavior_patterns, now=now)

    def simulate_accelerated(
        self,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        horizon_days: int = 30,
        now: datetime | None = None,
    ) -> SimulationResult:
        """Simulate increased completion velocity."""
        scenario = self.create_scenario(
            "Accelerated",
            horizon_days,
            assumptions={"scenario_type": self.ACCELERATED, "velocity_multiplier": 1.25},
            created_at=now,
        )
        return self.simulate_scenario(scenario, tasks, behavior_patterns, now=now)

    def simulate_delayed(
        self,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        horizon_days: int = 30,
        now: datetime | None = None,
    ) -> SimulationResult:
        """Simulate reduced productivity and slower execution."""
        scenario = self.create_scenario(
            "Delayed",
            horizon_days,
            assumptions={"scenario_type": self.DELAYED, "velocity_multiplier": 0.65},
            created_at=now,
        )
        return self.simulate_scenario(scenario, tasks, behavior_patterns, now=now)

    def simulate_dependency_failure(
        self,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        horizon_days: int = 30,
        now: datetime | None = None,
    ) -> SimulationResult:
        """Simulate a critical dependency becoming blocked."""
        scenario = self.create_scenario(
            "Dependency Failure",
            horizon_days,
            assumptions={"scenario_type": self.DEPENDENCY_FAILURE, "dependency_failure": True},
            created_at=now,
        )
        return self.simulate_scenario(scenario, tasks, behavior_patterns, now=now)

    def simulate_workload_expansion(
        self,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        horizon_days: int = 30,
        additional_tasks: int = 5,
        now: datetime | None = None,
    ) -> SimulationResult:
        """Simulate added workload entering the horizon."""
        scenario = self.create_scenario(
            "Workload Expansion",
            horizon_days,
            assumptions={
                "scenario_type": self.WORKLOAD_EXPANSION,
                "additional_tasks": additional_tasks,
            },
            created_at=now,
        )
        return self.simulate_scenario(scenario, tasks, behavior_patterns, now=now)

    def simulate_scenario(
        self,
        scenario: SimulationScenario | Dict[str, Any],
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> SimulationResult:
        """Run a deterministic what-if simulation."""
        scenario_obj = scenario if isinstance(scenario, SimulationScenario) else SimulationScenario(**scenario)
        behavior_patterns = behavior_patterns or {}
        if not isinstance(behavior_patterns, dict):
            raise ValueError("behavior_patterns must be a dictionary.")
        now = now or scenario_obj.created_at
        task_list = self._collect_tasks(tasks)
        scenario_type = self._scenario_type(scenario_obj.assumptions)
        task_list = self._apply_scenario_task_changes(task_list, scenario_obj, scenario_type)
        strategic_plan = self._strategic_plan(scenario_obj.horizon_days, task_list, behavior_patterns, now)
        goal_probability = self._goal_probability(behavior_patterns, now, scenario_type)
        milestone_probability = self._milestone_probability(behavior_patterns, scenario_type)
        workload_score = self._workload_score(task_list, behavior_patterns, scenario_obj.horizon_days, scenario_type)
        dependency_risk = self._dependency_risk(task_list, scenario_type)
        strategic_risk = self._safe_float(getattr(strategic_plan, "risk_score", 0.0), 0.0)
        risk_score = self._bounded(
            (strategic_risk * 0.45) + (dependency_risk * 0.3) + (workload_score * 0.25),
            0.0,
            100.0,
        )
        success_probability = self._bounded(
            ((goal_probability + milestone_probability) / 2.0)
            - (risk_score / 180.0)
            + self._scenario_success_adjustment(scenario_type),
            0.0,
            1.0,
        )
        confidence_score = self._confidence_score(task_list, behavior_patterns, risk_score, strategic_plan)
        projected_completion_days = self._projected_completion_days(
            task_list,
            behavior_patterns,
            scenario_obj.horizon_days,
            scenario_type,
        )
        result = SimulationResult(
            scenario_id=scenario_obj.scenario_id,
            success_probability=round(success_probability, 4),
            goal_completion_probability=round(goal_probability, 4),
            milestone_completion_probability=round(milestone_probability, 4),
            workload_score=round(workload_score, 2),
            risk_score=round(risk_score, 2),
            confidence_score=round(confidence_score, 2),
            projected_state={
                "scenario_type": scenario_type,
                "projected_completion_days": projected_completion_days,
                "projected_goal_state": self._projected_goal_state(goal_probability),
                "task_count": len(task_list),
                "blocked_task_count": self._blocked_task_count(task_list, scenario_type),
                "strategic_plan_id": getattr(strategic_plan, "plan_id", None),
            },
            recommendations=self._recommendations(
                scenario_type=scenario_type,
                risk_score=risk_score,
                workload_score=workload_score,
                dependency_risk=dependency_risk,
                success_probability=success_probability,
            ),
        )
        self.simulation_results.append(result)
        return result

    def compare_scenarios(
        self,
        scenarios: List[SimulationScenario | Dict[str, Any]],
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> List[Dict[str, Any]]:
        """Run and rank scenarios from best outcome to worst outcome."""
        if not isinstance(scenarios, list):
            raise ValueError("scenarios must be a list.")
        results = [self.simulate_scenario(scenario, tasks, behavior_patterns, now=now) for scenario in scenarios]
        ranked = sorted(
            results,
            key=lambda result: (
                -result.success_probability,
                result.risk_score,
                -result.confidence_score,
                result.scenario_id,
            ),
        )
        return [
            {
                "rank": index,
                **asdict(result),
            }
            for index, result in enumerate(ranked, start=1)
        ]

    def summarize_future_projection(self) -> Dict[str, Any] | None:
        """Return a compact summary of the latest simulation, if one exists."""
        if not self.simulation_results:
            return None
        latest = self.simulation_results[-1]
        return {
            "scenario_id": latest.scenario_id,
            "success_probability": latest.success_probability,
            "risk_score": latest.risk_score,
            "confidence_score": latest.confidence_score,
            "projected_completion_days": latest.projected_state.get("projected_completion_days"),
            "recommendation_count": len(latest.recommendations),
        }

    def _strategic_plan(
        self,
        horizon_days: int,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        now: datetime,
    ) -> Any:
        if self.strategic_planning_engine is None:
            return None
        return self.strategic_planning_engine.generate_plan(
            horizon_days,
            tasks=tasks,
            behavior_patterns=behavior_patterns,
            now=now,
        )

    def _goal_probability(self, behavior_patterns: Dict[str, Any], now: datetime, scenario_type: str) -> float:
        forecasts = []
        if self.strategic_planning_engine is not None:
            forecasts = self.strategic_planning_engine.forecast_goals(behavior_patterns, now=now)
        if forecasts:
            base = sum(float(item["goal_completion_probability"]) for item in forecasts) / len(forecasts)
        else:
            base = self._productivity_factor(behavior_patterns)
        return self._bounded(base * self._scenario_velocity(scenario_type), 0.0, 1.0)

    def _milestone_probability(self, behavior_patterns: Dict[str, Any], scenario_type: str) -> float:
        forecasts = []
        if self.strategic_planning_engine is not None:
            forecasts = self.strategic_planning_engine.forecast_milestones(behavior_patterns)
        if forecasts:
            base = sum(float(item["milestone_completion_probability"]) for item in forecasts) / len(forecasts)
        else:
            base = self._productivity_factor(behavior_patterns)
        return self._bounded(base * self._scenario_velocity(scenario_type), 0.0, 1.0)

    def _dependency_risk(self, tasks: List[Dict[str, Any]], scenario_type: str) -> float:
        blocked_count = self._blocked_task_count(tasks, scenario_type)
        bottleneck_score = 0.0
        if self.dependency_intelligence_engine is not None:
            bottlenecks = self.dependency_intelligence_engine.detect_bottlenecks()
            bottleneck_score = max(
                (self._safe_float(item.get("dependency_impact_score"), 0.0) for item in bottlenecks),
                default=0.0,
            )
        failure_penalty = 25.0 if scenario_type == self.DEPENDENCY_FAILURE else 0.0
        return self._bounded((blocked_count * 18.0) + (bottleneck_score * 0.35) + failure_penalty, 0.0, 100.0)

    def _workload_score(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        horizon_days: int,
        scenario_type: str,
    ) -> float:
        total_hours = sum(self._task_duration(task) for task in tasks)
        capacity = self._daily_capacity(behavior_patterns) * horizon_days
        overload = max(0.0, (total_hours / capacity) - 1.0) if capacity > 0 else 0.0
        expansion_penalty = 18.0 if scenario_type == self.WORKLOAD_EXPANSION else 0.0
        return self._bounded((overload * 70.0) + expansion_penalty, 0.0, 100.0)

    def _projected_completion_days(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        horizon_days: int,
        scenario_type: str,
    ) -> int:
        if not tasks:
            return 0
        total_hours = sum(self._task_duration(task) for task in tasks)
        velocity = max(0.1, self._scenario_velocity(scenario_type))
        daily_capacity = self._daily_capacity(behavior_patterns) * velocity
        projected_days = math.ceil(total_hours / daily_capacity) if daily_capacity > 0 else horizon_days
        if scenario_type == self.DEPENDENCY_FAILURE:
            projected_days += max(1, len(tasks) // 3)
        return max(1, int(projected_days))

    def _projected_goal_state(self, probability: float) -> str:
        if probability >= 0.75:
            return "on_track"
        if probability >= 0.45:
            return "at_risk"
        return "likely_delayed"

    def _recommendations(
        self,
        *,
        scenario_type: str,
        risk_score: float,
        workload_score: float,
        dependency_risk: float,
        success_probability: float,
    ) -> List[str]:
        recommendations: List[str] = []
        if success_probability < 0.5:
            recommendations.append("Prioritize highest-impact goal tasks")
        if dependency_risk >= 30.0:
            recommendations.append("Recover or unblock critical dependencies")
        if workload_score >= 25.0:
            recommendations.append("Reduce workload or extend planning horizon")
        if risk_score >= 50.0:
            recommendations.append("Create mitigation plan for high-risk milestones")
        if scenario_type == self.ACCELERATED:
            recommendations.append("Maintain acceleration by protecting focus capacity")
        if scenario_type == self.WORKLOAD_EXPANSION:
            recommendations.append("Defer low-alignment tasks before accepting expansion")
        if not recommendations:
            recommendations.append("Maintain current execution strategy")
        return sorted(dict.fromkeys(recommendations))

    def _apply_scenario_task_changes(
        self,
        tasks: List[Dict[str, Any]],
        scenario: SimulationScenario,
        scenario_type: str,
    ) -> List[Dict[str, Any]]:
        changed = [dict(task) for task in tasks]
        if scenario_type == self.WORKLOAD_EXPANSION:
            additional_tasks = int(self._safe_float(scenario.assumptions.get("additional_tasks", 5), 5.0))
            if additional_tasks < 0:
                raise ValueError("additional_tasks must be non-negative.")
            for index in range(additional_tasks):
                changed.append(
                    {
                        "id": f"simulated-extra-{index + 1}",
                        "estimated_duration": 1.0,
                        "goal_id": None,
                    }
                )
        if scenario.task_ids:
            allowed = set(scenario.task_ids)
            changed = [task for task in changed if task.get("id") in allowed]
        return changed

    def _collect_tasks(self, tasks: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
        if tasks is None:
            tasks = []
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list of dictionaries.")
        collected: List[Dict[str, Any]] = []
        seen_ids = set()
        for index, task in enumerate(tasks, start=1):
            if not isinstance(task, dict):
                raise ValueError("Each task must be a dictionary.")
            task_copy = dict(task)
            task_id = task_copy.get("id", f"task-{index}")
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError("Each task id must be a non-empty string when provided.")
            task_id = task_id.strip()
            if task_id in seen_ids:
                raise ValueError("task ids must be unique.")
            seen_ids.add(task_id)
            task_copy["id"] = task_id
            self._task_duration(task_copy)
            collected.append(task_copy)
        return collected

    def _blocked_task_count(self, tasks: List[Dict[str, Any]], scenario_type: str) -> int:
        if self.dependency_intelligence_engine is None or not tasks:
            blocked = sum(1 for task in tasks if task.get("blocked"))
        else:
            blocked = len(self.dependency_intelligence_engine.detect_blocked_tasks(tasks))
        if scenario_type == self.DEPENDENCY_FAILURE and tasks:
            blocked = max(1, blocked)
        return blocked

    def _scenario_type(self, assumptions: Dict[str, Any]) -> str:
        scenario_type = str(assumptions.get("scenario_type", self.BASELINE)).strip().lower()
        supported = {
            self.BASELINE,
            self.ACCELERATED,
            self.DELAYED,
            self.DEPENDENCY_FAILURE,
            self.WORKLOAD_EXPANSION,
        }
        if scenario_type not in supported:
            raise ValueError("scenario_type must be baseline, accelerated, delayed, dependency_failure, or workload_expansion.")
        return scenario_type

    def _scenario_velocity(self, scenario_type: str) -> float:
        return {
            self.BASELINE: 1.0,
            self.ACCELERATED: 1.25,
            self.DELAYED: 0.65,
            self.DEPENDENCY_FAILURE: 0.8,
            self.WORKLOAD_EXPANSION: 0.9,
        }[scenario_type]

    def _scenario_success_adjustment(self, scenario_type: str) -> float:
        return {
            self.BASELINE: 0.0,
            self.ACCELERATED: 0.08,
            self.DELAYED: -0.12,
            self.DEPENDENCY_FAILURE: -0.18,
            self.WORKLOAD_EXPANSION: -0.08,
        }[scenario_type]

    def _confidence_score(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        risk_score: float,
        strategic_plan: Any,
    ) -> float:
        plan_confidence = self._safe_float(getattr(strategic_plan, "confidence_score", 60.0), 60.0)
        productivity_confidence = self._productivity_factor(behavior_patterns) * 20.0
        evidence = min(15.0, len(tasks) * 2.0)
        return self._bounded((plan_confidence * 0.55) + productivity_confidence + evidence - (risk_score * 0.15), 0.0, 100.0)

    def _productivity_factor(self, behavior_patterns: Dict[str, Any]) -> float:
        if "average_productivity" in behavior_patterns:
            value = self._safe_float(behavior_patterns.get("average_productivity"), 0.5)
            return self._bounded(value / 100.0 if value > 1.0 else value, 0.0, 1.0)
        hourly = behavior_patterns.get("hourly_productivity", {})
        if isinstance(hourly, dict) and hourly:
            values = [self._safe_float(value, 0.0) for value in hourly.values()]
            return self._bounded((sum(values) / len(values)) / 100.0, 0.0, 1.0)
        return 0.5

    def _daily_capacity(self, behavior_patterns: Dict[str, Any]) -> float:
        for key in ("daily_capacity_hours", "available_hours", "focus_hours_per_day"):
            if key in behavior_patterns:
                return self._bounded(self._safe_float(behavior_patterns[key], 6.0), 1.0, 16.0)
        return 6.0

    def _task_duration(self, task: Dict[str, Any]) -> float:
        value = task.get("estimated_duration", task.get("duration", 1.0))
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError("task duration must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError("task duration must be finite.")
        if number <= 0:
            raise ValueError("task duration must be positive.")
        return number

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
