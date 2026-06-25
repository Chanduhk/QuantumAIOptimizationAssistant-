from __future__ import annotations

import math
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List

from backend.app.domain.executive_reasoning_model import (
    Evidence,
    EvidenceConflict,
    ExecutiveRecommendation,
    ExecutiveReasoningTrace,
)


class ExecutiveReasoningEngine:
    """Fuse subsystem evidence into one deterministic executive recommendation.

    Scoring policy:
    - Source reliability weights reward engines closest to their owned expertise.
    - Evidence score and confidence dominate the ranking.
    - Lower risk, dependency feasibility, simulation support, and reflection quality
      raise confidence.
    - Conflicts, burnout, blocked dependencies, weak simulations, and missing evidence
      reduce confidence.
    """

    SOURCE_WEIGHTS = {
        "DecisionIntelligenceEngine": 1.25,
        "MultiObjectiveOptimizationEngine": 1.2,
        "FutureSimulationEngine": 1.1,
        "DependencyIntelligenceEngine": 1.15,
        "GoalIntelligenceEngine": 1.05,
        "DecisionEngine": 1.0,
        "PredictionEngine": 0.95,
        "StrategicPlanningEngine": 1.05,
        "AdaptiveLifeOperatingSystem": 1.0,
        "BehaviorLearningEngine": 0.9,
        "MetaCognitiveEngine": 0.9,
        "ContextAwarenessEngine": 0.9,
        "PersonalKnowledgeEngine": 0.85,
        "ExecutiveBrain": 1.0,
    }
    EXPECTED_EVIDENCE_SOURCES = 8
    RISK_PENALTIES = {"low": 0.0, "unknown": 4.0, "medium": 10.0, "high": 24.0, "critical": 42.0}

    def collect_evidence(
        self,
        *,
        executive_context: Dict[str, Any] | None = None,
        executive_objectives: Dict[str, Any] | None = None,
        decision_state: Dict[str, Any] | None = None,
        candidate_plans: Dict[str, Any] | None = None,
        recommended_plan: Dict[str, Any] | None = None,
        future_analysis: Dict[str, Any] | None = None,
        tradeoff_analysis: Dict[str, Any] | None = None,
        risk_summary: Dict[str, Any] | None = None,
        explanations: Dict[str, Any] | None = None,
        reflection: Dict[str, Any] | None = None,
        extra_evidence: List[Evidence | Dict[str, Any]] | None = None,
    ) -> List[Evidence]:
        """Collect normalized evidence from available executive pipeline outputs."""
        evidence: List[Evidence] = []
        evidence.extend(self._evidence_from_context(executive_context or {}))
        evidence.extend(self._evidence_from_objectives(executive_objectives or {}))
        evidence.extend(self._evidence_from_decision_state(decision_state or {}))
        evidence.extend(self._evidence_from_candidate_plans(candidate_plans or {}))
        evidence.extend(self._evidence_from_recommended_plan(recommended_plan or {}, risk_summary or {}))
        evidence.extend(self._evidence_from_future_analysis(future_analysis or {}))
        evidence.extend(self._evidence_from_tradeoffs(tradeoff_analysis or {}))
        evidence.extend(self._evidence_from_explanations(explanations or {}))
        evidence.extend(self._evidence_from_reflection(reflection or {}))
        if extra_evidence is not None:
            if not isinstance(extra_evidence, list):
                raise ValueError("extra_evidence must be a list.")
            evidence.extend(self.normalize_evidence(item) for item in extra_evidence)
        return self._dedupe_evidence(evidence)

    def normalize_evidence(self, payload: Evidence | Dict[str, Any]) -> Evidence:
        """Normalize a raw evidence dictionary or existing Evidence object."""
        if isinstance(payload, Evidence):
            return payload
        if not isinstance(payload, dict):
            raise ValueError("evidence payload must be a dictionary.")
        if {"source", "confidence", "recommendation", "risk_level", "priority", "score", "explanation", "metadata"} <= set(payload):
            return Evidence(**payload)
        source = self._text(payload.get("source", "UnknownSource"), "source")
        recommendation = self._text(payload.get("recommendation", payload.get("title", "Review evidence")), "recommendation")
        confidence = self._bounded(payload.get("confidence", payload.get("confidence_score", 50.0)), "confidence", 0.0, 100.0)
        score = self._bounded(payload.get("score", payload.get("overall_score", confidence)), "score", 0.0, 100.0)
        priority = self._positive_int(payload.get("priority", 5), "priority")
        risk_level = self._risk_level(payload.get("risk_level"), payload.get("risk_score"))
        explanation = self._text(payload.get("explanation", payload.get("reasoning", recommendation)), "explanation")
        metadata = self._dict(payload.get("metadata", {}), "metadata")
        return Evidence(source, confidence, recommendation, risk_level, priority, score, explanation, metadata)

    def detect_conflicts(self, evidence: List[Evidence | Dict[str, Any]]) -> List[EvidenceConflict]:
        """Detect deterministic disagreements and override conditions."""
        normalized = [self.normalize_evidence(item) for item in evidence]
        conflicts: List[EvidenceConflict] = []
        for index, left in enumerate(normalized):
            for right in normalized[index + 1 :]:
                conflicts.extend(self._pair_conflicts(left, right))
        return sorted(
            self._dedupe_conflicts(conflicts),
            key=lambda item: (-item.severity, item.source_a, item.source_b, item.conflict_reason),
        )

    def score_evidence(self, evidence: Evidence | Dict[str, Any]) -> float:
        """Return deterministic weighted evidence score in the 0-100 range."""
        item = self.normalize_evidence(evidence)
        source_weight = self.SOURCE_WEIGHTS.get(item.source, 0.8)
        priority_bonus = max(0.0, 18.0 - (item.priority * 2.5))
        risk_penalty = self.RISK_PENALTIES[item.risk_level]
        dependency_bonus = 12.0 if item.metadata.get("dependency_feasible") is True else 0.0
        simulation_bonus = 8.0 if item.metadata.get("simulation_supported") is True else 0.0
        reflection_penalty = self._bounded(item.metadata.get("reflection_error", 0.0), "reflection_error", 0.0, 100.0) * 0.1
        blocked_bonus = 55.0 if item.source == "DependencyIntelligenceEngine" and item.metadata.get("blocked") else 0.0
        raw = (
            item.score * 0.42
            + item.confidence * 0.34
            + priority_bonus
            + dependency_bonus
            + simulation_bonus
            + blocked_bonus
            + (source_weight * 8.0)
            - risk_penalty
            - reflection_penalty
        )
        return round(self._clamp(raw, 0.0, 100.0), 2)

    def reason(
        self,
        *,
        executive_context: Dict[str, Any] | None = None,
        executive_objectives: Dict[str, Any] | None = None,
        decision_state: Dict[str, Any] | None = None,
        candidate_plans: Dict[str, Any] | None = None,
        recommended_plan: Dict[str, Any] | None = None,
        future_analysis: Dict[str, Any] | None = None,
        tradeoff_analysis: Dict[str, Any] | None = None,
        risk_summary: Dict[str, Any] | None = None,
        explanations: Dict[str, Any] | None = None,
        reflection: Dict[str, Any] | None = None,
        extra_evidence: List[Evidence | Dict[str, Any]] | None = None,
    ) -> ExecutiveRecommendation:
        """Fuse evidence, resolve conflicts, and return the executive recommendation."""
        evidence = self.collect_evidence(
            executive_context=executive_context,
            executive_objectives=executive_objectives,
            decision_state=decision_state,
            candidate_plans=candidate_plans,
            recommended_plan=recommended_plan,
            future_analysis=future_analysis,
            tradeoff_analysis=tradeoff_analysis,
            risk_summary=risk_summary,
            explanations=explanations,
            reflection=reflection,
            extra_evidence=extra_evidence,
        )
        if not evidence:
            evidence = [
                Evidence(
                    source="ExecutiveBrain",
                    confidence=35.0,
                    recommendation="Request more evidence before committing to a plan",
                    risk_level="unknown",
                    priority=5,
                    score=35.0,
                    explanation="No intelligence subsystem produced usable evidence.",
                    metadata={"missing_evidence": True},
                )
            ]
        conflicts = self.detect_conflicts(evidence)
        ranked = self._rank_evidence(evidence)
        selected = ranked[0]
        confidence = self._propagate_confidence(selected, evidence, conflicts)
        tradeoffs = self.analyze_tradeoffs(selected, evidence, conflicts)
        alternatives = self.evaluate_alternatives(selected, ranked[1:])
        risk_summary_dict = self._build_risk_summary(selected, evidence, conflicts)
        steps = self._reasoning_steps(evidence, conflicts, selected, confidence)
        trace = ExecutiveReasoningTrace(
            evidence_used=evidence,
            conflicts_found=conflicts,
            reasoning_steps=steps,
            selected_strategy=selected.recommendation,
            confidence=confidence,
            rejected_alternatives=alternatives,
            tradeoffs=tradeoffs,
            risk_summary=risk_summary_dict,
        )
        return ExecutiveRecommendation(
            recommended_action=selected.recommendation,
            confidence=confidence,
            executive_priority=selected.priority,
            why=self._why(selected, evidence, conflicts),
            expected_benefits=self._expected_benefits(selected, evidence),
            known_risks=self._known_risks(selected, evidence, conflicts),
            alternatives=alternatives,
            reasoning_trace=trace,
        )

    def analyze_tradeoffs(
        self,
        selected: Evidence | Dict[str, Any],
        evidence: List[Evidence | Dict[str, Any]],
        conflicts: List[EvidenceConflict | Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Return structured tradeoffs for the selected evidence."""
        selected_item = self.normalize_evidence(selected)
        normalized = [self.normalize_evidence(item) for item in evidence]
        conflict_count = len([item if isinstance(item, EvidenceConflict) else EvidenceConflict(**item) for item in conflicts])
        risk_penalty = self.RISK_PENALTIES[selected_item.risk_level]
        tradeoffs = [
            {
                "category": "productivity",
                "benefit": round(selected_item.score, 2),
                "cost": round(risk_penalty, 2),
                "explanation": f"{selected_item.source} offers score {selected_item.score} with {selected_item.risk_level} risk.",
            },
            {
                "category": "goal_progress",
                "benefit": round(self._agreement_score(selected_item, normalized), 2),
                "cost": round(conflict_count * 5.0, 2),
                "explanation": "Agreement across sources increases goal-progress confidence.",
            },
            {
                "category": "dependency_impact",
                "benefit": 100.0 if selected_item.metadata.get("dependency_feasible", True) else 25.0,
                "cost": 30.0 if selected_item.metadata.get("blocked") else 0.0,
                "explanation": "Blocked dependencies override otherwise attractive recommendations.",
            },
            {
                "category": "strategic_benefit",
                "benefit": round(selected_item.confidence, 2),
                "cost": round(max(0.0, 100.0 - selected_item.confidence), 2),
                "explanation": "Strategic benefit follows confidence after risk and disagreement adjustments.",
            },
        ]
        return sorted(tradeoffs, key=lambda item: item["category"])

    def evaluate_alternatives(
        self,
        selected: Evidence | Dict[str, Any],
        alternatives: List[Evidence | Dict[str, Any]],
        *,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Return top rejected alternatives with deterministic rejection reasons."""
        selected_item = self.normalize_evidence(selected)
        ranked = self._rank_evidence([self.normalize_evidence(item) for item in alternatives])
        rejected = []
        selected_score = self.score_evidence(selected_item)
        for item in ranked[:limit]:
            reason = "Lower fused evidence score."
            if item.risk_level in {"high", "critical"} and selected_item.risk_level in {"low", "medium", "unknown"}:
                reason = "Higher risk than the selected recommendation."
            elif self._canonical(item.recommendation) == self._canonical(selected_item.recommendation):
                reason = "Supports the selected action but carried less authority."
            rejected.append(
                {
                    "recommendation": item.recommendation,
                    "source": item.source,
                    "score": self.score_evidence(item),
                    "score_gap": round(max(0.0, selected_score - self.score_evidence(item)), 2),
                    "why_rejected": reason,
                }
            )
        return rejected

    def to_dict(self, recommendation: ExecutiveRecommendation) -> Dict[str, Any]:
        """Convert a recommendation into plain dictionaries for orchestrator output."""
        return asdict(recommendation)

    def _evidence_from_context(self, context: Dict[str, Any]) -> List[Evidence]:
        self._validate_payload(context, "executive_context")
        evidence = []
        snapshot = context.get("context_snapshot")
        if isinstance(snapshot, dict):
            risk_state = str(snapshot.get("risk_state", "unknown")).lower()
            evidence.append(
                Evidence(
                    "ContextAwarenessEngine",
                    confidence=self._bounded(snapshot.get("confidence", 70.0), "context confidence", 0.0, 100.0),
                    recommendation=f"Respect current {risk_state} context",
                    risk_level=risk_state if risk_state in self.RISK_PENALTIES else "unknown",
                    priority=3,
                    score=75.0,
                    explanation="Current context state affects executive confidence.",
                    metadata={"context_alignment": snapshot.get("momentum_state"), "source_payload": snapshot},
                )
            )
        adaptive = context.get("adaptive_life")
        if isinstance(adaptive, dict):
            burnout = self._bounded(adaptive.get("burnout_probability", 0.0) * 100.0, "burnout_probability", 0.0, 100.0)
            risk_level = "critical" if burnout >= 75 else "high" if burnout >= 50 else "medium" if burnout >= 30 else "low"
            evidence.append(
                Evidence(
                    "AdaptiveLifeOperatingSystem",
                    confidence=80.0,
                    recommendation="Reduce workload pressure" if burnout >= 50 else "Maintain adaptive workload",
                    risk_level=risk_level,
                    priority=1 if burnout >= 75 else 3,
                    score=100.0 - burnout,
                    explanation="Burnout and capacity signals constrain aggressive planning.",
                    metadata={"burnout_probability": burnout, "aggressive_planning_warning": burnout >= 50},
                )
            )
        learning = context.get("behavior_learning")
        if isinstance(learning, dict):
            summary = learning.get("behavior_learning_summary", {})
            habit_strength = self._bounded(summary.get("habit_strength", 50.0), "habit_strength", 0.0, 100.0) if isinstance(summary, dict) else 50.0
            evidence.append(
                Evidence(
                    "BehaviorLearningEngine",
                    confidence=habit_strength,
                    recommendation="Follow learned productive habits",
                    risk_level="low",
                    priority=4,
                    score=habit_strength,
                    explanation="Behavior history supports recommendations matching learned habits.",
                    metadata={"behavior_supported": habit_strength >= 60.0},
                )
            )
        return evidence

    def _evidence_from_objectives(self, objectives: Dict[str, Any]) -> List[Evidence]:
        self._validate_payload(objectives, "executive_objectives")
        evidence = []
        goal_state = objectives.get("goal_state")
        if isinstance(goal_state, list) and goal_state:
            first = goal_state[0]
            if isinstance(first, dict):
                title = str(first.get("title") or first.get("goal_id") or "highest priority goal")
                priority = self._positive_int(first.get("priority", 5), "goal priority")
                evidence.append(
                    Evidence(
                        "GoalIntelligenceEngine",
                        confidence=75.0,
                        recommendation=f"Advance {title}",
                        risk_level="low",
                        priority=max(1, min(10, priority)),
                        score=self._clamp(priority * 10.0, 0.0, 100.0),
                        explanation="Goal priority indicates strategic importance.",
                        metadata={"goal_id": first.get("goal_id"), "goal_alignment": True},
                    )
                )
        dependency_state = objectives.get("dependency_state")
        if isinstance(dependency_state, dict):
            blocked = dependency_state.get("blocked_tasks", [])
            blocked_count = len(blocked) if isinstance(blocked, list) else 0
            recommendation = "Resolve dependency blockers" if blocked_count else "Proceed with dependency-feasible plan"
            evidence.append(
                Evidence(
                    "DependencyIntelligenceEngine",
                    confidence=88.0,
                    recommendation=recommendation,
                    risk_level="high" if blocked_count else "low",
                    priority=1 if blocked_count else 3,
                    score=self._clamp(100.0 - blocked_count * 20.0, 0.0, 100.0),
                    explanation="Dependency feasibility can override otherwise attractive work.",
                    metadata={"blocked": blocked_count > 0, "blocked_count": blocked_count, "dependency_feasible": blocked_count == 0},
                )
            )
        knowledge_state = objectives.get("knowledge_state")
        if isinstance(knowledge_state, dict):
            health = knowledge_state.get("knowledge_health", {})
            connectivity = self._bounded(health.get("knowledge_connectivity_score", 50.0), "knowledge_connectivity_score", 0.0, 100.0) if isinstance(health, dict) else 50.0
            evidence.append(
                Evidence(
                    "PersonalKnowledgeEngine",
                    confidence=connectivity,
                    recommendation="Use connected personal knowledge for prioritization",
                    risk_level="unknown",
                    priority=6,
                    score=connectivity,
                    explanation="Knowledge connectivity affects personalization quality.",
                    metadata={"knowledge_connectivity_score": connectivity},
                )
            )
        return evidence

    def _evidence_from_decision_state(self, decision_state: Dict[str, Any]) -> List[Evidence]:
        self._validate_payload(decision_state, "decision_state")
        evidence = []
        ordered = decision_state.get("recommended_task_order")
        if isinstance(ordered, list) and ordered and isinstance(ordered[0], dict):
            first = ordered[0]
            score = self._bounded(first.get("decision_score", first.get("predicted_productivity", 65.0)), "decision score", 0.0, 100.0)
            evidence.append(
                Evidence(
                    "DecisionEngine",
                    confidence=70.0,
                    recommendation=str(first.get("title") or first.get("id") or "top ranked task"),
                    risk_level="low",
                    priority=self._positive_int(first.get("priority", 5), "task priority"),
                    score=score,
                    explanation="DecisionEngine ranked this task highest.",
                    metadata={"task_id": first.get("id"), "decision_score": score},
                )
            )
        predicted = decision_state.get("predicted_tasks")
        if isinstance(predicted, list) and predicted:
            scores = [self._maybe_float(task.get("predicted_productivity")) for task in predicted if isinstance(task, dict)]
            scores = [score for score in scores if score is not None]
            if scores:
                average = round(sum(scores) / len(scores), 2)
                evidence.append(
                    Evidence(
                        "PredictionEngine",
                        confidence=average,
                        recommendation="Prioritize high predicted productivity work",
                        risk_level="low" if average >= 60 else "medium",
                        priority=4,
                        score=average,
                        explanation="Prediction quality supports productivity-aligned execution.",
                        metadata={"average_predicted_productivity": average},
                    )
                )
        return evidence

    def _evidence_from_candidate_plans(self, candidate_plans: Dict[str, Any]) -> List[Evidence]:
        self._validate_payload(candidate_plans, "candidate_plans")
        plans = candidate_plans.get("plans", [])
        if not isinstance(plans, list) or not plans:
            return []
        optimized = any(isinstance(plan, dict) and plan.get("plan_type") == "optimized_schedule" for plan in plans)
        return [
            Evidence(
                "StrategicPlanningEngine",
                confidence=68.0 + min(len(plans), 4) * 4.0,
                recommendation="Use candidate plan set with optimization coverage" if optimized else "Use available candidate plan set",
                risk_level="low" if optimized else "unknown",
                priority=4,
                score=75.0 if optimized else 60.0,
                explanation="Candidate plan diversity improves executive optionality.",
                metadata={"candidate_plan_count": len(plans), "has_optimized_plan": optimized},
            )
        ]

    def _evidence_from_recommended_plan(self, plan: Dict[str, Any], risk_summary: Dict[str, Any]) -> List[Evidence]:
        self._validate_payload(plan, "recommended_plan")
        if not plan:
            return []
        self._validate_payload(risk_summary, "risk_summary")
        return [
            Evidence(
                "ExecutiveBrain",
                confidence=self._bounded(plan.get("overall_score", 50.0), "overall_score", 0.0, 100.0),
                recommendation=str(plan.get("title") or plan.get("option_id") or "selected plan"),
                risk_level=self._risk_level(risk_summary.get("risk_level"), risk_summary.get("risk_score")),
                priority=2,
                score=self._bounded(plan.get("overall_score", 50.0), "overall_score", 0.0, 100.0),
                explanation=str(plan.get("reasoning") or "Executive pipeline selected this plan."),
                metadata={"option_id": plan.get("option_id"), "pipeline_selected": True},
            )
        ]

    def _evidence_from_future_analysis(self, future: Dict[str, Any]) -> List[Evidence]:
        self._validate_payload(future, "future_analysis")
        evidence = []
        simulation = future.get("simulation")
        if isinstance(simulation, dict):
            confidence = self._bounded(simulation.get("confidence_score", 60.0), "simulation confidence", 0.0, 100.0)
            success = self._bounded(simulation.get("success_probability", 0.5) * 100.0, "success_probability", 0.0, 100.0)
            evidence.append(
                Evidence(
                    "FutureSimulationEngine",
                    confidence=confidence,
                    recommendation=str(simulation.get("scenario_name") or simulation.get("scenario_id") or "simulation-supported path"),
                    risk_level=self._risk_level(None, simulation.get("risk_score")),
                    priority=3,
                    score=success,
                    explanation="Future simulation estimates success and risk of the current trajectory.",
                    metadata={"simulation_supported": success >= 60.0, "risk_score": simulation.get("risk_score")},
                )
            )
        ranked = future.get("ranked_futures", [])
        if isinstance(ranked, list) and ranked and isinstance(ranked[0], dict):
            top = ranked[0]
            summary = top.get("optimization_summary", {})
            selected = summary.get("selected_future", {}) if isinstance(summary, dict) else {}
            evidence.append(
                Evidence(
                    "MultiObjectiveOptimizationEngine",
                    confidence=self._bounded(top.get("overall_score", 70.0), "optimization overall_score", 0.0, 100.0),
                    recommendation=str(top.get("selected_scenario_name") or selected.get("scenario_name") or "optimized future"),
                    risk_level="low",
                    priority=2,
                    score=self._bounded(top.get("overall_score", selected.get("overall_score", 70.0)), "optimization score", 0.0, 100.0),
                    explanation="Multi-objective optimization balances productivity, goals, risk, and workload.",
                    metadata={"simulation_supported": True, "selected_scenario_id": top.get("selected_scenario_id") or selected.get("scenario_id")},
                )
            )
        return evidence

    def _evidence_from_tradeoffs(self, tradeoffs: Dict[str, Any]) -> List[Evidence]:
        self._validate_payload(tradeoffs, "tradeoff_analysis")
        items = tradeoffs.get("tradeoffs", [])
        if not isinstance(items, list) or not items:
            return []
        return [
            Evidence(
                "DecisionIntelligenceEngine",
                confidence=72.0,
                recommendation="Review explicit tradeoffs before committing",
                risk_level="medium" if len(items) >= 3 else "low",
                priority=5,
                score=max(45.0, 80.0 - len(items) * 5.0),
                explanation="Tradeoff count affects executive confidence.",
                metadata={"tradeoff_count": len(items)},
            )
        ]

    def _evidence_from_explanations(self, explanations: Dict[str, Any]) -> List[Evidence]:
        self._validate_payload(explanations, "explanations")
        if not explanations:
            return []
        return [
            Evidence(
                "ConversationalEngine",
                confidence=65.0,
                recommendation="Prefer explainable recommendation path",
                risk_level="unknown",
                priority=7,
                score=65.0,
                explanation="Availability of explanations improves user trust.",
                metadata={"explanation_count": len(explanations)},
            )
        ]

    def _evidence_from_reflection(self, reflection: Dict[str, Any]) -> List[Evidence]:
        self._validate_payload(reflection, "reflection")
        evidence = []
        meta = reflection.get("meta_cognitive")
        if isinstance(meta, dict):
            average_error = self._bounded(meta.get("average_error", 20.0), "average_error", 0.0, 100.0)
            evidence.append(
                Evidence(
                    "MetaCognitiveEngine",
                    confidence=max(0.0, 100.0 - average_error),
                    recommendation="Trust strategies with lower historical error",
                    risk_level=str(meta.get("risk_level", "unknown")).lower() if str(meta.get("risk_level", "unknown")).lower() in self.RISK_PENALTIES else "unknown",
                    priority=5,
                    score=max(0.0, 100.0 - average_error),
                    explanation="Meta-cognitive reflection adjusts confidence based on error history.",
                    metadata={"reflection_error": average_error},
                )
            )
        return evidence

    def _pair_conflicts(self, left: Evidence, right: Evidence) -> List[EvidenceConflict]:
        conflicts = []
        different = self._canonical(left.recommendation) != self._canonical(right.recommendation)
        score_gap = abs(self.score_evidence(left) - self.score_evidence(right))
        if different and left.confidence >= 70.0 and right.confidence >= 70.0 and score_gap <= 25.0:
            conflicts.append(
                EvidenceConflict(
                    left.source,
                    right.source,
                    "High-confidence sources recommend different actions.",
                    min(100.0, 35.0 + score_gap),
                    "Prefer higher fused confidence; retain runner-up as alternative.",
                )
            )
        if left.metadata.get("blocked") and right.source != "DependencyIntelligenceEngine":
            conflicts.append(
                EvidenceConflict(
                    left.source,
                    right.source,
                    "Dependency evidence reports blockers against a competing recommendation.",
                    85.0,
                    "Blocked dependency overrides goal or productivity preference.",
                )
            )
        if right.metadata.get("blocked") and left.source != "DependencyIntelligenceEngine":
            conflicts.append(
                EvidenceConflict(
                    left.source,
                    right.source,
                    "Dependency evidence reports blockers against a competing recommendation.",
                    85.0,
                    "Blocked dependency overrides goal or productivity preference.",
                )
            )
        if {left.risk_level, right.risk_level} & {"high", "critical"} and {left.risk_level, right.risk_level} & {"low"}:
            conflicts.append(
                EvidenceConflict(
                    left.source,
                    right.source,
                    "Risk assessment conflicts with low-risk recommendation.",
                    55.0,
                    "Reduce executive confidence and prefer feasible lower-risk evidence.",
                )
            )
        if (left.metadata.get("aggressive_planning_warning") or right.metadata.get("aggressive_planning_warning")) and (
            left.score >= 75.0 or right.score >= 75.0
        ):
            conflicts.append(
                EvidenceConflict(
                    left.source,
                    right.source,
                    "Burnout warning conflicts with aggressive high-score plan.",
                    70.0,
                    "Reduce aggressive planning confidence until capacity risk is addressed.",
                )
            )
        return conflicts

    def _rank_evidence(self, evidence: List[Evidence]) -> List[Evidence]:
        return sorted(
            evidence,
            key=lambda item: (
                -self.score_evidence(item),
                item.priority,
                item.risk_level,
                item.source,
                item.recommendation,
            ),
        )

    def _propagate_confidence(self, selected: Evidence, evidence: List[Evidence], conflicts: List[EvidenceConflict]) -> float:
        agreement_count = sum(1 for item in evidence if self._canonical(item.recommendation) == self._canonical(selected.recommendation))
        agreement_bonus = min(18.0, agreement_count * 4.5)
        source_bonus = min(12.0, len(evidence) * 1.5)
        missing_penalty = max(0.0, (self.EXPECTED_EVIDENCE_SOURCES - len(evidence)) * 2.5)
        conflict_penalty = min(35.0, sum(conflict.severity for conflict in conflicts) / max(1, len(conflicts)) * 0.22)
        risk_penalty = self.RISK_PENALTIES[selected.risk_level] * 0.35
        simulation_bonus = 8.0 if any(item.source == "FutureSimulationEngine" and item.metadata.get("simulation_supported") for item in evidence) else 0.0
        optimization_bonus = 8.0 if any(item.source == "MultiObjectiveOptimizationEngine" for item in evidence) else 0.0
        reflection_penalty = max((self._bounded(item.metadata.get("reflection_error", 0.0), "reflection_error", 0.0, 100.0) for item in evidence), default=0.0) * 0.08
        raw = (
            selected.confidence * 0.42
            + selected.score * 0.28
            + agreement_bonus
            + source_bonus
            + simulation_bonus
            + optimization_bonus
            - missing_penalty
            - conflict_penalty
            - risk_penalty
            - reflection_penalty
        )
        return round(self._clamp(raw, 0.0, 100.0), 2)

    def _build_risk_summary(self, selected: Evidence, evidence: List[Evidence], conflicts: List[EvidenceConflict]) -> Dict[str, Any]:
        highest = max((self.RISK_PENALTIES[item.risk_level] for item in evidence), default=0.0)
        conflict_pressure = min(40.0, len(conflicts) * 5.0)
        selected_pressure = self.RISK_PENALTIES[selected.risk_level]
        score = round(self._clamp(highest * 0.45 + conflict_pressure + selected_pressure * 0.35, 0.0, 100.0), 2)
        return {
            "risk_score": score,
            "risk_level": self._risk_from_score(score),
            "conflict_count": len(conflicts),
            "highest_source_risk": max((item.risk_level for item in evidence), key=lambda level: self.RISK_PENALTIES[level], default="unknown"),
        }

    def _reasoning_steps(self, evidence: List[Evidence], conflicts: List[EvidenceConflict], selected: Evidence, confidence: float) -> List[str]:
        steps = [
            f"Collected {len(evidence)} evidence sources.",
            f"Found {len(conflicts)} conflicts.",
        ]
        if conflicts:
            steps.append(f"Resolved strongest conflict with policy: {conflicts[0].resolution_strategy}")
        if any(conflict.severity >= 70.0 for conflict in conflicts):
            steps.append("Reduced confidence because high-severity conflicts were present.")
        steps.append(f"Selected {selected.source} recommendation: {selected.recommendation}.")
        steps.append(f"Final executive confidence: {confidence}%.")
        return steps

    def _why(self, selected: Evidence, evidence: List[Evidence], conflicts: List[EvidenceConflict]) -> str:
        return (
            f"{selected.source} produced the strongest fused evidence score "
            f"({self.score_evidence(selected)}) after evaluating {len(evidence)} sources "
            f"and resolving {len(conflicts)} conflicts."
        )

    def _expected_benefits(self, selected: Evidence, evidence: List[Evidence]) -> List[str]:
        benefits = [f"{selected.recommendation} is supported by {selected.source}."]
        if any(item.source == "FutureSimulationEngine" for item in evidence):
            benefits.append("Future simulation evidence supports the recommendation.")
        if any(item.source == "MultiObjectiveOptimizationEngine" for item in evidence):
            benefits.append("Multi-objective optimization evidence supports the recommendation.")
        if any(item.source == "DependencyIntelligenceEngine" and item.metadata.get("dependency_feasible") for item in evidence):
            benefits.append("Dependency analysis indicates the plan is feasible.")
        return sorted(dict.fromkeys(benefits))

    def _known_risks(self, selected: Evidence, evidence: List[Evidence], conflicts: List[EvidenceConflict]) -> List[str]:
        risks = []
        if selected.risk_level in {"medium", "high", "critical"}:
            risks.append(f"Selected evidence carries {selected.risk_level} risk.")
        if conflicts:
            risks.append(f"{len(conflicts)} evidence conflicts require attention.")
        if any(item.metadata.get("aggressive_planning_warning") for item in evidence):
            risks.append("Burnout warning may reduce execution quality.")
        if any(item.metadata.get("blocked") for item in evidence):
            risks.append("Dependency blockers may prevent execution.")
        return risks or ["No major executive risks detected."]

    def _agreement_score(self, selected: Evidence, evidence: List[Evidence]) -> float:
        if not evidence:
            return 0.0
        agreement = sum(1 for item in evidence if self._canonical(item.recommendation) == self._canonical(selected.recommendation))
        return (agreement / len(evidence)) * 100.0

    def _dedupe_evidence(self, evidence: List[Evidence]) -> List[Evidence]:
        deduped: List[Evidence] = []
        seen = set()
        for item in evidence:
            key = (item.source, self._canonical(item.recommendation), item.priority)
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return sorted(deduped, key=lambda item: (item.source, item.priority, item.recommendation))

    def _dedupe_conflicts(self, conflicts: List[EvidenceConflict]) -> List[EvidenceConflict]:
        deduped = []
        seen = set()
        for conflict in conflicts:
            pair = tuple(sorted([conflict.source_a, conflict.source_b]))
            key = (pair, conflict.conflict_reason)
            if key not in seen:
                seen.add(key)
                deduped.append(conflict)
        return deduped

    def _risk_level(self, risk_level: Any, risk_score: Any = None) -> str:
        if isinstance(risk_level, str) and risk_level.strip().lower() in self.RISK_PENALTIES:
            return risk_level.strip().lower()
        score = self._maybe_float(risk_score)
        if score is None:
            return "unknown"
        return self._risk_from_score(score)

    def _risk_from_score(self, score: float) -> str:
        if score >= 75.0:
            return "critical"
        if score >= 50.0:
            return "high"
        if score >= 25.0:
            return "medium"
        return "low"

    def _canonical(self, value: str) -> str:
        return " ".join(value.lower().replace("_", " ").split())

    def _text(self, value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value.strip()

    def _positive_int(self, value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be a positive integer.")
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a positive integer.") from None
        if number <= 0:
            raise ValueError(f"{field_name} must be a positive integer.")
        return number

    def _dict(self, value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        self._validate_payload(value, field_name)
        return dict(value)

    def _bounded(self, value: Any, field_name: str, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.") from None
        if not math.isfinite(number):
            raise ValueError(f"{field_name} must be finite.")
        return self._clamp(number, minimum, maximum)

    def _maybe_float(self, value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            raise ValueError("numeric evidence values must be finite.")
        return number

    def _clamp(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    def _validate_payload(self, payload: Any, field_name: str) -> None:
        if is_dataclass(payload):
            payload = asdict(payload)
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
