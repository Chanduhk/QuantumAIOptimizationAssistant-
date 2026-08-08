from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from backend.app.domain.executive_execution_model import (
    ExecutionCheckpoint,
    ExecutionDeviation,
    ExecutionTimeline,
    ExecutiveAlert,
    PlanExecutionState,
    RecoveryRecommendation,
)


class ExecutiveExecutionEngine:
    """Supervise execution against a previously selected executive strategy.

    The engine does not plan, schedule, optimize, predict, learn user behavior, or
    reason about strategy selection. It only monitors execution alignment and
    returns recommendation-only recovery guidance.
    """

    DEFAULT_MAX_HISTORY = 500
    BASE_TIMESTAMP = datetime(2026, 1, 1, 0, 0, 0)
    LATE_PROGRESS_GAP = 15.0
    SEVERE_PROGRESS_GAP = 35.0
    CONFIDENCE_DROP_THRESHOLD = 15.0
    CAPACITY_OVERLOAD_THRESHOLD = 115.0
    HEALTH_WARNING_THRESHOLD = 65.0
    HEALTH_CRITICAL_THRESHOLD = 40.0

    def __init__(self, max_history: int = DEFAULT_MAX_HISTORY) -> None:
        if not isinstance(max_history, int) or isinstance(max_history, bool) or max_history <= 0:
            raise ValueError("max_history must be a positive integer.")
        self.max_history = max_history
        self._checkpoints: List[ExecutionCheckpoint] = []
        self._checkpoint_ids: set[str] = set()

    def record_execution_checkpoint(
        self,
        checkpoint: ExecutionCheckpoint | Dict[str, Any] | None = None,
        *,
        checkpoint_id: str | None = None,
        timestamp: datetime | None = None,
        selected_strategy: str | None = None,
        planned_progress: float = 0.0,
        actual_progress: float = 0.0,
        confidence: float = 50.0,
        status: str = "not_started",
        metadata: Dict[str, Any] | None = None,
    ) -> ExecutionCheckpoint:
        """Record a validated execution checkpoint in bounded memory."""
        if checkpoint is not None:
            checkpoint_obj = checkpoint if isinstance(checkpoint, ExecutionCheckpoint) else ExecutionCheckpoint(**self._dict(checkpoint, "checkpoint"))
        else:
            checkpoint_obj = ExecutionCheckpoint(
                checkpoint_id=checkpoint_id or self.generate_next_checkpoint(),
                timestamp=timestamp or self._next_timestamp(),
                selected_strategy=selected_strategy or "Unknown executive strategy",
                planned_progress=planned_progress,
                actual_progress=actual_progress,
                confidence=confidence,
                status=status,
                metadata=metadata or {},
            )
        if checkpoint_obj.checkpoint_id in self._checkpoint_ids:
            raise ValueError("checkpoint_id must be unique.")
        self._checkpoints.append(checkpoint_obj)
        self._checkpoint_ids.add(checkpoint_obj.checkpoint_id)
        if len(self._checkpoints) > self.max_history:
            removed = self._checkpoints.pop(0)
            self._checkpoint_ids.discard(removed.checkpoint_id)
        return checkpoint_obj

    def track_execution_progress(
        self,
        *,
        selected_strategy: str,
        checkpoint: ExecutionCheckpoint | Dict[str, Any] | None = None,
        executive_context: Dict[str, Any] | None = None,
        executive_reasoning: Dict[str, Any] | None = None,
        risk_summary: Dict[str, Any] | None = None,
        experience_summary: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Record progress and return execution supervision outputs."""
        if checkpoint is None:
            checkpoint = self._checkpoint_from_inputs(
                selected_strategy=selected_strategy,
                executive_context=executive_context or {},
                executive_reasoning=executive_reasoning or {},
                risk_summary=risk_summary or {},
                experience_summary=experience_summary or {},
            )
        checkpoint_obj = self.record_execution_checkpoint(checkpoint)
        deviations = self.detect_execution_deviation(
            checkpoint_obj,
            executive_context=executive_context or {},
            executive_reasoning=executive_reasoning or {},
            risk_summary=risk_summary or {},
        )
        state = self.estimate_execution_health(checkpoint_obj, deviations)
        recovery = self.generate_recovery_plan(deviations, state)
        alerts = self.generate_execution_alerts(deviations, state)
        timeline = self.execution_timeline(deviations, alerts)
        dashboard = self.generate_executive_dashboard(state, deviations, alerts, recovery, timeline)
        summary = self.generate_execution_summary(state, deviations, recovery)
        return {
            "execution_state": asdict(state),
            "execution_health": {
                "execution_health": state.execution_health,
                "execution_confidence": state.execution_confidence,
                "execution_stability": state.execution_stability,
                "execution_momentum": state.execution_momentum,
                "execution_risk": state.execution_risk,
                "schedule_reliability": state.schedule_reliability,
                "goal_progress": state.goal_progress,
                "recovery_readiness": state.recovery_readiness,
            },
            "execution_dashboard": dashboard,
            "execution_alerts": [asdict(alert) for alert in alerts],
            "execution_deviations": [asdict(deviation) for deviation in deviations],
            "execution_recovery": [asdict(item) for item in recovery],
            "execution_summary": {"summary": summary, "explanation": self.generate_execution_explanation(state, deviations)},
            "execution_timeline": asdict(timeline),
            "execution_confidence": {"confidence": state.execution_confidence},
            "next_execution_checkpoint": self.generate_next_checkpoint_payload(state),
        }

    def detect_execution_deviation(
        self,
        checkpoint: ExecutionCheckpoint | Dict[str, Any],
        *,
        executive_context: Dict[str, Any] | None = None,
        executive_reasoning: Dict[str, Any] | None = None,
        risk_summary: Dict[str, Any] | None = None,
    ) -> List[ExecutionDeviation]:
        """Detect execution deviations from the selected strategy."""
        checkpoint_obj = checkpoint if isinstance(checkpoint, ExecutionCheckpoint) else ExecutionCheckpoint(**self._dict(checkpoint, "checkpoint"))
        context = executive_context or {}
        reasoning = executive_reasoning or {}
        risks = risk_summary or {}
        deviations: List[ExecutionDeviation] = []
        deviations.extend(self.detect_schedule_slippage(checkpoint_obj))
        deviations.extend(self.detect_goal_slippage(checkpoint_obj, context))
        deviations.extend(self.detect_dependency_blockage(context))
        deviations.extend(self.detect_capacity_overload(context))
        deviations.extend(self.detect_strategy_drift(checkpoint_obj, reasoning))
        deviations.extend(self._detect_confidence_degradation(checkpoint_obj))
        deviations.extend(self._detect_context_mismatch(context))
        deviations.extend(self._detect_priority_inversion(context))
        if risks.get("executive_risk_level") in {"high", "critical"} or risks.get("risk_level") in {"high", "critical"}:
            deviations.append(
                self._deviation(
                    "confidence_degradation",
                    "high",
                    70.0,
                    "Executive risk is elevated during execution.",
                    "Reduce workload and review risk drivers before continuing.",
                    checkpoint_obj.timestamp,
                    self._affected_goals(context),
                    {"risk_summary": risks},
                )
            )
        return self._dedupe_deviations(deviations)

    def detect_schedule_slippage(self, checkpoint: ExecutionCheckpoint | Dict[str, Any]) -> List[ExecutionDeviation]:
        """Detect schedule drift from planned progress."""
        checkpoint_obj = checkpoint if isinstance(checkpoint, ExecutionCheckpoint) else ExecutionCheckpoint(**self._dict(checkpoint, "checkpoint"))
        gap = checkpoint_obj.planned_progress - checkpoint_obj.actual_progress
        if gap < self.LATE_PROGRESS_GAP:
            return []
        severity_score = min(100.0, gap * 2.0)
        return [
            self._deviation(
                "schedule_drift",
                self._severity_from_score(severity_score),
                severity_score,
                f"Execution is {round(gap, 2)} percentage points behind planned progress.",
                "Reorder tasks or increase protected focus time.",
                checkpoint_obj.timestamp,
                self._metadata_goals(checkpoint_obj.metadata),
                {"progress_gap": round(gap, 2)},
            )
        ]

    def detect_goal_slippage(self, checkpoint: ExecutionCheckpoint | Dict[str, Any], executive_context: Dict[str, Any] | None = None) -> List[ExecutionDeviation]:
        """Detect goal progress slippage using checkpoint and context metadata."""
        checkpoint_obj = checkpoint if isinstance(checkpoint, ExecutionCheckpoint) else ExecutionCheckpoint(**self._dict(checkpoint, "checkpoint"))
        goal_progress = self._bounded((executive_context or {}).get("goal_progress", checkpoint_obj.actual_progress), "goal_progress", 0.0, 100.0)
        planned = checkpoint_obj.planned_progress
        if planned - goal_progress < self.LATE_PROGRESS_GAP:
            return []
        return [
            self._deviation(
                "goal_drift",
                "medium",
                min(100.0, (planned - goal_progress) * 1.8),
                "Goal progress is lagging behind the selected executive strategy.",
                "Protect strategic work and defer lower-alignment tasks.",
                checkpoint_obj.timestamp,
                self._affected_goals(executive_context or {}),
                {"goal_progress": goal_progress, "planned_progress": planned},
            )
        ]

    def detect_dependency_blockage(self, executive_context: Dict[str, Any] | None = None) -> List[ExecutionDeviation]:
        """Detect blocked dependencies from executive objective/context state."""
        context = executive_context or {}
        blocked = context.get("blocked_tasks", [])
        if not isinstance(blocked, list) or not blocked:
            return []
        return [
            self._deviation(
                "blocked_dependency",
                "critical",
                min(100.0, 70.0 + len(blocked) * 5.0),
                "Execution is blocked by unresolved task dependencies.",
                "Recover dependency chain before continuing dependent work.",
                self._current_timestamp(),
                self._affected_goals(context),
                {"blocked_count": len(blocked)},
            )
        ]

    def detect_capacity_overload(self, executive_context: Dict[str, Any] | None = None) -> List[ExecutionDeviation]:
        """Detect capacity overload from available workload signals."""
        context = executive_context or {}
        utilization = self._bounded(context.get("capacity_utilization", 0.0), "capacity_utilization", 0.0, 500.0)
        if utilization <= self.CAPACITY_OVERLOAD_THRESHOLD:
            return []
        return [
            self._deviation(
                "capacity_overload",
                self._severity_from_score(min(100.0, utilization - 50.0)),
                min(100.0, utilization - 50.0),
                "Execution capacity is overloaded relative to the selected strategy.",
                "Reduce workload or delay non-critical execution items.",
                self._current_timestamp(),
                self._affected_goals(context),
                {"capacity_utilization": utilization},
            )
        ]

    def detect_strategy_drift(
        self,
        checkpoint: ExecutionCheckpoint | Dict[str, Any],
        executive_reasoning: Dict[str, Any] | None = None,
    ) -> List[ExecutionDeviation]:
        """Detect whether observed execution no longer matches the selected strategy."""
        checkpoint_obj = checkpoint if isinstance(checkpoint, ExecutionCheckpoint) else ExecutionCheckpoint(**self._dict(checkpoint, "checkpoint"))
        expected = str((executive_reasoning or {}).get("recommended_action", checkpoint_obj.selected_strategy)).strip()
        if not expected or expected == checkpoint_obj.selected_strategy:
            return []
        return [
            self._deviation(
                "goal_drift",
                "medium",
                55.0,
                "Observed execution strategy differs from the executive recommendation.",
                "Re-align execution with the selected executive strategy.",
                checkpoint_obj.timestamp,
                self._metadata_goals(checkpoint_obj.metadata),
                {"expected_strategy": expected, "observed_strategy": checkpoint_obj.selected_strategy},
            )
        ]

    def estimate_completion_probability(self, checkpoint: ExecutionCheckpoint | Dict[str, Any], deviations: List[ExecutionDeviation | Dict[str, Any]] | None = None) -> float:
        """Estimate bounded completion probability from progress and deviations."""
        checkpoint_obj = checkpoint if isinstance(checkpoint, ExecutionCheckpoint) else ExecutionCheckpoint(**self._dict(checkpoint, "checkpoint"))
        deviation_penalty = sum(self._deviation_obj(item).severity_score for item in (deviations or [])) * 0.12
        progress_bonus = checkpoint_obj.actual_progress * 0.55
        confidence_bonus = checkpoint_obj.confidence * 0.35
        return round(self._clamp(progress_bonus + confidence_bonus - deviation_penalty, 0.0, 100.0), 2)

    def estimate_schedule_confidence(self, checkpoint: ExecutionCheckpoint | Dict[str, Any], deviations: List[ExecutionDeviation | Dict[str, Any]] | None = None) -> float:
        """Estimate bounded schedule confidence."""
        checkpoint_obj = checkpoint if isinstance(checkpoint, ExecutionCheckpoint) else ExecutionCheckpoint(**self._dict(checkpoint, "checkpoint"))
        gap = max(0.0, checkpoint_obj.planned_progress - checkpoint_obj.actual_progress)
        deviation_penalty = len(deviations or []) * 5.0
        return round(self._clamp(100.0 - gap * 1.5 - deviation_penalty, 0.0, 100.0), 2)

    def estimate_execution_health(
        self,
        checkpoint: ExecutionCheckpoint | Dict[str, Any],
        deviations: List[ExecutionDeviation | Dict[str, Any]] | None = None,
    ) -> PlanExecutionState:
        """Compute deterministic execution health scores."""
        checkpoint_obj = checkpoint if isinstance(checkpoint, ExecutionCheckpoint) else ExecutionCheckpoint(**self._dict(checkpoint, "checkpoint"))
        deviation_objs = [self._deviation_obj(item) for item in (deviations or [])]
        schedule_reliability = self.estimate_schedule_confidence(checkpoint_obj, deviation_objs)
        completion_probability = self.estimate_completion_probability(checkpoint_obj, deviation_objs)
        execution_risk = round(self._clamp(sum(item.severity_score for item in deviation_objs) / max(1, len(deviation_objs)), 0.0, 100.0), 2) if deviation_objs else 10.0
        stability = round(self._clamp(100.0 - len(deviation_objs) * 12.0 - execution_risk * 0.25, 0.0, 100.0), 2)
        momentum = round(self._clamp(checkpoint_obj.actual_progress - max(0.0, checkpoint_obj.planned_progress - checkpoint_obj.actual_progress) + 50.0, 0.0, 100.0), 2)
        recovery_readiness = round(self._clamp(100.0 - execution_risk * 0.55 + checkpoint_obj.confidence * 0.2, 0.0, 100.0), 2)
        health = round(
            self._clamp(
                completion_probability * 0.3
                + schedule_reliability * 0.2
                + stability * 0.2
                + momentum * 0.15
                + recovery_readiness * 0.15,
                0.0,
                100.0,
            ),
            2,
        )
        status = "completed" if checkpoint_obj.actual_progress >= 100.0 else "blocked" if any(item.deviation_type == "blocked_dependency" for item in deviation_objs) else "at_risk" if health < self.HEALTH_WARNING_THRESHOLD else "on_track"
        return PlanExecutionState(
            state_id=f"execution-state-{checkpoint_obj.checkpoint_id}",
            timestamp=checkpoint_obj.timestamp,
            selected_strategy=checkpoint_obj.selected_strategy,
            progress=checkpoint_obj.actual_progress,
            execution_health=health,
            execution_confidence=completion_probability,
            execution_stability=stability,
            execution_momentum=momentum,
            execution_risk=execution_risk,
            schedule_reliability=schedule_reliability,
            goal_progress=checkpoint_obj.actual_progress,
            recovery_readiness=recovery_readiness,
            status=status,
            metadata={"checkpoint_id": checkpoint_obj.checkpoint_id, "deviation_count": len(deviation_objs)},
        )

    def generate_recovery_plan(
        self,
        deviations: List[ExecutionDeviation | Dict[str, Any]],
        state: PlanExecutionState | Dict[str, Any],
    ) -> List[RecoveryRecommendation]:
        """Generate recommendation-only recovery actions."""
        state_obj = state if isinstance(state, PlanExecutionState) else PlanExecutionState(**self._dict(state, "state"))
        deviation_objs = [self._deviation_obj(item) for item in deviations]
        recommendations: List[RecoveryRecommendation] = []
        if not deviation_objs:
            recommendations.append(self._recovery("protect strategic work", 4, 55.0, "Execution is on track; protect the current strategy.", state_obj.timestamp, {}))
        for deviation in deviation_objs:
            action = self._recovery_action(deviation.deviation_type)
            recommendations.append(
                self._recovery(
                    action,
                    1 if deviation.severity in {"critical", "high"} else 3,
                    min(100.0, 45.0 + deviation.severity_score * 0.4),
                    deviation.recommended_recovery,
                    deviation.detected_at,
                    {"deviation_id": deviation.deviation_id, "deviation_type": deviation.deviation_type},
                )
            )
        return self._dedupe_recoveries(recommendations)

    def generate_execution_alerts(
        self,
        deviations: List[ExecutionDeviation | Dict[str, Any]],
        state: PlanExecutionState | Dict[str, Any],
    ) -> List[ExecutiveAlert]:
        """Generate executive alerts from deviations and health state."""
        state_obj = state if isinstance(state, PlanExecutionState) else PlanExecutionState(**self._dict(state, "state"))
        alerts: List[ExecutiveAlert] = []
        for index, deviation in enumerate([self._deviation_obj(item) for item in deviations], start=1):
            if deviation.severity in {"medium", "high", "critical"}:
                alerts.append(
                    ExecutiveAlert(
                        alert_id=f"execution-alert-{deviation.deviation_id}-{index}",
                        alert_type=deviation.deviation_type,
                        severity=deviation.severity,
                        message=deviation.description,
                        timestamp=deviation.detected_at,
                        recommended_action=deviation.recommended_recovery,
                        metadata={"severity_score": deviation.severity_score},
                    )
                )
        if state_obj.execution_health < self.HEALTH_CRITICAL_THRESHOLD:
            alerts.append(
                ExecutiveAlert(
                    alert_id=f"execution-alert-health-{state_obj.state_id}",
                    alert_type="execution_health",
                    severity="critical",
                    message="Execution health is critically low.",
                    timestamp=state_obj.timestamp,
                    recommended_action="Pause and rebalance execution before continuing.",
                    metadata={"execution_health": state_obj.execution_health},
                )
            )
        return alerts

    def generate_executive_dashboard(
        self,
        state: PlanExecutionState | Dict[str, Any],
        deviations: List[ExecutionDeviation | Dict[str, Any]],
        alerts: List[ExecutiveAlert | Dict[str, Any]],
        recovery: List[RecoveryRecommendation | Dict[str, Any]],
        timeline: ExecutionTimeline | Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate deterministic execution dashboard output."""
        state_obj = state if isinstance(state, PlanExecutionState) else PlanExecutionState(**self._dict(state, "state"))
        deviation_count = len(deviations)
        alert_count = len(alerts)
        return {
            "current_execution_status": state_obj.status,
            "overall_health": state_obj.execution_health,
            "current_risks": [self._deviation_obj(item).description for item in deviations],
            "current_opportunities": self._execution_opportunities(state_obj),
            "current_deviations": deviation_count,
            "recovery_actions": [self._recovery_obj(item).action for item in recovery],
            "next_executive_review": self.generate_next_checkpoint_payload(state_obj),
            "confidence_trend": self._confidence_trend(),
            "execution_momentum": state_obj.execution_momentum,
            "executive_summary": self.generate_execution_summary(state_obj, [self._deviation_obj(item) for item in deviations], [self._recovery_obj(item) for item in recovery]),
            "alert_count": alert_count,
            "timeline_id": timeline.timeline_id if isinstance(timeline, ExecutionTimeline) else timeline.get("timeline_id"),
        }

    def generate_execution_summary(
        self,
        state: PlanExecutionState | Dict[str, Any],
        deviations: List[ExecutionDeviation | Dict[str, Any]],
        recovery: List[RecoveryRecommendation | Dict[str, Any]],
    ) -> str:
        """Return a concise execution supervision summary."""
        state_obj = state if isinstance(state, PlanExecutionState) else PlanExecutionState(**self._dict(state, "state"))
        summary = (
            f"Execution is {state_obj.status} with health {state_obj.execution_health} "
            f"and {len(deviations)} deviations; {len(recovery)} recovery actions are recommended."
        )
        if not summary.strip():
            raise ValueError("execution summary must be non-empty.")
        return summary

    def generate_next_checkpoint(self) -> str:
        """Return a deterministic next checkpoint identifier."""
        return f"execution-checkpoint-{len(self._checkpoints) + 1}"

    def generate_next_checkpoint_payload(self, state: PlanExecutionState | Dict[str, Any]) -> Dict[str, Any]:
        """Return next checkpoint recommendation payload."""
        state_obj = state if isinstance(state, PlanExecutionState) else PlanExecutionState(**self._dict(state, "state"))
        return {
            "checkpoint_id": self.generate_next_checkpoint(),
            "recommended_review_after_minutes": 30 if state_obj.status in {"at_risk", "blocked"} else 60,
            "focus": "recovery" if state_obj.status in {"at_risk", "blocked"} else "progress verification",
        }

    def generate_execution_explanation(
        self,
        state: PlanExecutionState | Dict[str, Any],
        deviations: List[ExecutionDeviation | Dict[str, Any]],
    ) -> str:
        """Explain why the current execution state was detected."""
        state_obj = state if isinstance(state, PlanExecutionState) else PlanExecutionState(**self._dict(state, "state"))
        if not deviations:
            return "Execution remains aligned with the selected executive strategy."
        return (
            f"Execution health is {state_obj.execution_health} because "
            f"{len(deviations)} deviations were detected against the selected strategy."
        )

    def execution_timeline(
        self,
        deviations: List[ExecutionDeviation | Dict[str, Any]] | None = None,
        alerts: List[ExecutiveAlert | Dict[str, Any]] | None = None,
    ) -> ExecutionTimeline:
        """Return immutable timeline over current bounded history."""
        created_at = self._checkpoints[-1].timestamp if self._checkpoints else self.BASE_TIMESTAMP
        return ExecutionTimeline(
            timeline_id=f"execution-timeline-{len(self._checkpoints)}",
            checkpoints=list(self._checkpoints),
            deviations=deviations or [],
            alerts=alerts or [],
            created_at=created_at,
        )

    def _checkpoint_from_inputs(
        self,
        *,
        selected_strategy: str,
        executive_context: Dict[str, Any],
        executive_reasoning: Dict[str, Any],
        risk_summary: Dict[str, Any],
        experience_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        context_payload = executive_context.get("context", {}) if isinstance(executive_context.get("context"), dict) else {}
        task_count = len(context_payload.get("current_tasks", [])) if isinstance(context_payload.get("current_tasks", []), list) else 0
        confidence = self._bounded(executive_reasoning.get("confidence", risk_summary.get("executive_confidence", 45.0)), "confidence", 0.0, 100.0)
        planned_progress = 100.0 if task_count == 0 else min(100.0, 20.0 + task_count * 10.0)
        actual_progress = self._bounded(executive_context.get("actual_progress", 0.0), "actual_progress", 0.0, 100.0)
        status = "completed" if actual_progress >= 100.0 else "not_started" if actual_progress == 0.0 else "on_track"
        return {
            "checkpoint_id": self.generate_next_checkpoint(),
            "timestamp": self._next_timestamp(),
            "selected_strategy": selected_strategy,
            "planned_progress": planned_progress,
            "actual_progress": actual_progress,
            "confidence": confidence,
            "status": status,
            "metadata": {
                "task_count": task_count,
                "risk_level": risk_summary.get("executive_risk_level", risk_summary.get("risk_level", "unknown")),
                "experience_decision_count": experience_summary.get("decision_count", 0) if isinstance(experience_summary, dict) else 0,
            },
        }

    def _detect_confidence_degradation(self, checkpoint: ExecutionCheckpoint) -> List[ExecutionDeviation]:
        if len(self._checkpoints) < 2:
            return []
        previous = self._checkpoints[-2]
        drop = previous.confidence - checkpoint.confidence
        if drop < self.CONFIDENCE_DROP_THRESHOLD:
            return []
        return [
            self._deviation(
                "falling_confidence",
                "medium",
                min(100.0, drop * 2.0),
                "Execution confidence has fallen since the previous checkpoint.",
                "Review current blockers and reduce uncertainty before continuing.",
                checkpoint.timestamp,
                self._metadata_goals(checkpoint.metadata),
                {"confidence_drop": round(drop, 2)},
            )
        ]

    def _detect_context_mismatch(self, executive_context: Dict[str, Any]) -> List[ExecutionDeviation]:
        if not executive_context.get("context_mismatch"):
            return []
        return [
            self._deviation(
                "context_mismatch",
                "medium",
                55.0,
                "Current context no longer matches the selected execution strategy.",
                "Reconfirm execution context before continuing.",
                self._current_timestamp(),
                self._affected_goals(executive_context),
                {},
            )
        ]

    def _detect_priority_inversion(self, executive_context: Dict[str, Any]) -> List[ExecutionDeviation]:
        if not executive_context.get("priority_inversion"):
            return []
        return [
            self._deviation(
                "priority_inversion",
                "medium",
                60.0,
                "Lower-priority work is displacing strategic execution.",
                "Protect strategic work and rebalance execution order.",
                self._current_timestamp(),
                self._affected_goals(executive_context),
                {},
            )
        ]

    def _deviation(
        self,
        deviation_type: str,
        severity: str,
        severity_score: float,
        description: str,
        recommended_recovery: str,
        detected_at: datetime,
        affected_goals: List[str],
        metadata: Dict[str, Any],
    ) -> ExecutionDeviation:
        return ExecutionDeviation(
            deviation_id=f"execution-deviation-{deviation_type}-{len(metadata)}-{int(severity_score)}",
            deviation_type=deviation_type,
            severity=severity,
            severity_score=severity_score,
            detected_at=detected_at,
            affected_goals=affected_goals,
            description=description,
            recommended_recovery=recommended_recovery,
            metadata=metadata,
        )

    def _recovery(self, action: str, priority: int, impact: float, rationale: str, created_at: datetime, metadata: Dict[str, Any]) -> RecoveryRecommendation:
        return RecoveryRecommendation(
            recovery_id=f"execution-recovery-{action.replace(' ', '-')}-{priority}",
            action=action,
            priority=priority,
            expected_impact=impact,
            rationale=rationale,
            created_at=created_at,
            metadata=metadata,
        )

    def _recovery_action(self, deviation_type: str) -> str:
        return {
            "late_execution": "increase focus time",
            "missed_milestone": "delay milestone",
            "blocked_dependency": "recover dependency chain",
            "falling_confidence": "rebalance execution",
            "goal_drift": "protect strategic work",
            "schedule_drift": "reorder tasks",
            "capacity_overload": "reduce workload",
            "context_mismatch": "rebalance execution",
            "priority_inversion": "protect strategic work",
            "confidence_degradation": "reduce workload",
        }.get(deviation_type, "rebalance execution")

    def _dedupe_deviations(self, deviations: List[ExecutionDeviation]) -> List[ExecutionDeviation]:
        deduped: List[ExecutionDeviation] = []
        seen = set()
        for deviation in deviations:
            key = (deviation.deviation_type, deviation.description)
            if key not in seen:
                seen.add(key)
                deduped.append(deviation)
        return sorted(deduped, key=lambda item: (-item.severity_score, item.deviation_type, item.deviation_id))

    def _dedupe_recoveries(self, recoveries: List[RecoveryRecommendation]) -> List[RecoveryRecommendation]:
        deduped: List[RecoveryRecommendation] = []
        seen = set()
        for recovery in recoveries:
            if recovery.action not in seen:
                seen.add(recovery.action)
                deduped.append(recovery)
        return sorted(deduped, key=lambda item: (item.priority, -item.expected_impact, item.action))

    def _deviation_obj(self, value: ExecutionDeviation | Dict[str, Any]) -> ExecutionDeviation:
        return value if isinstance(value, ExecutionDeviation) else ExecutionDeviation(**self._dict(value, "deviation"))

    def _recovery_obj(self, value: RecoveryRecommendation | Dict[str, Any]) -> RecoveryRecommendation:
        return value if isinstance(value, RecoveryRecommendation) else RecoveryRecommendation(**self._dict(value, "recovery"))

    def _severity_from_score(self, score: float) -> str:
        if score >= 75.0:
            return "critical"
        if score >= 50.0:
            return "high"
        if score >= 25.0:
            return "medium"
        return "low"

    def _confidence_trend(self) -> str:
        if len(self._checkpoints) < 2:
            return "insufficient_data"
        previous, current = self._checkpoints[-2], self._checkpoints[-1]
        if current.confidence > previous.confidence + 5.0:
            return "improving"
        if current.confidence < previous.confidence - 5.0:
            return "declining"
        return "stable"

    def _next_timestamp(self) -> datetime:
        return self.BASE_TIMESTAMP + timedelta(minutes=len(self._checkpoints))

    def _current_timestamp(self) -> datetime:
        return self._checkpoints[-1].timestamp if self._checkpoints else self.BASE_TIMESTAMP

    def _execution_opportunities(self, state: PlanExecutionState) -> List[str]:
        opportunities = []
        if state.execution_health >= 75.0:
            opportunities.append("Maintain current execution rhythm")
        if state.recovery_readiness >= 70.0:
            opportunities.append("Recovery capacity is available if deviations increase")
        if state.execution_momentum >= 70.0:
            opportunities.append("Execution momentum is strong")
        return opportunities or ["Continue monitoring execution alignment"]

    def _affected_goals(self, executive_context: Dict[str, Any]) -> List[str]:
        goals = executive_context.get("affected_goals", [])
        if isinstance(goals, list):
            return [str(goal) for goal in goals if str(goal).strip()]
        return []

    def _metadata_goals(self, metadata: Dict[str, Any]) -> List[str]:
        goals = metadata.get("affected_goals", [])
        if isinstance(goals, list):
            return [str(goal) for goal in goals if str(goal).strip()]
        return []

    def _bounded(self, value: Any, field_name: str, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        if number < minimum or number > maximum:
            raise ValueError(f"{field_name} must be between {minimum} and {maximum}.")
        return number

    def _dict(self, value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        self._validate_payload(value, field_name)
        return dict(value)

    def _validate_payload(self, payload: Any, field_name: str) -> None:
        if isinstance(payload, dict):
            for value in payload.values():
                self._validate_payload(value, field_name)
            return
        if isinstance(payload, list):
            for value in payload:
                self._validate_payload(value, field_name)
            return
        if isinstance(payload, bool) or payload is None or isinstance(payload, str):
            return
        if isinstance(payload, (int, float)) and not math.isfinite(float(payload)):
            raise ValueError(f"{field_name} contains non-finite numeric value.")

    def _clamp(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
