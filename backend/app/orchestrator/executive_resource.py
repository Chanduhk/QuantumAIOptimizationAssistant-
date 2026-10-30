from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Dict, List

from backend.app.domain.optimization_input_contract import normalize_duration
from backend.app.domain.executive_resource_model import (
    AttentionAllocation,
    CapacityForecast,
    EnergyProfile,
    ExecutiveResourceSummary,
    ResourceAllocation,
    ResourceConflict,
    ResourceRecommendation,
    ResourceState,
)


class ExecutiveResourceEngine:
    """Supervise finite executive resources from existing executive outputs.

    Inputs are read-only dictionaries already produced by Executive Reasoning,
    Executive Experience, Executive Execution, Adaptive OS, Behavior Learning,
    and Context Awareness. Outputs are recommendation-only resource diagnostics.
    """

    DEFAULT_MAX_HISTORY = 500
    OVER_UTILIZATION_THRESHOLD = 110.0
    UNDER_UTILIZATION_THRESHOLD = 35.0
    ATTENTION_FRAGMENTATION_THRESHOLD = 55.0
    CONTEXT_SWITCH_THRESHOLD = 6
    HIGH_LOAD_THRESHOLD = 75.0
    LOW_CAPACITY_THRESHOLD = 35.0

    def __init__(self, max_history: int = DEFAULT_MAX_HISTORY) -> None:
        if not isinstance(max_history, int) or isinstance(max_history, bool) or max_history <= 0:
            raise ValueError("max_history must be a positive integer.")
        self.max_history = max_history
        self._history: List[ExecutiveResourceSummary] = []

    def evaluate_time_budget(self, executive_context: Dict[str, Any] | None = None, execution_outputs: Dict[str, Any] | None = None) -> ResourceAllocation:
        """Evaluate time allocation quality from context and execution outputs."""
        context = self._dict(executive_context or {}, "executive_context")
        execution = self._dict(execution_outputs or {}, "execution_outputs")
        workload = context.get("context", {}) if isinstance(context.get("context"), dict) else {}
        tasks = workload.get("current_tasks", []) if isinstance(workload.get("current_tasks"), list) else []
        consumed = self._task_time_percent(tasks)
        planned = self._nested_score(execution, ["execution_state", "progress"], 50.0)
        utilization = self._utilization(consumed, max(1.0, planned))
        return ResourceAllocation("resource-allocation-time", "time", planned, consumed, utilization, 2, "ExecutiveExecution", {"task_count": len(tasks)})

    def evaluate_energy_budget(self, executive_context: Dict[str, Any] | None = None, behavior_learning: Dict[str, Any] | None = None) -> EnergyProfile:
        """Evaluate energy stability using existing context and behavior-learning signals."""
        context = self._dict(executive_context or {}, "executive_context")
        learning = self._dict(behavior_learning or {}, "behavior_learning")
        patterns = self._nested_dict(context, ["context", "behavior_patterns"])
        average_energy = self._score(patterns.get("average_energy_level", patterns.get("energy_level", 65.0)), 0.0, 100.0)
        burnout = self._nested_score(context, ["adaptive_life", "burnout_probability"], 0.0)
        volatility = self._nested_score(learning, ["learning_snapshot", "behavior_volatility"], 20.0)
        consumed = self._clamp(100.0 - average_energy + burnout * 0.35, 0.0, 100.0)
        stability = self._clamp(100.0 - consumed * 0.45 - volatility * 0.25, 0.0, 100.0)
        recovery = self._clamp(average_energy - burnout * 0.25 + 20.0, 0.0, 100.0)
        return EnergyProfile("resource-energy-profile", average_energy, consumed, stability, recovery, {"burnout_probability": burnout})

    def evaluate_attention_budget(self, executive_context: Dict[str, Any] | None = None, behavior_learning: Dict[str, Any] | None = None) -> AttentionAllocation:
        """Evaluate attention distribution from task mix and behavior signals."""
        context = self._dict(executive_context or {}, "executive_context")
        learning = self._dict(behavior_learning or {}, "behavior_learning")
        tasks = self._tasks_from_context(context)
        types = [str(task.get("task_type", task.get("type", "general"))).strip().lower() or "general" for task in tasks]
        unique_types = len(set(types))
        focus_blocks = len([task for task in tasks if self._duration(task) >= 1.5])
        context_switches = max(0, unique_types - 1)
        meeting_load = round(100.0 * types.count("meeting") / max(1, len(types)), 2)
        learned_focus = self._nested_score(learning, ["behavior_learning_summary", "consistency_score"], 65.0)
        fragmentation = self._clamp(context_switches * 12.0 + meeting_load * 0.4, 0.0, 100.0)
        deep_work = self._clamp(learned_focus - fragmentation * 0.35 + focus_blocks * 5.0, 0.0, 100.0)
        return AttentionAllocation("resource-attention-allocation", focus_blocks, meeting_load, context_switches, deep_work, fragmentation, {"task_types": sorted(set(types))})

    def evaluate_capacity_budget(self, executive_context: Dict[str, Any] | None = None, execution_outputs: Dict[str, Any] | None = None) -> CapacityForecast:
        """Evaluate near-term capacity from execution and context outputs."""
        context = self._dict(executive_context or {}, "executive_context")
        execution = self._dict(execution_outputs or {}, "execution_outputs")
        tasks = self._tasks_from_context(context)
        demand = self._task_time_percent(tasks)
        execution_capacity = self._nested_score(execution, ["execution_health", "execution_health"], 70.0)
        available = self._clamp(execution_capacity, 0.0, 100.0)
        utilization = self._utilization(demand, max(1.0, available))
        risk = "critical" if utilization >= 140.0 else "high" if utilization >= 115.0 else "medium" if utilization >= 90.0 else "low"
        confidence = self._nested_score(execution, ["execution_confidence", "confidence"], 55.0)
        return CapacityForecast("resource-capacity-forecast", 7, available, demand, utilization, risk, confidence, {"task_count": len(tasks)})

    def evaluate_cognitive_load(self, executive_context: Dict[str, Any] | None = None, reasoning: Dict[str, Any] | None = None, execution_outputs: Dict[str, Any] | None = None) -> Dict[str, float]:
        """Evaluate cognitive load without changing any upstream decision."""
        context = self._dict(executive_context or {}, "executive_context")
        reasoning_payload = self._dict(reasoning or {}, "reasoning")
        execution = self._dict(execution_outputs or {}, "execution_outputs")
        conflict_count = len(self._nested_list(reasoning_payload, ["reasoning_trace", "conflicts_found"]))
        deviation_count = len(execution.get("execution_deviations", [])) if isinstance(execution.get("execution_deviations", []), list) else 0
        task_count = len(self._tasks_from_context(context))
        load = self._clamp(task_count * 5.0 + conflict_count * 12.0 + deviation_count * 8.0, 0.0, 100.0)
        return {"cognitive_load": round(load, 2), "decision_fatigue": round(self._clamp(load - 55.0, 0.0, 100.0), 2)}

    def evaluate_resource_balance(
        self,
        state: ResourceState | Dict[str, Any],
        attention: AttentionAllocation | Dict[str, Any],
        energy: EnergyProfile | Dict[str, Any],
        capacity: CapacityForecast | Dict[str, Any],
        conflicts: List[ResourceConflict | Dict[str, Any]] | None = None,
    ) -> ExecutiveResourceSummary:
        """Aggregate resource signals into bounded executive resource scores."""
        state_obj = state if isinstance(state, ResourceState) else ResourceState(**self._dict(state, "resource_state"))
        attention_obj = attention if isinstance(attention, AttentionAllocation) else AttentionAllocation(**self._dict(attention, "attention"))
        energy_obj = energy if isinstance(energy, EnergyProfile) else EnergyProfile(**self._dict(energy, "energy"))
        capacity_obj = capacity if isinstance(capacity, CapacityForecast) else CapacityForecast(**self._dict(capacity, "capacity"))
        conflict_objs = [self._conflict_obj(item) for item in (conflicts or [])]
        conflict_penalty = sum(item.impact_score for item in conflict_objs) / max(1, len(conflict_objs)) if conflict_objs else 0.0
        utilization = self._clamp(self.estimate_resource_utilization(state_obj), 0.0, 100.0)
        efficiency = self.estimate_resource_efficiency(state_obj, conflict_objs)
        resilience = self.estimate_resource_resilience(energy_obj, capacity_obj, conflict_objs)
        health = self._clamp(efficiency * 0.4 + resilience * 0.35 + (100.0 - conflict_penalty) * 0.25, 0.0, 100.0)
        overall = self._clamp(health * 0.35 + state_obj.strategic_capacity * 0.2 + energy_obj.energy_stability * 0.15 + attention_obj.deep_work_percent * 0.15 + state_obj.executive_reserve * 0.15, 0.0, 100.0)
        summary = f"Executive resource score is {round(overall, 2)} with {len(conflict_objs)} resource conflicts."
        result = ExecutiveResourceSummary(
            "executive-resource-summary",
            health,
            utilization,
            attention_obj.deep_work_percent,
            energy_obj.energy_stability,
            state_obj.strategic_capacity,
            energy_obj.recovery_readiness,
            state_obj.cognitive_load,
            capacity_obj.available_capacity,
            state_obj.executive_reserve,
            overall,
            summary,
            {"conflict_count": len(conflict_objs), "capacity_risk": capacity_obj.risk_level},
        )
        self._record_summary(result)
        return result

    def detect_resource_conflicts(self, state: ResourceState | Dict[str, Any], attention: AttentionAllocation | Dict[str, Any], energy: EnergyProfile | Dict[str, Any], capacity: CapacityForecast | Dict[str, Any]) -> List[ResourceConflict]:
        """Detect resource conflicts from validated resource state."""
        state_obj = state if isinstance(state, ResourceState) else ResourceState(**self._dict(state, "resource_state"))
        attention_obj = attention if isinstance(attention, AttentionAllocation) else AttentionAllocation(**self._dict(attention, "attention"))
        energy_obj = energy if isinstance(energy, EnergyProfile) else EnergyProfile(**self._dict(energy, "energy"))
        capacity_obj = capacity if isinstance(capacity, CapacityForecast) else CapacityForecast(**self._dict(capacity, "capacity"))
        conflicts: List[ResourceConflict] = []
        if capacity_obj.utilization > self.OVER_UTILIZATION_THRESHOLD:
            conflicts.append(self._conflict("over_allocation", "time", capacity_obj.utilization - 50.0, "Projected demand exceeds executive capacity.", "Delay low-value work"))
        if capacity_obj.utilization < self.UNDER_UTILIZATION_THRESHOLD:
            conflicts.append(self._conflict("under_utilization", "time", 35.0, "Available time appears under-used.", "Increase focus block"))
        if energy_obj.consumed_energy > self.HIGH_LOAD_THRESHOLD:
            conflicts.append(self._conflict("energy_overload", "energy", energy_obj.consumed_energy, "Energy consumption is too high for the current plan.", "Increase recovery"))
        if state_obj.risk_budget < self.LOW_CAPACITY_THRESHOLD:
            conflicts.append(self._conflict("risk_saturation", "risk_budget", 100.0 - state_obj.risk_budget, "Risk budget is nearly exhausted.", "Reduce cognitive load"))
        if state_obj.strategic_capacity < self.LOW_CAPACITY_THRESHOLD:
            conflicts.append(self._conflict("strategic_starvation", "strategic_capacity", 100.0 - state_obj.strategic_capacity, "Strategic work is being starved.", "Rebalance strategic effort"))
        if state_obj.recovery_capacity < self.LOW_CAPACITY_THRESHOLD:
            conflicts.append(self._conflict("recovery_deficit", "recovery_capacity", 100.0 - state_obj.recovery_capacity, "Recovery capacity is too low.", "Increase recovery"))
        conflicts.extend(self.detect_attention_fragmentation(attention_obj))
        conflicts.extend(self.detect_context_switch_cost(attention_obj))
        if state_obj.cognitive_load > self.HIGH_LOAD_THRESHOLD:
            conflicts.append(self._conflict("decision_fatigue", "cognitive_load", state_obj.cognitive_load, "Cognitive load is high enough to impair decisions.", "Reduce multitasking"))
        return self._dedupe_conflicts(conflicts)

    def detect_attention_fragmentation(self, attention: AttentionAllocation | Dict[str, Any]) -> List[ResourceConflict]:
        """Detect fragmented attention from validated attention allocation."""
        attention_obj = attention if isinstance(attention, AttentionAllocation) else AttentionAllocation(**self._dict(attention, "attention"))
        if attention_obj.fragmented_attention_percent <= self.ATTENTION_FRAGMENTATION_THRESHOLD:
            return []
        return [self._conflict("attention_fragmentation", "attention", attention_obj.fragmented_attention_percent, "Attention is fragmented across too many work modes.", "Protect deep work")]

    def detect_context_switch_cost(self, attention: AttentionAllocation | Dict[str, Any]) -> List[ResourceConflict]:
        """Detect excessive context switching from validated attention allocation."""
        attention_obj = attention if isinstance(attention, AttentionAllocation) else AttentionAllocation(**self._dict(attention, "attention"))
        if attention_obj.context_switches < self.CONTEXT_SWITCH_THRESHOLD:
            return []
        impact = min(100.0, attention_obj.context_switches * 10.0)
        return [self._conflict("context_switching", "attention", impact, "Context switching cost is elevated.", "Reduce multitasking")]

    def estimate_resource_efficiency(self, state: ResourceState | Dict[str, Any], conflicts: List[ResourceConflict | Dict[str, Any]] | None = None) -> float:
        """Estimate bounded resource efficiency from utilization and conflicts."""
        state_obj = state if isinstance(state, ResourceState) else ResourceState(**self._dict(state, "resource_state"))
        conflict_penalty = len(conflicts or []) * 6.0
        balance_bonus = 100.0 - abs(state_obj.consumed_time - state_obj.available_time)
        return round(self._clamp(balance_bonus - state_obj.cognitive_load * 0.25 - conflict_penalty, 0.0, 100.0), 2)

    def estimate_resource_utilization(self, state: ResourceState | Dict[str, Any]) -> float:
        """Estimate bounded aggregate utilization across time and energy."""
        state_obj = state if isinstance(state, ResourceState) else ResourceState(**self._dict(state, "resource_state"))
        time_utilization = self._utilization(state_obj.consumed_time, max(1.0, state_obj.available_time))
        energy_utilization = self._utilization(state_obj.consumed_energy, max(1.0, state_obj.available_energy))
        return round(self._clamp((time_utilization + energy_utilization) / 2.0, 0.0, 100.0), 2)

    def estimate_resource_resilience(self, energy: EnergyProfile | Dict[str, Any], capacity: CapacityForecast | Dict[str, Any], conflicts: List[ResourceConflict | Dict[str, Any]] | None = None) -> float:
        """Estimate ability to absorb resource pressure."""
        energy_obj = energy if isinstance(energy, EnergyProfile) else EnergyProfile(**self._dict(energy, "energy"))
        capacity_obj = capacity if isinstance(capacity, CapacityForecast) else CapacityForecast(**self._dict(capacity, "capacity"))
        conflict_penalty = sum(self._conflict_obj(item).impact_score for item in (conflicts or [])) * 0.08
        return round(self._clamp(energy_obj.recovery_readiness * 0.45 + energy_obj.energy_stability * 0.3 + capacity_obj.confidence * 0.25 - conflict_penalty, 0.0, 100.0), 2)

    def generate_resource_recommendations(self, conflicts: List[ResourceConflict | Dict[str, Any]], summary: ExecutiveResourceSummary | Dict[str, Any]) -> List[ResourceRecommendation]:
        """Generate deterministic recommendation-only resource actions."""
        summary_obj = summary if isinstance(summary, ExecutiveResourceSummary) else ExecutiveResourceSummary(**self._dict(summary, "summary"))
        recommendations = [
            ResourceRecommendation(
                f"resource-recommendation-{self._slug(self._conflict_obj(conflict).recommended_action)}",
                self._conflict_obj(conflict).recommended_action,
                1 if self._conflict_obj(conflict).severity in {"high", "critical"} else 3,
                min(100.0, 45.0 + self._conflict_obj(conflict).impact_score * 0.4),
                self._conflict_obj(conflict).description,
                [self._conflict_obj(conflict).affected_resource],
                {"conflict_id": self._conflict_obj(conflict).conflict_id},
            )
            for conflict in conflicts
        ]
        if not recommendations:
            recommendations.append(ResourceRecommendation("resource-recommendation-protect-current-balance", "Protect deep work", 4, max(40.0, summary_obj.overall_resource_score), "Resource allocation is currently balanced.", ["attention"]))
        return self._dedupe_recommendations(recommendations)

    def generate_resource_dashboard(self, state: ResourceState | Dict[str, Any], summary: ExecutiveResourceSummary | Dict[str, Any], conflicts: List[ResourceConflict | Dict[str, Any]], recommendations: List[ResourceRecommendation | Dict[str, Any]], attention: AttentionAllocation | Dict[str, Any], energy: EnergyProfile | Dict[str, Any], capacity: CapacityForecast | Dict[str, Any]) -> Dict[str, Any]:
        """Generate validated executive resource dashboard."""
        state_obj = state if isinstance(state, ResourceState) else ResourceState(**self._dict(state, "resource_state"))
        summary_obj = summary if isinstance(summary, ExecutiveResourceSummary) else ExecutiveResourceSummary(**self._dict(summary, "summary"))
        attention_obj = attention if isinstance(attention, AttentionAllocation) else AttentionAllocation(**self._dict(attention, "attention"))
        energy_obj = energy if isinstance(energy, EnergyProfile) else EnergyProfile(**self._dict(energy, "energy"))
        capacity_obj = capacity if isinstance(capacity, CapacityForecast) else CapacityForecast(**self._dict(capacity, "capacity"))
        dashboard = {
            "current_resource_state": asdict(state_obj),
            "resource_health": summary_obj.resource_health,
            "resource_conflicts": [asdict(self._conflict_obj(item)) for item in conflicts],
            "resource_allocation": {"time": state_obj.consumed_time, "energy": state_obj.consumed_energy, "strategic": state_obj.strategic_capacity},
            "executive_reserve": state_obj.executive_reserve,
            "attention_distribution": asdict(attention_obj),
            "energy_distribution": asdict(energy_obj),
            "capacity_forecast": asdict(capacity_obj),
            "recovery_status": "ready" if summary_obj.recovery_readiness >= 60.0 else "constrained",
            "executive_summary": summary_obj.executive_summary,
            "recommendations": [asdict(self._recommendation_obj(item)) for item in recommendations],
        }
        self._validate_output(dashboard, "resource_dashboard")
        return dashboard

    def generate_resource_summary(
        self,
        *,
        executive_context: Dict[str, Any] | None = None,
        executive_reasoning: Dict[str, Any] | None = None,
        executive_experience: Dict[str, Any] | None = None,
        execution_outputs: Dict[str, Any] | None = None,
        adaptive_life: Dict[str, Any] | None = None,
        behavior_learning: Dict[str, Any] | None = None,
        context_awareness: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Return all Executive Brain resource-intelligence outputs."""
        context = self._merge_context(executive_context or {}, adaptive_life or {}, behavior_learning or {}, context_awareness or {})
        execution = self._dict(execution_outputs or {}, "execution_outputs")
        reasoning = self._dict(executive_reasoning or {}, "executive_reasoning")
        experience = self._dict(executive_experience or {}, "executive_experience")
        time_allocation = self.evaluate_time_budget(context, execution)
        energy = self.evaluate_energy_budget(context, behavior_learning or {})
        attention = self.evaluate_attention_budget(context, behavior_learning or {})
        capacity = self.evaluate_capacity_budget(context, execution)
        cognitive = self.evaluate_cognitive_load(context, reasoning, execution)
        state = self._resource_state(time_allocation, energy, attention, capacity, cognitive, reasoning, execution, experience)
        conflicts = self.detect_resource_conflicts(state, attention, energy, capacity)
        summary = self.evaluate_resource_balance(state, attention, energy, capacity, conflicts)
        recommendations = self.generate_resource_recommendations(conflicts, summary)
        dashboard = self.generate_resource_dashboard(state, summary, conflicts, recommendations, attention, energy, capacity)
        outputs = {
            "resource_state": asdict(state),
            "resource_health": {
                "resource_health": summary.resource_health,
                "attention_quality": summary.attention_quality,
                "energy_stability": summary.energy_stability,
                "strategic_capacity": summary.strategic_capacity,
                "recovery_readiness": summary.recovery_readiness,
                "cognitive_load": summary.cognitive_load,
                "execution_capacity": summary.execution_capacity,
                "executive_reserve": summary.executive_reserve,
                "overall_resource_score": summary.overall_resource_score,
            },
            "resource_dashboard": dashboard,
            "resource_conflicts": [asdict(item) for item in conflicts],
            "resource_recommendations": [asdict(item) for item in recommendations],
            "resource_summary": asdict(summary),
            "resource_forecast": asdict(capacity),
            "resource_efficiency": {"efficiency": self.estimate_resource_efficiency(state, conflicts)},
            "resource_utilization": {"utilization": self.estimate_resource_utilization(state)},
            "executive_resource_score": {"score": summary.overall_resource_score},
        }
        self._validate_resource_outputs(outputs)
        return outputs

    def _resource_state(self, time_allocation: ResourceAllocation, energy: EnergyProfile, attention: AttentionAllocation, capacity: CapacityForecast, cognitive: Dict[str, float], reasoning: Dict[str, Any], execution: Dict[str, Any], experience: Dict[str, Any]) -> ResourceState:
        confidence = self._score(reasoning.get("confidence", self._nested_score(execution, ["execution_confidence", "confidence"], 50.0)), 0.0, 100.0)
        reserve = self._clamp((energy.recovery_readiness + capacity.available_capacity + confidence) / 3.0 - cognitive["cognitive_load"] * 0.2, 0.0, 100.0)
        risk_budget = self._clamp(100.0 - self._nested_score(execution, ["execution_state", "execution_risk"], 20.0), 0.0, 100.0)
        strategic_capacity = self._clamp(confidence * 0.4 + capacity.available_capacity * 0.35 + attention.deep_work_percent * 0.25, 0.0, 100.0)
        return ResourceState(
            "executive-resource-state",
            time_allocation.allocated_percent,
            time_allocation.consumed_percent,
            energy.available_energy,
            energy.consumed_energy,
            cognitive["cognitive_load"],
            attention.deep_work_percent,
            strategic_capacity,
            self._nested_score(execution, ["execution_health", "execution_health"], 65.0),
            energy.recovery_readiness,
            risk_budget,
            self._clamp(100.0 - cognitive["decision_fatigue"], 0.0, 100.0),
            confidence,
            reserve,
            {"experience_decision_count": experience.get("decision_count", 0)},
        )

    def _record_summary(self, summary: ExecutiveResourceSummary) -> None:
        self._history.append(summary)
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history :]

    def _merge_context(self, context: Dict[str, Any], adaptive: Dict[str, Any], learning: Dict[str, Any], awareness: Dict[str, Any]) -> Dict[str, Any]:
        merged = self._dict(context, "executive_context")
        if adaptive:
            merged["adaptive_life"] = self._dict(adaptive, "adaptive_life")
        if learning:
            merged["behavior_learning"] = self._dict(learning, "behavior_learning")
        if awareness:
            merged["context_awareness"] = self._dict(awareness, "context_awareness")
        return merged

    def _tasks_from_context(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        payload = context.get("context", {}) if isinstance(context.get("context"), dict) else {}
        tasks = payload.get("current_tasks", [])
        if not isinstance(tasks, list):
            raise ValueError("current_tasks must be a list.")
        if any(not isinstance(task, dict) for task in tasks):
            raise ValueError("current_tasks entries must be dictionaries.")
        self._validate_output(tasks, "current_tasks")
        return [dict(task) for task in tasks]

    def _task_time_percent(self, tasks: List[Dict[str, Any]]) -> float:
        hours = sum(self._duration(task) for task in tasks)
        return round(self._clamp((hours / 8.0) * 100.0, 0.0, 100.0), 2)

    def _duration(self, task: Dict[str, Any]) -> float:
        value = task.get("estimated_duration", task.get("duration", 1.0))
        unit = task.get("estimated_duration_unit")
        if unit is not None:
            source = task.get("estimated_duration_source")
            value = normalize_duration(value, unit, source).normalized_hours
        return self._clamp(self._score(value, 0.0, 24.0), 0.0, 24.0)

    def _conflict(self, conflict_type: str, resource: str, impact: float, description: str, action: str) -> ResourceConflict:
        impact_score = self._clamp(impact, 0.0, 100.0)
        return ResourceConflict(f"resource-conflict-{conflict_type}-{resource}", conflict_type, self._severity_from_score(impact_score), resource, impact_score, description, action)

    def _dedupe_conflicts(self, conflicts: List[ResourceConflict]) -> List[ResourceConflict]:
        seen = set()
        result = []
        for conflict in conflicts:
            key = (conflict.conflict_type, conflict.affected_resource)
            if key not in seen:
                seen.add(key)
                result.append(conflict)
        return sorted(result, key=lambda item: (-item.impact_score, item.conflict_type, item.affected_resource))

    def _dedupe_recommendations(self, recommendations: List[ResourceRecommendation]) -> List[ResourceRecommendation]:
        seen = set()
        result = []
        for recommendation in recommendations:
            if recommendation.recommendation_id not in seen:
                seen.add(recommendation.recommendation_id)
                result.append(recommendation)
        return sorted(result, key=lambda item: (item.priority, -item.expected_benefit, item.action))

    def _validate_resource_outputs(self, outputs: Dict[str, Any]) -> None:
        expected = {
            "resource_state",
            "resource_health",
            "resource_dashboard",
            "resource_conflicts",
            "resource_recommendations",
            "resource_summary",
            "resource_forecast",
            "resource_efficiency",
            "resource_utilization",
            "executive_resource_score",
        }
        if set(outputs) != expected:
            raise ValueError("resource outputs have invalid fields.")
        for key in expected - {"resource_conflicts", "resource_recommendations"}:
            if not isinstance(outputs[key], dict):
                raise ValueError(f"{key} must be a dictionary.")
        for key in ("resource_conflicts", "resource_recommendations"):
            if not isinstance(outputs[key], list):
                raise ValueError(f"{key} must be a list.")
        self._validate_output(outputs, "resource outputs")

    def _validate_output(self, value: Any, field_name: str) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                self._validate_output(nested, field_name)
            return
        if isinstance(value, list):
            for nested in value:
                self._validate_output(nested, field_name)
            return
        if isinstance(value, bool) or value is None or isinstance(value, str):
            return
        if isinstance(value, (int, float)) and not math.isfinite(float(value)):
            raise ValueError(f"{field_name} contains non-finite numeric value.")

    def _nested_dict(self, payload: Dict[str, Any], path: List[str]) -> Dict[str, Any]:
        value: Any = payload
        for key in path:
            if not isinstance(value, dict):
                return {}
            value = value.get(key, {})
        return value if isinstance(value, dict) else {}

    def _nested_list(self, payload: Dict[str, Any], path: List[str]) -> List[Any]:
        value: Any = payload
        for key in path:
            if not isinstance(value, dict):
                return []
            value = value.get(key, [])
        return value if isinstance(value, list) else []

    def _nested_score(self, payload: Dict[str, Any], path: List[str], default: float) -> float:
        value: Any = payload
        for key in path:
            if not isinstance(value, dict):
                return default
            value = value.get(key, default)
        return self._score(value, 0.0, 100.0)

    def _score(self, value: Any, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError("resource numeric inputs must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError("resource numeric inputs must be finite.")
        if number < minimum or number > maximum:
            raise ValueError("resource numeric inputs are out of range.")
        return number

    def _utilization(self, consumed: float, available: float) -> float:
        if available <= 0.0:
            raise ValueError("available resource must be positive.")
        return round(self._clamp((consumed / available) * 100.0, 0.0, 200.0), 2)

    def _severity_from_score(self, score: float) -> str:
        if score >= 75.0:
            return "critical"
        if score >= 50.0:
            return "high"
        if score >= 25.0:
            return "medium"
        return "low"

    def _conflict_obj(self, value: ResourceConflict | Dict[str, Any]) -> ResourceConflict:
        return value if isinstance(value, ResourceConflict) else ResourceConflict(**self._dict(value, "conflict"))

    def _recommendation_obj(self, value: ResourceRecommendation | Dict[str, Any]) -> ResourceRecommendation:
        return value if isinstance(value, ResourceRecommendation) else ResourceRecommendation(**self._dict(value, "recommendation"))

    def _dict(self, value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        self._validate_output(value, field_name)
        return dict(value)

    def _slug(self, value: str) -> str:
        return "-".join(part for part in value.lower().split() if part)

    def _clamp(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, round(value, 4)))
