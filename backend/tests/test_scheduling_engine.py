import math

import pytest

from backend.app.engines.scheduling_engine import SchedulingEngine


@pytest.fixture
def engine() -> SchedulingEngine:
    return SchedulingEngine()


def test_generates_schedule_by_ranked_productivity_hours(engine: SchedulingEngine) -> None:
    tasks = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    patterns = {"hourly_productivity": {9: 90, 10: 80, 8: 50}}

    result = engine.optimize_schedule(tasks, patterns, day_start=8, day_end=10)
    by_id = {task["id"]: task for task in result}

    assert by_id["a"]["scheduled_hour"] == 9
    assert by_id["b"]["scheduled_hour"] == 10
    assert by_id["c"]["scheduled_hour"] == 8
    assert by_id["a"]["schedule_score"] == 90.0
    assert [task["scheduled_hour"] for task in result] == [8, 9, 10]


def test_focus_hours_are_used_when_productivity_map_is_missing(engine: SchedulingEngine) -> None:
    tasks = [{"id": "a"}, {"id": "b"}, {"id": "c"}]

    result = engine.optimize_schedule(tasks, {"best_focus_hours": [11, 9]}, day_start=8, day_end=12)
    by_id = {task["id"]: task for task in result}

    assert by_id["a"]["scheduled_hour"] == 11
    assert by_id["b"]["scheduled_hour"] == 9
    assert by_id["c"]["scheduled_hour"] == 8


def test_empty_task_list_returns_empty_schedule(engine: SchedulingEngine) -> None:
    assert engine.optimize_schedule([], {}, day_start=8, day_end=10) == []


def test_duplicate_productivity_scores_keep_stable_hour_order(engine: SchedulingEngine) -> None:
    tasks = [{"id": "a"}, {"id": "b"}]
    patterns = {"hourly_productivity": {9: 50, 10: 50}}

    result = engine.optimize_schedule(tasks, patterns, day_start=9, day_end=10)
    by_id = {task["id"]: task for task in result}

    assert by_id["a"]["scheduled_hour"] == 9
    assert by_id["b"]["scheduled_hour"] == 10


def test_missing_productivity_map_falls_back_to_day_range(engine: SchedulingEngine) -> None:
    tasks = [{"id": "a"}, {"id": "b"}]

    result = engine.optimize_schedule(tasks, {}, day_start=6, day_end=7)

    assert [task["scheduled_hour"] for task in result] == [6, 7]
    assert all(task["schedule_score"] == 0.0 for task in result)


def test_string_hour_keys_match_integer_key_behavior(engine: SchedulingEngine) -> None:
    tasks = [{"id": "a"}, {"id": "b"}]
    string_patterns = {"hourly_productivity": {"10": 10, "9": 90}}
    integer_patterns = {"hourly_productivity": {10: 10, 9: 90}}

    string_result = engine.optimize_schedule(tasks, string_patterns, day_start=9, day_end=10)
    integer_result = engine.optimize_schedule(tasks, integer_patterns, day_start=9, day_end=10)

    assert string_result == integer_result
    assert {task["id"]: task["scheduled_hour"] for task in string_result} == {"a": 9, "b": 10}


def test_schedule_beyond_day_end_adds_warning_fields(engine: SchedulingEngine) -> None:
    result = engine.optimize_schedule(
        [{"id": "a", "estimated_duration": 3}],
        {"hourly_productivity": {9: 90}},
        day_start=8,
        day_end=10,
    )

    scheduled = result[0]
    assert scheduled["scheduled_hour"] == 9
    assert scheduled["scheduled_end_hour"] == 12.0
    assert scheduled["schedule_warning"] == "scheduled_end_hour exceeds day_end."
    assert "capacity_warning" in scheduled


def test_schedule_within_day_end_does_not_add_warning_fields(engine: SchedulingEngine) -> None:
    result = engine.optimize_schedule(
        [{"id": "a", "estimated_duration": 1}],
        {"hourly_productivity": {9: 90}},
        day_start=8,
        day_end=10,
    )

    assert "schedule_warning" not in result[0]
    assert "capacity_warning" not in result[0]


def test_large_task_count_is_deterministic_and_preserves_schema(engine: SchedulingEngine) -> None:
    tasks = [{"id": f"task-{index}", "estimated_duration": 1} for index in range(100)]
    patterns = {"hourly_productivity": {hour: hour for hour in range(8, 20)}}

    first = engine.optimize_schedule(tasks, patterns, day_start=8, day_end=20)
    second = engine.optimize_schedule(tasks, patterns, day_start=8, day_end=20)

    assert first == second
    assert len(first) == 100
    assert all("scheduled_hour" in task for task in first)
    assert all("scheduled_end_hour" in task for task in first)
    assert all("schedule_score" in task for task in first)


def test_scheduling_is_deterministic(engine: SchedulingEngine) -> None:
    tasks = [{"id": "a"}, {"id": "b"}]
    patterns = {"hourly_productivity": {9: 60, 10: 50}, "best_focus_hours": [8]}

    first = engine.optimize_schedule(tasks, patterns, day_start=8, day_end=10)
    second = engine.optimize_schedule(tasks, patterns, day_start=8, day_end=10)

    assert first == second


def test_rejects_invalid_inputs(engine: SchedulingEngine) -> None:
    with pytest.raises(ValueError, match="tasks must be a list"):
        engine.optimize_schedule(None, {}, day_start=8, day_end=10)

    with pytest.raises(ValueError, match="tasks must be a list"):
        engine.optimize_schedule({"id": "not-a-list"}, {}, day_start=8, day_end=10)

    with pytest.raises(ValueError, match="behavior_patterns must be a dictionary"):
        engine.optimize_schedule([], None, day_start=8, day_end=10)

    with pytest.raises(ValueError, match="day_start must be less than day_end"):
        engine.optimize_schedule([], {}, day_start=10, day_end=10)

    with pytest.raises(ValueError, match="day_start must be less than day_end"):
        engine.optimize_schedule([], {}, day_start=10, day_end=8)

    with pytest.raises(ValueError, match="Each task must be a dictionary"):
        engine.optimize_schedule([{"id": "valid"}, None], {}, day_start=8, day_end=10)


@pytest.mark.parametrize(
    "duration",
    [0, -1, math.nan, math.inf, -math.inf, "not-numeric"],
)
def test_rejects_invalid_duration_values(engine: SchedulingEngine, duration: object) -> None:
    with pytest.raises(ValueError):
        engine.optimize_schedule([{"id": "a", "estimated_duration": duration}], {}, day_start=8, day_end=10)


def test_accepts_actual_duration_when_estimated_duration_is_missing(engine: SchedulingEngine) -> None:
    result = engine.optimize_schedule([{"id": "a", "actual_duration": 1.5}], {}, day_start=8, day_end=10)

    assert result[0]["scheduled_end_hour"] == 9.5


def test_missing_productivity_map_and_focus_hours_still_schedule(engine: SchedulingEngine) -> None:
    result = engine.optimize_schedule([{"id": "a"}, {"id": "b"}], {}, day_start=8, day_end=10)

    assert [task["scheduled_hour"] for task in result] == [8, 9]
    assert [task["schedule_score"] for task in result] == [0.0, 0.0]


def test_rejects_invalid_hour_values(engine: SchedulingEngine) -> None:
    with pytest.raises(ValueError, match="day_start and day_end must be integer hours"):
        engine.optimize_schedule([], {}, day_start="8", day_end=10)

    with pytest.raises(ValueError, match="hourly_productivity hours must be integer hours"):
        engine.optimize_schedule([], {"hourly_productivity": {9.5: 70}}, day_start=8, day_end=10)

    with pytest.raises(ValueError, match="best_focus_hours must contain integer hours"):
        engine.optimize_schedule([], {"best_focus_hours": [9.5]}, day_start=8, day_end=10)
