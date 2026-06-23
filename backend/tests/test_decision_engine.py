import math

import pytest

from backend.app.engines.decision_engine import DecisionEngine


@pytest.fixture
def engine() -> DecisionEngine:
    return DecisionEngine()


def test_prioritizes_tasks_by_existing_decision_score_formula(engine: DecisionEngine) -> None:
    tasks = [
        {"id": "low", "priority": 2, "estimated_duration": 1, "task_type": "admin"},
        {"id": "high", "priority": 8, "estimated_duration": 1, "task_type": "admin"},
    ]
    predictions = [
        {"id": "low", "predicted_productivity": 10},
        {"id": "high", "predicted_productivity": 10},
    ]

    result = engine.prioritize_tasks(tasks, predictions, {})

    assert [task["id"] for task in result] == ["high", "low"]
    assert all("decision_score" in task for task in result)
    assert all(isinstance(task["decision_score"], float) for task in result)
    assert all("decision_breakdown" in task for task in result)


def test_predicted_productivity_influences_ranking(engine: DecisionEngine) -> None:
    tasks = [
        {"id": "low-prediction", "priority": 3, "estimated_duration": 1, "task_type": "coding"},
        {"id": "high-prediction", "priority": 3, "estimated_duration": 1, "task_type": "coding"},
    ]
    predictions = [
        {"id": "low-prediction", "predicted_productivity": 10},
        {"id": "high-prediction", "predicted_productivity": 90},
    ]

    result = engine.prioritize_tasks(tasks, predictions, {})

    assert result[0]["id"] == "high-prediction"
    assert result[0]["decision_score"] > result[1]["decision_score"]


def test_preferred_task_type_boost_affects_score(engine: DecisionEngine) -> None:
    tasks = [
        {"id": "general", "priority": 3, "estimated_duration": 1, "task_type": "admin"},
        {"id": "preferred", "priority": 3, "estimated_duration": 1, "task_type": "Deep_Work"},
    ]

    result = engine.prioritize_tasks(tasks, [], {"preferred_task_types": ["deep_work"]})

    assert result[0]["id"] == "preferred"
    assert result[0]["decision_score"] - result[1]["decision_score"] == 8.0


def test_duration_penalty_favors_shorter_equivalent_tasks(engine: DecisionEngine) -> None:
    tasks = [
        {"id": "long", "priority": 4, "estimated_duration": 4, "task_type": "coding"},
        {"id": "short", "priority": 4, "estimated_duration": 1, "task_type": "coding"},
    ]

    result = engine.prioritize_tasks(tasks, [], {})

    assert result[0]["id"] == "short"
    assert result[0]["decision_score"] > result[1]["decision_score"]


def test_empty_task_list_returns_empty_list(engine: DecisionEngine) -> None:
    assert engine.prioritize_tasks([], [], {}) == []


def test_missing_prediction_values_default_to_zero(engine: DecisionEngine) -> None:
    tasks = [{"id": "task-1", "priority": 1, "estimated_duration": 1}]
    predictions = [{"id": "task-1"}]

    result = engine.prioritize_tasks(tasks, predictions, {})

    assert result[0]["predicted_productivity"] == 0.0
    assert result[0]["decision_score"] == 12.5
    assert result[0]["decision_breakdown"]["priority_score"] == 14.0
    assert result[0]["decision_breakdown"]["duration_penalty"] == -1.5


def test_tasks_without_ids_use_none_prediction_key(engine: DecisionEngine) -> None:
    tasks = [{"priority": 1, "estimated_duration": 1}]
    predictions = [{"predicted_productivity": 40}]

    result = engine.prioritize_tasks(tasks, predictions, {})

    assert result[0]["predicted_productivity"] == 40.0
    assert result[0]["decision_score"] == 40.5


def test_ranking_is_deterministic(engine: DecisionEngine) -> None:
    tasks = [
        {"id": "a", "priority": 2, "estimated_duration": 2},
        {"id": "b", "priority": 5, "estimated_duration": 1},
        {"id": "c", "priority": 3, "estimated_duration": 1},
    ]
    predictions = [
        {"id": "a", "predicted_productivity": 90},
        {"id": "b", "predicted_productivity": 40},
        {"id": "c", "predicted_productivity": 70},
    ]

    first = engine.prioritize_tasks(tasks, predictions, {})
    second = engine.prioritize_tasks(tasks, predictions, {})

    assert first == second


def test_rejects_none_tasks(engine: DecisionEngine) -> None:
    with pytest.raises(ValueError, match="tasks must be a list"):
        engine.prioritize_tasks(None, [], {})


def test_rejects_malformed_task_entries(engine: DecisionEngine) -> None:
    with pytest.raises(ValueError, match="Each task must be a dictionary"):
        engine.prioritize_tasks([{"id": "valid"}, "invalid"], [], {})


def test_strategic_and_goal_aligned_tasks_rise_in_ranking(engine: DecisionEngine) -> None:
    tasks = [
        {"id": "routine", "priority": 3, "estimated_duration": 1},
        {
            "id": "strategic",
            "priority": 3,
            "estimated_duration": 1,
            "strategic_importance": 8,
            "goal_alignment_score": 0.75,
        },
    ]

    result = engine.prioritize_tasks(tasks, [], {})

    assert result[0]["id"] == "strategic"
    breakdown = result[0]["decision_breakdown"]
    assert breakdown["strategic_score"] == 32.0
    assert breakdown["goal_alignment_score"] == 15.0


def test_overdue_tasks_receive_bounded_deadline_urgency(engine: DecisionEngine) -> None:
    tasks = [
        {"id": "later", "priority": 3, "estimated_duration": 1, "deadline_hours_remaining": 72},
        {"id": "overdue", "priority": 3, "estimated_duration": 1, "deadline_hours_remaining": -5},
    ]

    result = engine.prioritize_tasks(tasks, [], {})

    assert result[0]["id"] == "overdue"
    assert result[0]["decision_breakdown"]["deadline_score"] == 30.0
    assert result[0]["decision_breakdown"]["deadline_score"] <= 30.0


def test_deferred_tasks_gain_bounded_starvation_score(engine: DecisionEngine) -> None:
    tasks = [
        {"id": "new", "priority": 3, "estimated_duration": 1, "times_deferred": 0},
        {"id": "stale", "priority": 3, "estimated_duration": 1, "times_deferred": 99},
    ]

    result = engine.prioritize_tasks(tasks, [], {})

    assert result[0]["id"] == "stale"
    assert result[0]["decision_breakdown"]["starvation_score"] == 20.0


def test_energy_alignment_rewards_matching_energy_requirement(engine: DecisionEngine) -> None:
    tasks = [
        {"id": "mismatch", "priority": 3, "estimated_duration": 1, "energy_requirement": 20},
        {"id": "match", "priority": 3, "estimated_duration": 1, "energy_requirement": 78},
    ]

    result = engine.prioritize_tasks(tasks, [], {"average_energy_level": 80})

    assert result[0]["id"] == "match"
    assert result[0]["decision_breakdown"]["energy_alignment_score"] > result[1]["decision_breakdown"]["energy_alignment_score"]


def test_context_switch_penalty_applies_when_dominant_task_type_is_known(engine: DecisionEngine) -> None:
    tasks = [
        {"id": "same-context", "priority": 3, "estimated_duration": 1, "task_type": "coding"},
        {"id": "switch", "priority": 3, "estimated_duration": 1, "task_type": "admin"},
    ]

    result = engine.prioritize_tasks(tasks, [], {"dominant_task_type": "coding"})

    assert result[0]["id"] == "same-context"
    assert result[1]["decision_breakdown"]["context_switch_penalty"] == -6.0


def test_decision_breakdown_sums_to_decision_score(engine: DecisionEngine) -> None:
    task = {
        "id": "rich",
        "priority": 5,
        "estimated_duration": 2,
        "strategic_importance": 4,
        "deadline_hours_remaining": 8,
        "times_deferred": 2,
        "energy_requirement": 70,
        "goal_alignment_score": 60,
        "task_type": "coding",
    }

    result = engine.prioritize_tasks([task], [{"id": "rich", "predicted_productivity": 50}], {"average_energy_level": 75})[0]

    assert round(sum(result["decision_breakdown"].values()), 2) == result["decision_score"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("strategic_importance", math.nan),
        ("deadline_hours_remaining", math.inf),
        ("times_deferred", -math.inf),
        ("energy_requirement", "bad"),
        ("goal_alignment_score", math.nan),
        ("priority", "bad"),
        ("estimated_duration", math.inf),
    ],
)
def test_malformed_optional_values_are_safely_defaulted(
    engine: DecisionEngine,
    field: str,
    value: object,
) -> None:
    task = {"id": "task", "priority": 1, "estimated_duration": 1, field: value}

    result = engine.prioritize_tasks([task], [{"id": "task", "predicted_productivity": math.inf}], {"average_energy_level": math.nan})[0]

    assert math.isfinite(result["decision_score"])
    assert result["predicted_productivity"] == 0.0
    assert all(math.isfinite(component) for component in result["decision_breakdown"].values())


def test_score_components_are_bounded(engine: DecisionEngine) -> None:
    task = {
        "id": "bounded",
        "priority": 999,
        "estimated_duration": 999,
        "strategic_importance": 999,
        "deadline_hours_remaining": -999,
        "times_deferred": 999,
        "energy_requirement": 999,
        "goal_alignment_score": 999,
    }

    result = engine.prioritize_tasks([task], [{"id": "bounded", "predicted_productivity": 999}], {"average_energy_level": 100})[0]
    breakdown = result["decision_breakdown"]

    assert result["predicted_productivity"] == 100.0
    assert breakdown["priority_score"] == 140.0
    assert breakdown["strategic_score"] == 40.0
    assert breakdown["starvation_score"] == 20.0
    assert breakdown["goal_alignment_score"] == 20.0
    assert breakdown["duration_penalty"] == -36.0


def test_rich_decision_ranking_is_deterministic(engine: DecisionEngine) -> None:
    tasks = [
        {"id": "b", "priority": 4, "estimated_duration": 1, "times_deferred": 2},
        {"id": "a", "priority": 4, "estimated_duration": 1, "times_deferred": 2},
    ]

    first = engine.prioritize_tasks(tasks, [], {})
    second = engine.prioritize_tasks(tasks, [], {})

    assert first == second
    assert [task["id"] for task in first] == ["a", "b"]
