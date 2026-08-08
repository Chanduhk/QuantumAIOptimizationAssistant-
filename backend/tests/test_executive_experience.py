from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest

from backend.app.domain.executive_experience_model import (
    ExecutiveDecisionRecord,
    ExecutiveLearningSnapshot,
    ExecutivePattern,
    ExecutiveStrategyProfile,
)
from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain
from backend.app.orchestrator.executive_experience import ExecutiveExperience


BASE_TIME = datetime(2026, 1, 1, 9, 0, 0)


def reasoning(action="Use optimized plan", confidence=82.0, sources=None, conflicts=None):
    sources = sources or ["DecisionIntelligenceEngine", "FutureSimulationEngine"]
    evidence = [
        {
            "source": source,
            "confidence": confidence,
            "recommendation": action,
            "risk_level": "low",
            "priority": 2,
            "score": 80.0,
            "explanation": f"{source} supports {action}.",
            "metadata": {},
        }
        for source in sources
    ]
    return {
        "recommended_action": action,
        "confidence": confidence,
        "executive_priority": 2,
        "why": "Best fused evidence.",
        "expected_benefits": ["Goal progress"],
        "known_risks": ["No major risks"],
        "alternatives": [{"recommendation": "Alternative", "why_rejected": "Lower score"}],
        "reasoning_trace": {
            "evidence_used": evidence,
            "conflicts_found": conflicts or [],
            "reasoning_steps": ["Collected evidence.", f"Selected {action}."],
            "selected_strategy": action,
            "confidence": confidence,
            "rejected_alternatives": [{"recommendation": "Alternative", "why_rejected": "Lower score"}],
            "tradeoffs": [{"category": "productivity", "benefit": 80.0, "cost": 5.0}],
            "risk_summary": {"risk_score": 10.0, "risk_level": "low"},
        },
    }


def record_payload(action="Use optimized plan", confidence=82.0, sources=None, conflicts=None):
    return {
        "executive_context": {"context": {"current_tasks": []}},
        "reasoning": reasoning(action=action, confidence=confidence, sources=sources, conflicts=conflicts),
        "recommended_plan": {"title": action},
        "risk_summary": {"risk_score": 10.0, "risk_level": "low"},
    }


def add_record(experience, index, action="Use optimized plan", confidence=82.0, success_score=None, sources=None, conflicts=None):
    return experience.record_decision(
        **record_payload(action=action, confidence=confidence, sources=sources, conflicts=conflicts),
        success_score=success_score,
        actual_outcome={"completed": success_score is not None} if success_score is not None else None,
        execution_time=1.5,
        timestamp=BASE_TIME + timedelta(minutes=index),
    )


def test_executive_decision_record_validation_and_immutability():
    record = ExecutiveDecisionRecord(
        decision_id="decision-1",
        timestamp=BASE_TIME,
        executive_context={"context": {}},
        selected_strategy="Use optimized plan",
        confidence=80.0,
        reasoning_trace=reasoning()["reasoning_trace"],
        evidence_summary={"evidence_count": 2, "conflict_count": 0, "sources": ["FutureSimulationEngine"]},
        tradeoffs=[{"category": "productivity", "benefit": 80.0}],
        risks={"risk_score": 10.0},
        expected_outcome={"expected_confidence": 80.0},
        actual_outcome=None,
        success_score=None,
        execution_time=1.0,
    )

    assert record.selected_strategy == "Use optimized plan"
    with pytest.raises(FrozenInstanceError):
        record.confidence = 1.0
    with pytest.raises(ValueError, match="timestamp must be a datetime"):
        ExecutiveDecisionRecord(
            decision_id="bad",
            timestamp="bad",
            executive_context={},
            selected_strategy="Bad",
            confidence=1.0,
            reasoning_trace=reasoning()["reasoning_trace"],
            evidence_summary={},
            tradeoffs=[],
            risks={},
            expected_outcome={},
            actual_outcome=None,
            success_score=None,
            execution_time=0.0,
        )
    with pytest.raises(ValueError, match="confidence must be finite"):
        ExecutiveDecisionRecord(
            decision_id="bad",
            timestamp=BASE_TIME,
            executive_context={},
            selected_strategy="Bad",
            confidence=float("nan"),
            reasoning_trace=reasoning()["reasoning_trace"],
            evidence_summary={},
            tradeoffs=[],
            risks={},
            expected_outcome={},
            actual_outcome=None,
            success_score=None,
            execution_time=0.0,
        )


def test_pattern_snapshot_and_strategy_profile_validation():
    pattern = ExecutivePattern(
        pattern_name="strategy:optimized",
        frequency=2,
        success_rate=75.0,
        average_confidence=80.0,
        common_failures=[],
        common_successes=["Simulation-supported reasoning succeeded"],
        recommended_strategy="Increase attention to optimized",
    )
    snapshot = ExecutiveLearningSnapshot(
        total_decisions=2,
        successful_decisions=1,
        failed_decisions=0,
        overall_success_rate=75.0,
        confidence_calibration={"calibration_status": "well_calibrated"},
        top_patterns=[{"pattern_name": pattern.pattern_name}],
        improvement_areas=["Increase importance of FutureSimulationEngine."],
    )
    profile = ExecutiveStrategyProfile("Use optimized plan", 2, 75.0, 80.0, 1.25)

    assert snapshot.total_decisions == 2
    assert profile.recommended_weight == 1.25
    with pytest.raises(ValueError, match="success_rate must be finite"):
        ExecutivePattern("bad", 1, float("inf"), 50.0)
    with pytest.raises(ValueError, match="recommended_weight must be between"):
        ExecutiveStrategyProfile("bad", 1, 50.0, 50.0, 3.0)


def test_experience_recording_and_bounded_history():
    experience = ExecutiveExperience(max_records=2)
    add_record(experience, 1, success_score=80.0)
    second = add_record(experience, 2, action="Reduce workload pressure", success_score=40.0)
    third = add_record(experience, 3, action="Use optimized plan", success_score=90.0)

    history = experience.get_history()
    assert len(history) == 2
    assert history[0].decision_id == second.decision_id
    assert history[1].decision_id == third.decision_id
    with pytest.raises(ValueError, match="limit must be a positive integer"):
        experience.get_history(limit=0)


def test_update_outcome_and_confidence_calibration():
    experience = ExecutiveExperience()
    record = add_record(experience, 1, confidence=95.0)

    updated = experience.update_outcome(
        record.decision_id,
        actual_outcome={"completed": False},
        success_score=40.0,
        execution_time=3.0,
    )
    calibration = experience.confidence_calibration()

    assert updated.success_score == 40.0
    assert calibration["calibration_status"] == "overestimated"
    assert calibration["calibration_error"] == 55.0
    with pytest.raises(ValueError, match="decision_id was not found"):
        experience.update_outcome("missing", actual_outcome={}, success_score=10.0)


def test_pattern_discovery_strategy_profiles_and_lessons():
    experience = ExecutiveExperience()
    add_record(experience, 1, action="Use optimized plan", confidence=80.0, success_score=85.0)
    add_record(experience, 2, action="Use optimized plan", confidence=82.0, success_score=90.0)
    add_record(
        experience,
        3,
        action="Deadline-only decision",
        confidence=90.0,
        success_score=35.0,
        sources=["DecisionEngine"],
    )
    add_record(
        experience,
        4,
        action="Deadline-only decision",
        confidence=88.0,
        success_score=40.0,
        sources=["DecisionEngine"],
    )

    patterns = experience.discover_patterns()
    profiles = experience.strategy_profiles()
    lessons = experience.executive_lessons()

    assert patterns[0].frequency >= 2
    assert profiles[0].strategy_name == "Use optimized plan"
    assert any("Use optimized plan is a reliable executive strategy." == lesson for lesson in lessons)
    assert any("Deadline-only decision should be treated cautiously" in lesson for lesson in lessons)


def test_learning_snapshot_and_experience_summary():
    experience = ExecutiveExperience()
    add_record(experience, 1, action="Use optimized plan", success_score=80.0)
    add_record(experience, 2, action="Use optimized plan", success_score=90.0)

    snapshot = experience.learning_snapshot()
    summary = experience.summarize_experience()

    assert snapshot.total_decisions == 2
    assert snapshot.successful_decisions == 2
    assert summary["executive_experience"]["decision_count"] == 2
    assert summary["executive_confidence_calibration"]["completed_decisions"] == 2
    assert isinstance(summary["executive_lessons"], list)


def test_experience_detects_recurring_conflicts():
    conflict = {
        "source_a": "GoalIntelligenceEngine",
        "source_b": "DependencyIntelligenceEngine",
        "conflict_reason": "Dependency evidence reports blockers.",
        "severity": 85.0,
        "resolution_strategy": "Resolve blockers first.",
    }
    experience = ExecutiveExperience()
    add_record(experience, 1, success_score=45.0, conflicts=[conflict])
    add_record(experience, 2, success_score=55.0, conflicts=[conflict])

    patterns = experience.discover_patterns()
    summary = experience.experience_summary()

    assert any(pattern.pattern_name == "conflict:recurring" for pattern in patterns)
    assert summary["most_common_conflict"] == "Dependency evidence reports blockers."


def test_experience_outputs_are_deterministic():
    first = ExecutiveExperience()
    second = ExecutiveExperience()
    for target in (first, second):
        add_record(target, 1, action="Use optimized plan", success_score=80.0)
        add_record(target, 2, action="Reduce workload pressure", success_score=60.0)

    assert first.summarize_experience() == second.summarize_experience()


def test_experience_rejects_malformed_inputs_and_non_finite_values():
    experience = ExecutiveExperience()
    bad = record_payload()
    bad["reasoning"] = {"recommended_action": "Bad"}
    with pytest.raises(ValueError, match="reasoning_trace"):
        experience.record_decision(**bad)
    with pytest.raises(ValueError, match="success_score must be finite"):
        experience.record_decision(**record_payload(), success_score=float("inf"))
    with pytest.raises(ValueError, match="evidence entries must be dictionaries"):
        experience.record_decision(
            **{
                **record_payload(),
                "reasoning": {
                    **reasoning(),
                    "reasoning_trace": {
                        **reasoning()["reasoning_trace"],
                        "evidence_used": ["bad"],
                    },
                },
            }
        )


def test_large_history_remains_deterministic():
    experience = ExecutiveExperience(max_records=200)
    for index in range(120):
        add_record(
            experience,
            index,
            action=f"Strategy {index % 4}",
            confidence=60.0 + (index % 30),
            success_score=50.0 + (index % 45),
            sources=["FutureSimulationEngine", f"Source{index % 3}"],
        )

    summary = experience.summarize_experience()

    assert summary["executive_experience"]["decision_count"] == 120
    assert len(summary["executive_strategy_profile"]) == 4
    assert summary == experience.summarize_experience()


def test_executive_brain_records_experience_outputs():
    brain = ExecutiveCognitiveBrain()
    result = brain.execute_planning_request([], behavior_patterns={}, goals=[])

    assert result["executive_experience"]["decision_count"] == 1
    assert result["executive_learning_summary"]["total_decisions"] == 1
    assert isinstance(result["executive_patterns"], list)
    assert isinstance(result["executive_strategy_profile"], list)
    assert result["executive_confidence_calibration"]["completed_decisions"] == 0
    assert brain.executive_experience.get_history(limit=1)[0].selected_strategy == result["executive_reasoning"]["recommended_action"]


def test_executive_brain_experience_is_additive_and_backward_compatible():
    result = ExecutiveCognitiveBrain().execute_planning_request([], behavior_patterns={}, goals=[])
    original_sections = {
        "executive_context",
        "executive_objectives",
        "candidate_plans",
        "recommended_plan",
        "future_analysis",
        "tradeoff_analysis",
        "risk_summary",
        "executive_summary",
        "explanations",
        "reflection",
        "executive_reasoning",
        "executive_confidence",
        "executive_tradeoffs",
        "executive_conflicts",
        "executive_trace",
    }

    assert original_sections <= set(result)
    assert "executive_experience" in result
    assert "executive_lessons" in result
