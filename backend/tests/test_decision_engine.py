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
