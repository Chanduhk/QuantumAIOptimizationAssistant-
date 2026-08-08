from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from backend.app.domain.executive_experience_model import (
    ExecutiveDecisionRecord,
    ExecutiveLearningSnapshot,
    ExecutivePattern,
    ExecutiveStrategyProfile,
)


class ExecutiveExperience:
    """Bounded in-memory executive experience for the Executive Cognitive Brain.

    This component records executive recommendations and derives deterministic
    learning summaries. It does not store memories, modify model weights, or
    change engine behavior.
    """

    def __init__(self, max_records: int = 1000) -> None:
        if not isinstance(max_records, int) or isinstance(max_records, bool) or max_records <= 0:
            raise ValueError("max_records must be a positive integer.")
        self.max_records = max_records
        self._records: List[ExecutiveDecisionRecord] = []

    def record_decision(
        self,
        *,
        executive_context: Dict[str, Any],
        reasoning: Dict[str, Any],
        recommended_plan: Dict[str, Any],
        risk_summary: Dict[str, Any],
        expected_outcome: Dict[str, Any] | None = None,
        actual_outcome: Dict[str, Any] | None = None,
        success_score: float | None = None,
        execution_time: float = 0.0,
        timestamp: datetime | None = None,
    ) -> ExecutiveDecisionRecord:
        """Record one executive reasoning cycle."""
        if not isinstance(reasoning, dict):
            raise ValueError("reasoning must be a dictionary.")
        trace = reasoning.get("reasoning_trace")
        if not isinstance(trace, dict):
            raise ValueError("reasoning_trace must be a dictionary.")
        timestamp = timestamp or datetime.utcnow()
        decision_id = f"executive-decision-{timestamp.strftime('%Y%m%d%H%M%S')}-{len(self._records) + 1}"
        evidence = trace.get("evidence_used", [])
        conflicts = trace.get("conflicts_found", [])
        record = ExecutiveDecisionRecord(
            decision_id=decision_id,
            timestamp=timestamp,
            executive_context=executive_context,
            selected_strategy=str(reasoning.get("recommended_action", recommended_plan.get("title", "unknown strategy"))),
            confidence=reasoning.get("confidence", 0.0),
            reasoning_trace=trace,
            evidence_summary={
                "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
                "conflict_count": len(conflicts) if isinstance(conflicts, list) else 0,
                "sources": self._evidence_sources(evidence),
            },
            tradeoffs=trace.get("tradeoffs", []),
            risks=risk_summary,
            expected_outcome=expected_outcome or self._expected_outcome(reasoning, recommended_plan, risk_summary),
            actual_outcome=actual_outcome,
            success_score=success_score,
            execution_time=execution_time,
        )
        self._records.append(record)
        if len(self._records) > self.max_records:
            self._records = self._records[-self.max_records :]
        return record

    def get_history(self, limit: int | None = None) -> List[ExecutiveDecisionRecord]:
        """Return recent executive decision records."""
        if limit is None:
            return list(self._records)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError("limit must be a positive integer.")
        return list(self._records[-limit:])

    def update_outcome(
        self,
        decision_id: str,
        *,
        actual_outcome: Dict[str, Any],
        success_score: float,
        execution_time: float | None = None,
    ) -> ExecutiveDecisionRecord:
        """Attach actual outcome data to a recorded decision."""
        if not isinstance(decision_id, str) or not decision_id.strip():
            raise ValueError("decision_id must be a non-empty string.")
        for index, record in enumerate(self._records):
            if record.decision_id == decision_id:
                updated = ExecutiveDecisionRecord(
                    decision_id=record.decision_id,
                    timestamp=record.timestamp,
                    executive_context=record.executive_context,
                    selected_strategy=record.selected_strategy,
                    confidence=record.confidence,
                    reasoning_trace=record.reasoning_trace,
                    evidence_summary=record.evidence_summary,
                    tradeoffs=record.tradeoffs,
                    risks=record.risks,
                    expected_outcome=record.expected_outcome,
                    actual_outcome=actual_outcome,
                    success_score=success_score,
                    execution_time=record.execution_time if execution_time is None else execution_time,
                )
                self._records[index] = updated
                return updated
        raise ValueError("decision_id was not found.")

    def confidence_calibration(self) -> Dict[str, Any]:
        """Compare predicted confidence with actual success scores."""
        completed = [record for record in self._records if record.success_score is not None]
        if not completed:
            return {
                "completed_decisions": 0,
                "average_confidence": 0.0,
                "average_success": 0.0,
                "calibration_error": 0.0,
                "calibration_status": "insufficient_data",
            }
        avg_confidence = self._average([record.confidence for record in completed])
        avg_success = self._average([record.success_score or 0.0 for record in completed])
        error = round(avg_confidence - avg_success, 2)
        if error > 10.0:
            status = "overestimated"
        elif error < -10.0:
            status = "underestimated"
        else:
            status = "well_calibrated"
        return {
            "completed_decisions": len(completed),
            "average_confidence": avg_confidence,
            "average_success": avg_success,
            "calibration_error": error,
            "calibration_status": status,
        }

    def strategy_profiles(self) -> List[ExecutiveStrategyProfile]:
        """Return deterministic strategy success profiles."""
        grouped = self._group_by_strategy()
        profiles = []
        for strategy, records in grouped.items():
            success_rate = self._success_rate(records)
            average_confidence = self._average([record.confidence for record in records])
            recommended_weight = self._recommended_weight(success_rate, average_confidence)
            profiles.append(
                ExecutiveStrategyProfile(
                    strategy_name=strategy,
                    times_used=len(records),
                    success_rate=success_rate,
                    average_confidence=average_confidence,
                    recommended_weight=recommended_weight,
                )
            )
        return sorted(profiles, key=lambda item: (-item.success_rate, -item.times_used, item.strategy_name))

    def discover_patterns(self) -> List[ExecutivePattern]:
        """Discover deterministic executive reasoning patterns."""
        patterns: List[ExecutivePattern] = []
        grouped = self._group_by_strategy()
        for strategy, records in grouped.items():
            if len(records) >= 2:
                success_rate = self._success_rate(records)
                patterns.append(
                    ExecutivePattern(
                        pattern_name=f"strategy:{strategy}",
                        frequency=len(records),
                        success_rate=success_rate,
                        average_confidence=self._average([record.confidence for record in records]),
                        common_failures=self._common_failures(records),
                        common_successes=self._common_successes(records),
                        recommended_strategy=self._strategy_recommendation(strategy, success_rate),
                    )
                )
        source_counts = self._source_counts()
        for source, frequency in source_counts.items():
            if frequency >= 2:
                related = [record for record in self._records if source in record.evidence_summary.get("sources", [])]
                success_rate = self._success_rate(related)
                patterns.append(
                    ExecutivePattern(
                        pattern_name=f"source:{source}",
                        frequency=frequency,
                        success_rate=success_rate,
                        average_confidence=self._average([record.confidence for record in related]),
                        common_failures=self._common_failures(related),
                        common_successes=self._common_successes(related),
                        recommended_strategy=self._source_recommendation(source, success_rate),
                    )
                )
        conflict_records = [record for record in self._records if record.evidence_summary.get("conflict_count", 0) > 0]
        if len(conflict_records) >= 2:
            patterns.append(
                ExecutivePattern(
                    pattern_name="conflict:recurring",
                    frequency=len(conflict_records),
                    success_rate=self._success_rate(conflict_records),
                    average_confidence=self._average([record.confidence for record in conflict_records]),
                    common_failures=["Dependency conflicts repeatedly reduce execution quality"],
                    common_successes=["Explicit conflict resolution improves explainability"],
                    recommended_strategy="Resolve conflicts before increasing executive confidence",
                )
            )
        return sorted(patterns, key=lambda item: (-item.frequency, -item.success_rate, item.pattern_name))

    def learning_snapshot(self) -> ExecutiveLearningSnapshot:
        """Return aggregate executive learning state."""
        completed = [record for record in self._records if record.success_score is not None]
        successful = [record for record in completed if (record.success_score or 0.0) >= 70.0]
        failed = [record for record in completed if (record.success_score or 0.0) < 50.0]
        snapshot = ExecutiveLearningSnapshot(
            total_decisions=len(self._records),
            successful_decisions=len(successful),
            failed_decisions=len(failed),
            overall_success_rate=self._success_rate(completed),
            confidence_calibration=self.confidence_calibration(),
            top_patterns=[asdict(pattern) for pattern in self.discover_patterns()[:5]],
            improvement_areas=self.improvement_areas(),
        )
        return snapshot

    def executive_lessons(self) -> List[str]:
        """Generate deterministic executive lessons from history."""
        if not self._records:
            return ["No executive decisions recorded yet."]
        lessons = []
        calibration = self.confidence_calibration()
        if calibration["calibration_status"] == "overestimated":
            lessons.append("Executive confidence has been overestimated relative to outcomes.")
        elif calibration["calibration_status"] == "underestimated":
            lessons.append("Executive confidence has been conservative relative to outcomes.")
        for profile in self.strategy_profiles()[:3]:
            if profile.success_rate >= 70.0:
                lessons.append(f"{profile.strategy_name} is a reliable executive strategy.")
            elif profile.times_used >= 2 and profile.success_rate < 50.0:
                lessons.append(f"{profile.strategy_name} should be treated cautiously in future reasoning.")
        sources = self._source_counts()
        if sources:
            strongest = sorted(sources.items(), key=lambda item: (-item[1], item[0]))[0][0]
            lessons.append(f"{strongest} is the most common evidence source in executive reasoning.")
        conflict_count = sum(record.evidence_summary.get("conflict_count", 0) for record in self._records)
        if conflict_count:
            lessons.append("Recurring conflicts should reduce executive confidence until resolved.")
        return sorted(dict.fromkeys(lessons))

    def improvement_areas(self) -> List[str]:
        """Return suggested future reasoning adjustments without mutating weights."""
        areas = []
        calibration = self.confidence_calibration()
        if calibration["calibration_status"] == "overestimated":
            areas.append("Decrease confidence when similar high-confidence strategies lack outcome support.")
        elif calibration["calibration_status"] == "underestimated":
            areas.append("Increase confidence when historically successful low-confidence strategies recur.")
        for profile in self.strategy_profiles():
            if profile.times_used >= 2 and profile.success_rate < 50.0:
                areas.append(f"Decrease reliance on {profile.strategy_name}.")
            elif profile.success_rate >= 75.0:
                areas.append(f"Increase attention to {profile.strategy_name}.")
        source_success = self._source_success()
        for source, success_rate in source_success.items():
            if success_rate >= 75.0:
                areas.append(f"Increase importance of {source}.")
            elif success_rate < 45.0:
                areas.append(f"Decrease importance of {source}.")
        if not areas:
            areas.append("Continue collecting executive outcomes before adjusting reasoning strategy.")
        return sorted(dict.fromkeys(areas))

    def experience_summary(self) -> Dict[str, Any] | None:
        """Return executive dashboard summary after experience exists."""
        if not self._records:
            return None
        profiles = self.strategy_profiles()
        calibration = self.confidence_calibration()
        source_counts = self._source_counts()
        conflict_reasons = self._conflict_reasons()
        strongest_source = sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))[0][0] if source_counts else None
        most_common_conflict = sorted(conflict_reasons.items(), key=lambda item: (-item[1], item[0]))[0][0] if conflict_reasons else None
        return {
            "decision_count": len(self._records),
            "success_rate": self._success_rate([record for record in self._records if record.success_score is not None]),
            "confidence_calibration": calibration,
            "most_successful_strategy": profiles[0].strategy_name if profiles else None,
            "weakest_strategy": profiles[-1].strategy_name if profiles else None,
            "strongest_evidence_source": strongest_source,
            "most_common_conflict": most_common_conflict,
            "improvement_priorities": self.improvement_areas(),
        }

    def summarize_experience(self) -> Dict[str, Any] | None:
        """Return all additive Executive Brain experience outputs."""
        summary = self.experience_summary()
        if summary is None:
            return None
        return {
            "executive_experience": summary,
            "executive_learning_summary": asdict(self.learning_snapshot()),
            "executive_patterns": [asdict(pattern) for pattern in self.discover_patterns()],
            "executive_strategy_profile": [asdict(profile) for profile in self.strategy_profiles()],
            "executive_confidence_calibration": self.confidence_calibration(),
            "executive_lessons": self.executive_lessons(),
        }

    def _expected_outcome(self, reasoning: Dict[str, Any], recommended_plan: Dict[str, Any], risk_summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "recommended_action": reasoning.get("recommended_action"),
            "expected_confidence": reasoning.get("confidence", 0.0),
            "selected_plan": recommended_plan.get("title"),
            "risk_level": risk_summary.get("executive_risk_level", risk_summary.get("risk_level", "unknown")),
        }

    def _evidence_sources(self, evidence: Any) -> List[str]:
        if not isinstance(evidence, list):
            raise ValueError("evidence_used must be a list.")
        sources = []
        for item in evidence:
            if not isinstance(item, dict):
                raise ValueError("evidence entries must be dictionaries.")
            source = item.get("source")
            if isinstance(source, str) and source.strip():
                sources.append(source.strip())
        return sorted(dict.fromkeys(sources))

    def _group_by_strategy(self) -> Dict[str, List[ExecutiveDecisionRecord]]:
        grouped: Dict[str, List[ExecutiveDecisionRecord]] = {}
        for record in self._records:
            grouped.setdefault(record.selected_strategy, []).append(record)
        return dict(sorted(grouped.items()))

    def _success_rate(self, records: List[ExecutiveDecisionRecord]) -> float:
        scored = [record.success_score for record in records if record.success_score is not None]
        if not scored:
            return 0.0
        return round(sum(scored) / len(scored), 2)

    def _average(self, values: List[float | None]) -> float:
        numbers = [float(value) for value in values if value is not None]
        if not numbers:
            return 0.0
        return round(sum(numbers) / len(numbers), 2)

    def _recommended_weight(self, success_rate: float, average_confidence: float) -> float:
        if success_rate >= 75.0:
            return 1.25
        if success_rate < 45.0 and average_confidence >= 70.0:
            return 0.75
        return 1.0

    def _strategy_recommendation(self, strategy: str, success_rate: float) -> str:
        if success_rate >= 75.0:
            return f"Increase attention to {strategy}"
        if success_rate < 45.0:
            return f"Reduce reliance on {strategy}"
        return f"Continue monitoring {strategy}"

    def _source_recommendation(self, source: str, success_rate: float) -> str:
        if success_rate >= 75.0:
            return f"Increase importance of {source}"
        if success_rate < 45.0:
            return f"Decrease importance of {source}"
        return f"Continue collecting outcomes for {source}"

    def _common_failures(self, records: List[ExecutiveDecisionRecord]) -> List[str]:
        failures = []
        for record in records:
            if record.success_score is not None and record.success_score < 50.0:
                if record.evidence_summary.get("conflict_count", 0):
                    failures.append("Conflicts preceded poor outcome")
                if record.risks.get("risk_level") in {"high", "critical"} or record.risks.get("executive_risk_level") in {"high", "critical"}:
                    failures.append("High risk preceded poor outcome")
        return sorted(dict.fromkeys(failures))

    def _common_successes(self, records: List[ExecutiveDecisionRecord]) -> List[str]:
        successes = []
        for record in records:
            if record.success_score is not None and record.success_score >= 70.0:
                if "FutureSimulationEngine" in record.evidence_summary.get("sources", []):
                    successes.append("Simulation-supported reasoning succeeded")
                if "DependencyIntelligenceEngine" in record.evidence_summary.get("sources", []):
                    successes.append("Dependency-aware reasoning succeeded")
                if record.confidence >= 70.0:
                    successes.append("High-confidence reasoning succeeded")
        return sorted(dict.fromkeys(successes))

    def _source_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for record in self._records:
            for source in record.evidence_summary.get("sources", []):
                counts[source] = counts.get(source, 0) + 1
        return dict(sorted(counts.items()))

    def _source_success(self) -> Dict[str, float]:
        grouped: Dict[str, List[ExecutiveDecisionRecord]] = {}
        for record in self._records:
            for source in record.evidence_summary.get("sources", []):
                grouped.setdefault(source, []).append(record)
        return {source: self._success_rate(records) for source, records in sorted(grouped.items())}

    def _conflict_reasons(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for record in self._records:
            conflicts = record.reasoning_trace.get("conflicts_found", [])
            if isinstance(conflicts, list):
                for conflict in conflicts:
                    if isinstance(conflict, dict):
                        reason = str(conflict.get("conflict_reason", "")).strip()
                        if reason:
                            counts[reason] = counts.get(reason, 0) + 1
        return dict(sorted(counts.items()))
