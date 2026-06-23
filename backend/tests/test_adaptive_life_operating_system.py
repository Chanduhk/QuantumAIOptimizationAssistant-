from __future__ import annotations

import math

import pytest

from backend.app.domain.adaptive_life_model import (
    AdaptiveRecommendation,
    LifeSignal,
    Opportunity,
    RiskAlert,
)
from backend.app.engines.adaptive_life_operating_system import AdaptiveLifeOperatingSystem
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def goals() -> list[dict]:
    return [
        {"goal_id": "g1", "priority": 8, "progress": 75, "days_inactive": 5},
        {"goal_id": "g2", "priority": 4, "progress": 20, "days_inactive": 45, "neglected": True},
    ]


def tasks() -> list[dict]:
    return [
        {"id": "t1", "goal_id": "g1", "priority": 5, "estimated_duration": 0.5, "completed": True},
        {"id": "t2", "goal_id": "g1", "priority": 3, "estimated_duration": 2.0, "completed": False},
        {"id": "t3", "goal_id": None, "priority": 2, "estimated_duration": 4.0, "completed": False},
    ]


def behavior() -> dict:
    return {
        "daily_capacity_hours": 4,
        "hourly_productivity": {9: 82, 14: 65},
        "stress_penalty": 0.35,
        "productivity_trend": "declining",
    }


def test_domain_model_validation() -> None:
    signal = LifeSignal("s1", "overload", "HIGH", 2, "Engine", "Description")
    opportunity = Opportunity("o1", "quick_win", 150, 2, "Act", "Benefit")
    alert = RiskAlert("r1", "overload", "critical", 1.5, ["g2", "g1", "g1"], "Mitigate")
    recommendation = AdaptiveRecommendation("a1", "capacity", 1, "Reason", "Action", "Outcome")

    assert signal.severity == "high"
    assert signal.confidence == 1.0
    assert opportunity.impact_score == 100.0
    assert opportunity.confidence == 1.0
    assert alert.affected_goals == ["g1", "g2"]
    assert recommendation.priority == 1

    with pytest.raises(ValueError, match="severity"):
        LifeSignal("s2", "type", "bad", 0.5, "Engine", "Description")

    with pytest.raises(ValueError, match="recommended_action"):
        Opportunity("o2", "category", 1, 0.5, "", "Benefit")

    with pytest.raises(ValueError, match="affected_goals"):
        RiskAlert("r2", "risk", "low", 0.5, [1], "Mitigate")

    with pytest.raises(ValueError, match="priority"):
        AdaptiveRecommendation("a2", "category", 0, "Reason", "Action", "Outcome")


def test_opportunity_detection_ranks_momentum_quick_wins_and_productive_periods() -> None:
    engine = AdaptiveLifeOperatingSystem()

    opportunities = engine.detect_opportunities(
        goals=goals(),
        tasks=tasks(),
        behavior_patterns=behavior(),
        dependency_analysis={"blocked_tasks": [], "critical_path": ["t1", "t2"]},
    )

    assert [item.impact_score for item in opportunities] == sorted(
        [item.impact_score for item in opportunities],
        reverse=True,
    )
    assert {item.category for item in opportunities} >= {
        "high_momentum_goal",
        "quick_win",
        "dependency_unlock",
        "productive_period",
    }


def test_risk_detection_finds_overload_blockers_neglect_and_forecast_risk() -> None:
    engine = AdaptiveLifeOperatingSystem()

    risks = engine.detect_risks(
        goals=goals(),
        tasks=tasks(),
        behavior_patterns={"daily_capacity_hours": 2, "productivity_trend": "declining"},
        dependency_analysis={"blocked_tasks": ["t2"]},
        simulation_summary={"risk_score": 65},
        reflection_summary={"average_error": 40},
    )

    risk_types = {risk.risk_type for risk in risks}
    assert "overloaded_schedule" in risk_types
    assert "blocked_dependencies" in risk_types
    assert "neglected_goals" in risk_types
    assert "declining_productivity" in risk_types
    assert "forecast_failure_risk" in risk_types


def test_burnout_analysis_levels() -> None:
    engine = AdaptiveLifeOperatingSystem()

    result = engine.analyze_burnout(
        behavior_patterns={"daily_capacity_hours": 1, "stress_penalty": 0.7, "productivity_trend": "declining"},
        tasks=tasks(),
        simulation_summary={"risk_score": 90},
        reflection_summary={"average_error": 50},
    )

    assert result["burnout_probability"] > 0.75
    assert result["burnout_level"] == "critical"


def test_strategic_drift_analysis() -> None:
    engine = AdaptiveLifeOperatingSystem()

    result = engine.analyze_strategic_drift(goals=goals(), tasks=tasks())

    assert result["strategic_alignment_score"] == 66.67
    assert result["strategic_drift_level"] == "medium"


def test_capacity_monitoring_detects_underload_healthy_and_overload() -> None:
    engine = AdaptiveLifeOperatingSystem()

    underload = engine.monitor_capacity(tasks=[{"estimated_duration": 1}], behavior_patterns={"daily_capacity_hours": 4})
    healthy = engine.monitor_capacity(tasks=[{"estimated_duration": 4}], behavior_patterns={"daily_capacity_hours": 4})
    overload = engine.monitor_capacity(tasks=tasks(), behavior_patterns={"daily_capacity_hours": 2})

    assert underload["load_status"] == "underload"
    assert healthy["load_status"] == "healthy_load"
    assert overload["load_status"] == "overload"


def test_momentum_analysis_detects_trajectories() -> None:
    engine = AdaptiveLifeOperatingSystem()

    accelerating = engine.analyze_momentum(goals=goals(), tasks=tasks(), forecast_summary={"success_probability": 0.9})
    declining = engine.analyze_momentum(goals=[{"progress": 5}], tasks=[{"completed": False}], forecast_summary={"success_probability": 0.1})

    assert accelerating["forecast_trajectory"] in {"stable", "accelerating"}
    assert declining["forecast_trajectory"] == "declining"


def test_adaptive_recommendation_generation() -> None:
    engine = AdaptiveLifeOperatingSystem()
    opportunities = engine.detect_opportunities(goals=goals(), tasks=tasks(), behavior_patterns=behavior())
    risks = engine.detect_risks(goals=goals(), tasks=tasks(), behavior_patterns={"daily_capacity_hours": 1})
    burnout = {"burnout_level": "high"}
    drift = {"strategic_alignment_score": 40}
    capacity = {"load_status": "overload"}
    momentum = {"forecast_trajectory": "declining"}

    recommendations = engine.generate_adaptive_recommendations(
        opportunities=opportunities,
        risks=risks,
        burnout=burnout,
        strategic_drift=drift,
        capacity=capacity,
        momentum=momentum,
    )

    assert [item.priority for item in recommendations] == sorted(item.priority for item in recommendations)
    assert {item.category for item in recommendations} >= {
        "risk_mitigation",
        "burnout_prevention",
        "strategic_alignment",
        "capacity",
        "momentum",
        "opportunity",
    }


def test_weekly_executive_brief_and_summary() -> None:
    engine = AdaptiveLifeOperatingSystem()

    assert engine.summarize_adaptive_life() is None

    brief = engine.generate_weekly_executive_brief(
        goals=goals(),
        tasks=tasks(),
        behavior_patterns=behavior(),
        dependency_analysis={"blocked_tasks": ["t2"], "critical_path": ["t1", "t2"]},
        simulation_summary={"risk_score": 60, "success_probability": 0.45},
        reflection_summary={"average_error": 35},
    )
    summary = engine.summarize_adaptive_life()

    assert "top_opportunities" in brief
    assert "top_risks" in brief
    assert "burnout_assessment" in brief
    assert "strategic_alignment" in brief
    assert "goal_momentum" in brief
    assert "recommended_actions" in brief
    assert summary is not None
    assert summary["risk_count"] > 0
    assert len(engine.life_signals) > 0


def test_malformed_inputs_are_rejected() -> None:
    engine = AdaptiveLifeOperatingSystem()

    with pytest.raises(ValueError, match="goals"):
        engine.detect_opportunities(goals={"bad": "shape"})

    with pytest.raises(ValueError, match="tasks"):
        engine.monitor_capacity(tasks=[None])

    with pytest.raises(ValueError, match="behavior_patterns"):
        engine.analyze_burnout(behavior_patterns=[])

    with pytest.raises(ValueError, match="positive"):
        engine.monitor_capacity(tasks=[{"estimated_duration": 0}])


def test_empty_state_is_deterministic() -> None:
    first = AdaptiveLifeOperatingSystem()
    second = AdaptiveLifeOperatingSystem()

    first_brief = first.generate_weekly_executive_brief()
    second_brief = second.generate_weekly_executive_brief()

    assert first_brief == second_brief
    assert first.summarize_adaptive_life() == second.summarize_adaptive_life()


def test_orchestrator_adaptive_life_summary_is_optional_and_validated() -> None:
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.adaptive_life_operating_system = AdaptiveLifeOperatingSystem()

    assert orchestrator._adaptive_life_summary() is None

    orchestrator.adaptive_life_operating_system.generate_weekly_executive_brief(
        goals=goals(),
        tasks=tasks(),
        behavior_patterns=behavior(),
    )
    summary = orchestrator._adaptive_life_summary()

    assert summary is not None
    assert "recommendation_count" in summary


def test_orchestrator_rejects_malformed_adaptive_life_summary() -> None:
    class BadAdaptiveOS:
        def summarize_adaptive_life(self):
            return {"burnout_probability": math.inf}

    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.adaptive_life_operating_system = BadAdaptiveOS()

    with pytest.raises(ValueError, match="adaptive_life_summary"):
        orchestrator._adaptive_life_summary()
