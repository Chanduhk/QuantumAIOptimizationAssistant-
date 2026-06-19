import pytest

from backend.app.engines.planning_engine import PlanningEngine


@pytest.fixture
def engine() -> PlanningEngine:
    return PlanningEngine()


def test_generates_daily_plan_with_expected_schema(engine: PlanningEngine) -> None:
    tasks = [
        {
            "id": "t1",
            "title": "Implement feature",
            "task_type": "coding",
            "priority": 5,
            "optimized_hour": 9,
            "estimated_duration": 2,
            "predicted_productivity": 82.4,
        }
    ]
    patterns = {"best_focus_hours": [9, 11], "preferred_task_types": ["coding"]}

    result = engine.generate_daily_plan(tasks, patterns)

    assert result["plan_date_context"] == "daily"
    assert result["best_focus_hours"] == [9, 11]
    assert result["preferred_task_types"] == ["coding"]
    assert result["tasks"][0]["sequence"] == 1
    assert result["tasks"][0]["task_id"] == "t1"
    assert result["tasks"][0]["recommended_hour"] == 9
    assert result["tasks"][0]["focus_alignment"] is True
    assert "matches preferred task type" in result["tasks"][0]["rationale"]


def test_assigns_best_focus_hours_when_task_has_no_hour(engine: PlanningEngine) -> None:
    tasks = [{"id": "a"}, {"id": "b"}, {"id": "c"}]

    result = engine.generate_daily_plan(tasks, {"best_focus_hours": [8, 10]})

    assert [task["recommended_hour"] for task in result["tasks"]] == [8, 10, 8]


def test_scheduled_hour_is_used_when_optimized_hour_is_missing(engine: PlanningEngine) -> None:
    result = engine.generate_daily_plan([{"id": "a", "scheduled_hour": 13}], {"best_focus_hours": [8]})

    assert result["tasks"][0]["recommended_hour"] == 13


def test_focus_alignment_tracks_preferred_task_type(engine: PlanningEngine) -> None:
    tasks = [{"id": "a", "task_type": "Admin"}, {"id": "b", "task_type": "coding"}]

    result = engine.generate_daily_plan(tasks, {"preferred_task_types": ["admin"]})

    assert [task["focus_alignment"] for task in result["tasks"]] == [True, False]


def test_missing_productivity_uses_available_rationale_or_default(engine: PlanningEngine) -> None:
    no_context = engine.generate_daily_plan([{"id": "a"}], {})
    focus_context = engine.generate_daily_plan([{"id": "b", "scheduled_hour": 10}], {})

    assert no_context["tasks"][0]["rationale"] == "planned using default heuristics"
    assert "scheduled near focus hour 10" in focus_context["tasks"][0]["rationale"]


def test_invalid_recommended_hour_becomes_none(engine: PlanningEngine) -> None:
    result = engine.generate_daily_plan([{"id": "a", "scheduled_hour": 99}], {})

    assert result["tasks"][0]["recommended_hour"] is None


def test_empty_task_list_returns_empty_plan(engine: PlanningEngine) -> None:
    assert engine.generate_daily_plan([], {"best_focus_hours": [9]})["tasks"] == []


def test_planning_is_deterministic(engine: PlanningEngine) -> None:
    tasks = [{"id": "a"}, {"id": "b", "task_type": "coding"}]
    patterns = {"best_focus_hours": [9], "preferred_task_types": ["coding"]}

    first = engine.generate_daily_plan(tasks, patterns)
    second = engine.generate_daily_plan(tasks, patterns)

    assert first == second


def test_rejects_invalid_inputs(engine: PlanningEngine) -> None:
    with pytest.raises(ValueError, match="tasks must be a list"):
        engine.generate_daily_plan(None, {})

    with pytest.raises(ValueError, match="Each task must be a dictionary"):
        engine.generate_daily_plan([{"id": "valid"}, object()], {})
