from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from backend.app.domain.adaptive_life_model import (
    AdaptiveRecommendation,
    LifeSignal,
    Opportunity,
    RiskAlert,
)


class AdaptiveLifeOperatingSystem:
    """Passive life operating layer that detects signals and recommends adaptations."""

    def __init__(self) -> None:
        self.life_signals: List[LifeSignal] = []
        self.latest_analysis: Dict[str, Any] | None = None

    def detect_opportunities(
        self,
        *,
        goals: List[Dict[str, Any]] | None = None,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        dependency_analysis: Dict[str, Any] | None = None,
    ) -> List[Opportunity]:
        """Detect ranked opportunities without taking actions."""
        goals = self._dict_list(goals or [], "goals")
        tasks = self._dict_list(tasks or [], "tasks")
        behavior_patterns = self._dict({} if behavior_patterns is None else behavior_patterns, "behavior_patterns")
        dependency_analysis = self._dict({} if dependency_analysis is None else dependency_analysis, "dependency_analysis")
        opportunities: List[Opportunity] = []
        for goal in goals:
            progress = self._safe_float(goal.get("progress"), 0.0)
            priority = self._safe_float(goal.get("priority"), 1.0)
            if progress >= 60.0 and priority >= 5.0:
                goal_id = str(goal.get("goal_id", goal.get("id", "goal")))
                opportunities.append(
                    Opportunity(
                        opportunity_id=f"opportunity-momentum-{goal_id}",
                        category="high_momentum_goal",
                        impact_score=min(100.0, progress * 0.6 + priority * 5.0),
                        confidence=0.82,
                        recommended_action=f"Protect focused execution for {goal_id}",
                        expected_benefit="Convert existing momentum into visible goal progress",
                    )
                )
        quick_wins = [
            task for task in tasks
            if self._task_duration(task) <= 1.0 and self._safe_float(task.get("priority"), 1.0) >= 3.0
        ]
        if quick_wins:
            opportunities.append(
                Opportunity(
                    opportunity_id="opportunity-quick-wins",
                    category="quick_win",
                    impact_score=min(100.0, len(quick_wins) * 12.0),
                    confidence=0.78,
                    recommended_action="Batch quick wins into the next high-energy block",
                    expected_benefit="Increase completion velocity with low execution cost",
                )
            )
        if dependency_analysis.get("blocked_tasks") == [] and dependency_analysis.get("critical_path"):
            opportunities.append(
                Opportunity(
                    opportunity_id="opportunity-dependency-unlock",
                    category="dependency_unlock",
                    impact_score=72.0,
                    confidence=0.75,
                    recommended_action="Advance the first available critical-path task",
                    expected_benefit="Preserve downstream execution flow",
                )
            )
        hourly_productivity = behavior_patterns.get("hourly_productivity", {})
        if isinstance(hourly_productivity, dict) and hourly_productivity:
            best_hour, best_score = max(
                ((str(hour), self._safe_float(score, 0.0)) for hour, score in hourly_productivity.items()),
                key=lambda item: (item[1], item[0]),
            )
            if best_score >= 75.0:
                opportunities.append(
                    Opportunity(
                        opportunity_id=f"opportunity-productive-hour-{best_hour}",
                        category="productive_period",
                        impact_score=min(100.0, best_score),
                        confidence=0.8,
                        recommended_action=f"Place strategic work near hour {best_hour}",
                        expected_benefit="Use unusually productive periods for leverage tasks",
                    )
                )
        return sorted(opportunities, key=lambda item: (-item.impact_score, item.opportunity_id))

    def detect_risks(
        self,
        *,
        goals: List[Dict[str, Any]] | None = None,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        dependency_analysis: Dict[str, Any] | None = None,
        simulation_summary: Dict[str, Any] | None = None,
        reflection_summary: Dict[str, Any] | None = None,
    ) -> List[RiskAlert]:
        """Detect ranked life-system risks."""
        goals = self._dict_list(goals or [], "goals")
        tasks = self._dict_list(tasks or [], "tasks")
        behavior_patterns = self._dict({} if behavior_patterns is None else behavior_patterns, "behavior_patterns")
        dependency_analysis = self._dict({} if dependency_analysis is None else dependency_analysis, "dependency_analysis")
        simulation_summary = self._dict({} if simulation_summary is None else simulation_summary, "simulation_summary")
        reflection_summary = self._dict({} if reflection_summary is None else reflection_summary, "reflection_summary")
        risks: List[RiskAlert] = []
        capacity = self.monitor_capacity(tasks=tasks, behavior_patterns=behavior_patterns)
        if capacity["load_status"] == "overload":
            risks.append(
                RiskAlert(
                    alert_id="risk-overload",
                    risk_type="overloaded_schedule",
                    severity="high" if capacity["capacity_utilization"] < 1.5 else "critical",
                    confidence=0.86,
                    affected_goals=self._goal_ids(goals),
                    recommended_mitigation="Reduce workload or expand the planning horizon",
                )
            )
        blocked_tasks = dependency_analysis.get("blocked_tasks", [])
        if isinstance(blocked_tasks, list) and blocked_tasks:
            risks.append(
                RiskAlert(
                    alert_id="risk-blocked-dependencies",
                    risk_type="blocked_dependencies",
                    severity="high",
                    confidence=0.84,
                    affected_goals=self._goal_ids(goals),
                    recommended_mitigation="Resolve prerequisite blockers before adding new work",
                )
            )
        neglected_goals = [
            str(goal.get("goal_id", goal.get("id")))
            for goal in goals
            if self._safe_float(goal.get("days_inactive"), 0.0) >= 30.0 or goal.get("neglected") is True
        ]
        if neglected_goals:
            risks.append(
                RiskAlert(
                    alert_id="risk-neglected-goals",
                    risk_type="neglected_goals",
                    severity="medium",
                    confidence=0.78,
                    affected_goals=neglected_goals,
                    recommended_mitigation="Schedule a recovery action for neglected goals",
                )
            )
        productivity_trend = str(behavior_patterns.get("productivity_trend", "")).lower()
        if productivity_trend == "declining" or self._safe_float(reflection_summary.get("average_error"), 0.0) >= 35.0:
            risks.append(
                RiskAlert(
                    alert_id="risk-declining-productivity",
                    risk_type="declining_productivity",
                    severity="high",
                    confidence=0.76,
                    affected_goals=self._goal_ids(goals),
                    recommended_mitigation="Lower planning confidence and protect recovery capacity",
                )
            )
        if self._safe_float(simulation_summary.get("risk_score"), 0.0) >= 50.0:
            risks.append(
                RiskAlert(
                    alert_id="risk-forecast-failure",
                    risk_type="forecast_failure_risk",
                    severity="high",
                    confidence=0.74,
                    affected_goals=self._goal_ids(goals),
                    recommended_mitigation="Run mitigation planning for high-risk projected outcomes",
                )
            )
        return sorted(risks, key=lambda item: (self._severity_rank(item.severity), item.alert_id))

    def analyze_burnout(
        self,
        *,
        behavior_patterns: Dict[str, Any] | None = None,
        tasks: List[Dict[str, Any]] | None = None,
        simulation_summary: Dict[str, Any] | None = None,
        reflection_summary: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Estimate burnout probability from load, trend, forecast risk, and reflection errors."""
        behavior_patterns = self._dict({} if behavior_patterns is None else behavior_patterns, "behavior_patterns")
        tasks = self._dict_list(tasks or [], "tasks")
        simulation_summary = self._dict({} if simulation_summary is None else simulation_summary, "simulation_summary")
        reflection_summary = self._dict({} if reflection_summary is None else reflection_summary, "reflection_summary")
        capacity = self.monitor_capacity(tasks=tasks, behavior_patterns=behavior_patterns)
        overload_component = max(0.0, capacity["capacity_utilization"] - 1.0) * 0.45
        stress = self._safe_float(behavior_patterns.get("stress_penalty"), 0.0)
        stress_component = stress if stress <= 1.0 else stress / 100.0
        trend_component = 0.2 if str(behavior_patterns.get("productivity_trend", "")).lower() == "declining" else 0.0
        simulation_component = self._safe_float(simulation_summary.get("risk_score"), 0.0) / 300.0
        reflection_component = self._safe_float(reflection_summary.get("average_error"), 0.0) / 400.0
        probability = self._bounded(
            overload_component + stress_component + trend_component + simulation_component + reflection_component,
            0.0,
            1.0,
        )
        return {
            "burnout_probability": round(probability, 4),
            "burnout_level": self._level(probability),
        }

    def analyze_strategic_drift(
        self,
        *,
        goals: List[Dict[str, Any]] | None = None,
        tasks: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Measure alignment between daily actions and stated goals."""
        goals = self._dict_list(goals or [], "goals")
        tasks = self._dict_list(tasks or [], "tasks")
        if not goals or not tasks:
            return {"strategic_alignment_score": 100.0, "strategic_drift_level": "low"}
        goal_ids = set(self._goal_ids(goals))
        aligned = sum(1 for task in tasks if task.get("goal_id") in goal_ids)
        score = (aligned / len(tasks)) * 100.0
        drift = 1.0 - (score / 100.0)
        return {
            "strategic_alignment_score": round(score, 2),
            "strategic_drift_level": self._level(drift),
        }

    def monitor_capacity(
        self,
        *,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Calculate available capacity, projected workload, and load status."""
        tasks = self._dict_list(tasks or [], "tasks")
        behavior_patterns = self._dict({} if behavior_patterns is None else behavior_patterns, "behavior_patterns")
        available_capacity = self._daily_capacity(behavior_patterns)
        projected_workload = sum(self._task_duration(task) for task in tasks)
        utilization = projected_workload / available_capacity if available_capacity > 0 else 0.0
        if utilization < 0.5:
            status = "underload"
        elif utilization <= 1.0:
            status = "healthy_load"
        else:
            status = "overload"
        return {
            "available_capacity": round(available_capacity, 2),
            "projected_workload": round(projected_workload, 2),
            "capacity_utilization": round(utilization, 4),
            "load_status": status,
        }

    def analyze_momentum(
        self,
        *,
        goals: List[Dict[str, Any]] | None = None,
        tasks: List[Dict[str, Any]] | None = None,
        forecast_summary: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Analyze goal momentum and task completion velocity."""
        goals = self._dict_list(goals or [], "goals")
        tasks = self._dict_list(tasks or [], "tasks")
        forecast_summary = self._dict({} if forecast_summary is None else forecast_summary, "forecast_summary")
        completed = sum(1 for task in tasks if task.get("completed") is True)
        velocity = completed / len(tasks) if tasks else 0.0
        average_progress = (
            sum(self._safe_float(goal.get("progress"), 0.0) for goal in goals) / len(goals)
            if goals else 0.0
        )
        forecast_success = self._safe_float(
            forecast_summary.get("success_probability", forecast_summary.get("goal_completion_probability", 0.5)),
            0.5,
        )
        momentum_score = self._bounded((velocity * 40.0) + (average_progress * 0.4) + (forecast_success * 20.0), 0.0, 100.0)
        if momentum_score >= 70.0:
            trajectory = "accelerating"
        elif momentum_score >= 40.0:
            trajectory = "stable"
        else:
            trajectory = "declining"
        return {
            "goal_momentum_score": round(momentum_score, 2),
            "task_completion_velocity": round(velocity, 4),
            "forecast_trajectory": trajectory,
        }

    def generate_adaptive_recommendations(
        self,
        *,
        opportunities: List[Opportunity] | None = None,
        risks: List[RiskAlert] | None = None,
        burnout: Dict[str, Any] | None = None,
        strategic_drift: Dict[str, Any] | None = None,
        capacity: Dict[str, Any] | None = None,
        momentum: Dict[str, Any] | None = None,
    ) -> List[AdaptiveRecommendation]:
        """Generate deterministic recommendations. Recommendations are advisory only."""
        opportunities = opportunities or []
        risks = risks or []
        burnout = self._dict({} if burnout is None else burnout, "burnout")
        strategic_drift = self._dict({} if strategic_drift is None else strategic_drift, "strategic_drift")
        capacity = self._dict({} if capacity is None else capacity, "capacity")
        momentum = self._dict({} if momentum is None else momentum, "momentum")
        recommendations: List[AdaptiveRecommendation] = []
        if risks:
            top_risk = sorted(risks, key=lambda item: (self._severity_rank(item.severity), item.alert_id))[0]
            recommendations.append(
                AdaptiveRecommendation(
                    recommendation_id=f"adaptive-risk-{top_risk.risk_type}",
                    category="risk_mitigation",
                    priority=1,
                    reason=top_risk.risk_type,
                    action=top_risk.recommended_mitigation,
                    expected_outcome="Reduce near-term execution risk",
                )
            )
        if burnout.get("burnout_level") in {"high", "critical"}:
            recommendations.append(
                AdaptiveRecommendation(
                    recommendation_id="adaptive-burnout-recovery",
                    category="burnout_prevention",
                    priority=1,
                    reason="Burnout probability is elevated",
                    action="Schedule recovery capacity before adding new commitments",
                    expected_outcome="Protect sustainable productivity",
                )
            )
        if strategic_drift.get("strategic_alignment_score", 100.0) < 60.0:
            recommendations.append(
                AdaptiveRecommendation(
                    recommendation_id="adaptive-strategic-realignment",
                    category="strategic_alignment",
                    priority=2,
                    reason="Daily actions are drifting from stated goals",
                    action="Move one goal-aligned task into the next planning block",
                    expected_outcome="Increase strategic alignment",
                )
            )
        if capacity.get("load_status") == "overload":
            recommendations.append(
                AdaptiveRecommendation(
                    recommendation_id="adaptive-capacity-rebalance",
                    category="capacity",
                    priority=1,
                    reason="Projected workload exceeds available capacity",
                    action="Defer or reduce low-impact tasks",
                    expected_outcome="Restore healthy load",
                )
            )
        if momentum.get("forecast_trajectory") == "declining":
            recommendations.append(
                AdaptiveRecommendation(
                    recommendation_id="adaptive-momentum-recovery",
                    category="momentum",
                    priority=2,
                    reason="Goal momentum is declining",
                    action="Choose a quick win tied to a high-priority goal",
                    expected_outcome="Rebuild execution momentum",
                )
            )
        if opportunities:
            top_opportunity = opportunities[0]
            recommendations.append(
                AdaptiveRecommendation(
                    recommendation_id=f"adaptive-opportunity-{top_opportunity.category}",
                    category="opportunity",
                    priority=3,
                    reason=top_opportunity.category,
                    action=top_opportunity.recommended_action,
                    expected_outcome=top_opportunity.expected_benefit,
                )
            )
        return sorted(
            {item.recommendation_id: item for item in recommendations}.values(),
            key=lambda item: (item.priority, item.recommendation_id),
        )

    def generate_weekly_executive_brief(
        self,
        *,
        goals: List[Dict[str, Any]] | None = None,
        tasks: List[Dict[str, Any]] | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        dependency_analysis: Dict[str, Any] | None = None,
        simulation_summary: Dict[str, Any] | None = None,
        reflection_summary: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Generate the weekly executive briefing."""
        opportunities = self.detect_opportunities(
            goals=goals,
            tasks=tasks,
            behavior_patterns=behavior_patterns,
            dependency_analysis=dependency_analysis,
        )
        risks = self.detect_risks(
            goals=goals,
            tasks=tasks,
            behavior_patterns=behavior_patterns,
            dependency_analysis=dependency_analysis,
            simulation_summary=simulation_summary,
            reflection_summary=reflection_summary,
        )
        burnout = self.analyze_burnout(
            behavior_patterns=behavior_patterns,
            tasks=tasks,
            simulation_summary=simulation_summary,
            reflection_summary=reflection_summary,
        )
        drift = self.analyze_strategic_drift(goals=goals, tasks=tasks)
        capacity = self.monitor_capacity(tasks=tasks, behavior_patterns=behavior_patterns)
        momentum = self.analyze_momentum(goals=goals, tasks=tasks, forecast_summary=simulation_summary)
        recommendations = self.generate_adaptive_recommendations(
            opportunities=opportunities,
            risks=risks,
            burnout=burnout,
            strategic_drift=drift,
            capacity=capacity,
            momentum=momentum,
        )
        brief = {
            "top_opportunities": [asdict(item) for item in opportunities[:3]],
            "top_risks": [asdict(item) for item in risks[:3]],
            "burnout_assessment": burnout,
            "strategic_alignment": drift,
            "goal_momentum": momentum,
            "capacity": capacity,
            "recommended_actions": [asdict(item) for item in recommendations],
        }
        self.latest_analysis = brief
        self._record_signals(opportunities, risks)
        return brief

    def summarize_adaptive_life(self) -> Dict[str, Any] | None:
        """Return compact ALOS summary only after analysis exists."""
        if self.latest_analysis is None:
            return None
        return {
            "opportunity_count": len(self.latest_analysis["top_opportunities"]),
            "risk_count": len(self.latest_analysis["top_risks"]),
            "recommendation_count": len(self.latest_analysis["recommended_actions"]),
            "burnout_probability": self.latest_analysis["burnout_assessment"]["burnout_probability"],
            "strategic_alignment_score": self.latest_analysis["strategic_alignment"]["strategic_alignment_score"],
            "load_status": self.latest_analysis["capacity"]["load_status"],
        }

    def _record_signals(self, opportunities: List[Opportunity], risks: List[RiskAlert]) -> None:
        self.life_signals = [
            LifeSignal(
                signal_id=f"signal-opportunity-{item.opportunity_id}",
                signal_type=item.category,
                severity="medium",
                confidence=item.confidence,
                source_engine="AdaptiveLifeOperatingSystem",
                description=item.expected_benefit,
            )
            for item in opportunities
        ] + [
            LifeSignal(
                signal_id=f"signal-risk-{item.alert_id}",
                signal_type=item.risk_type,
                severity=item.severity,
                confidence=item.confidence,
                source_engine="AdaptiveLifeOperatingSystem",
                description=item.recommended_mitigation,
            )
            for item in risks
        ]

    def _goal_ids(self, goals: List[Dict[str, Any]]) -> List[str]:
        return sorted(
            {
                str(goal.get("goal_id", goal.get("id")))
                for goal in goals
                if goal.get("goal_id", goal.get("id")) is not None
            }
        )

    def _dict_list(self, value: Any, field_name: str) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list of dictionaries.")
        if any(not isinstance(item, dict) for item in value):
            raise ValueError(f"{field_name} entries must be dictionaries.")
        return [dict(item) for item in value]

    def _dict(self, value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        return dict(value)

    def _daily_capacity(self, behavior_patterns: Dict[str, Any]) -> float:
        for key in ("daily_capacity_hours", "available_hours", "focus_hours_per_day"):
            if key in behavior_patterns:
                return self._bounded(self._safe_float(behavior_patterns[key], 6.0), 1.0, 16.0)
        return 6.0

    def _task_duration(self, task: Dict[str, Any]) -> float:
        value = task.get("estimated_duration", task.get("duration", 1.0))
        number = self._safe_float(value, 1.0)
        if number <= 0.0:
            raise ValueError("task duration must be positive.")
        return number

    def _level(self, probability: float) -> str:
        if probability >= 0.75:
            return "critical"
        if probability >= 0.5:
            return "high"
        if probability >= 0.25:
            return "medium"
        return "low"

    def _severity_rank(self, severity: str) -> int:
        return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(severity, 4)

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
