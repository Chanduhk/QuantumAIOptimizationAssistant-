import math

import pytest

from backend.app.engines.optimization_engine import OptimizationEngine


@pytest.fixture
def engine() -> OptimizationEngine:
    return OptimizationEngine()


def test_optimizes_schedule_by_pairing_best_tasks_with_best_hours(engine: OptimizationEngine) -> None:
    scheduled_tasks = [
        {"id": "low", "predicted_productivity": 30, "scheduled_hour": 8, "estimated_duration": 1, "schedule_score": 20},
        {"id": "high", "predicted_productivity": 90, "scheduled_hour": 10, "estimated_duration": 2, "schedule_score": 40},
    ]
    patterns = {"hourly_productivity": {8: 50, 10: 90}}

    result = engine.optimize_schedule(scheduled_tasks, patterns)
    by_id = {task["id"]: task for task in result["optimized_schedule"]}

    assert by_id["high"]["optimized_hour"] == 10
    assert by_id["high"]["optimized_end_hour"] == 12.0
    assert by_id["high"]["hour_productivity_score"] == 90.0
    assert isinstance(result["projected_productivity_gain"], float)


def test_projected_productivity_gain_uses_baseline_schedule_scores(engine: OptimizationEngine) -> None:
    scheduled_tasks = [
        {"id": "a", "predicted_productivity": 90, "scheduled_hour": 9, "schedule_score": 30},
        {"id": "b", "predicted_productivity": 80, "scheduled_hour": 10, "schedule_score": 40},
    ]
    patterns = {"hourly_productivity": {9: 100, 10: 90}}

    result = engine.optimize_schedule(scheduled_tasks, patterns)

    assert result["projected_productivity_gain"] == 120.0


def test_empty_schedule_returns_empty_result_schema(engine: OptimizationEngine) -> None:
    result = engine.optimize_schedule([], {})

    assert result == {"optimized_schedule": [], "projected_productivity_gain": 0.0}


def test_optimized_schedule_is_sorted_by_optimized_hour(engine: OptimizationEngine) -> None:
    scheduled_tasks = [
        {"id": "a", "predicted_productivity": 100, "scheduled_hour": 12},
        {"id": "b", "predicted_productivity": 10, "scheduled_hour": 8},
    ]

    result = engine.optimize_schedule(scheduled_tasks, {"hourly_productivity": {12: 80, 8: 20}})

    assert [task["optimized_hour"] for task in result["optimized_schedule"]] == [8, 12]


def test_missing_schedule_score_counts_as_zero_baseline(engine: OptimizationEngine) -> None:
    scheduled_tasks = [{"id": "a", "predicted_productivity": 1, "scheduled_hour": 9}]

    result = engine.optimize_schedule(scheduled_tasks, {"hourly_productivity": {9: 42}})

    assert result["projected_productivity_gain"] == 42.0


def test_rejects_non_positive_duration(engine: OptimizationEngine) -> None:
    scheduled_tasks = [{"id": "a", "predicted_productivity": 1, "scheduled_hour": 9, "estimated_duration": -2}]

    with pytest.raises(ValueError, match="duration must be positive"):
        engine.optimize_schedule(scheduled_tasks, {"hourly_productivity": {9: 42}})


def test_optimization_is_deterministic(engine: OptimizationEngine) -> None:
    scheduled_tasks = [
        {"id": "a", "predicted_productivity": 20, "scheduled_hour": 9},
        {"id": "b", "predicted_productivity": 30, "scheduled_hour": 10},
    ]
    patterns = {"hourly_productivity": {9: 50, 10: 60}}

    first = engine.optimize_schedule(scheduled_tasks, patterns)
    second = engine.optimize_schedule(scheduled_tasks, patterns)

    assert first == second


def test_rejects_invalid_inputs(engine: OptimizationEngine) -> None:
    with pytest.raises(ValueError, match="scheduled_tasks must be a list"):
        engine.optimize_schedule(None, {})

    with pytest.raises(ValueError, match="scheduled_tasks must be a list"):
        engine.optimize_schedule({"id": "not-a-list"}, {})

    with pytest.raises(ValueError, match="behavior_patterns must be a dictionary"):
        engine.optimize_schedule([], None)

    with pytest.raises(ValueError, match="Each scheduled task must be a dictionary"):
        engine.optimize_schedule([{"id": "valid"}, "bad"], {})


def test_string_productivity_keys_match_integer_key_behavior(engine: OptimizationEngine) -> None:
    scheduled_tasks = [
        {"id": "a", "predicted_productivity": 90, "scheduled_hour": 9, "schedule_score": 10},
        {"id": "b", "predicted_productivity": 80, "scheduled_hour": 10, "schedule_score": 20},
    ]

    string_result = engine.optimize_schedule(
        scheduled_tasks,
        {"hourly_productivity": {"9": 100, "10": 90}},
    )
    integer_result = engine.optimize_schedule(
        scheduled_tasks,
        {"hourly_productivity": {9: 100, 10: 90}},
    )

    assert string_result == integer_result
    assert string_result["projected_productivity_gain"] == 160.0


@pytest.mark.parametrize("duration", [math.nan, math.inf, -math.inf, "bad"])
def test_rejects_non_finite_or_non_numeric_duration(
    engine: OptimizationEngine,
    duration: object,
) -> None:
    with pytest.raises(ValueError):
        engine.optimize_schedule(
            [{"id": "a", "scheduled_hour": 9, "estimated_duration": duration}],
            {"hourly_productivity": {9: 50}},
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("predicted_productivity", math.nan),
        ("predicted_productivity", math.inf),
        ("predicted_productivity", "bad"),
        ("schedule_score", math.nan),
        ("schedule_score", math.inf),
        ("schedule_score", "bad"),
    ],
)
def test_rejects_invalid_task_scores(
    engine: OptimizationEngine,
    field: str,
    value: object,
) -> None:
    task = {"id": "a", "scheduled_hour": 9, field: value}

    with pytest.raises(ValueError):
        engine.optimize_schedule([task], {"hourly_productivity": {9: 50}})


@pytest.mark.parametrize(
    "patterns",
    [
        {"hourly_productivity": []},
        {"hourly_productivity": {9: math.nan}},
        {"hourly_productivity": {9: math.inf}},
        {"hourly_productivity": {9: "bad"}},
    ],
)
def test_rejects_malformed_productivity_map(
    engine: OptimizationEngine,
    patterns: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        engine.optimize_schedule([{"id": "a", "scheduled_hour": 9}], patterns)


@pytest.mark.parametrize("scheduled_hour", [25, -1, "invalid"])
def test_rejects_invalid_scheduled_hour(engine: OptimizationEngine, scheduled_hour: object) -> None:
    with pytest.raises(ValueError, match="scheduled_hour must be an hour from 0 to 24."):
        engine.optimize_schedule([{"id": "a", "scheduled_hour": scheduled_hour}], {})


def test_optimized_end_hour_overflow_adds_warning_fields(engine: OptimizationEngine) -> None:
    result = engine.optimize_schedule(
        [{"id": "a", "scheduled_hour": 9, "estimated_duration": 3}],
        {"hourly_productivity": {9: 50}},
    )

    optimized = result["optimized_schedule"][0]
    assert optimized["optimized_end_hour"] == 12.0
    assert optimized["optimized_schedule_warning"] == "optimized_end_hour exceeds scheduling window."
    assert "capacity_warning" in optimized


def test_optimized_end_hour_within_window_has_no_warning_fields(engine: OptimizationEngine) -> None:
    result = engine.optimize_schedule(
        [
            {"id": "a", "scheduled_hour": 9, "estimated_duration": 1, "predicted_productivity": 3},
            {"id": "b", "scheduled_hour": 10, "estimated_duration": 1, "predicted_productivity": 2},
            {"id": "c", "scheduled_hour": 12, "estimated_duration": 1, "predicted_productivity": 1},
        ],
        {"hourly_productivity": {9: 70, 10: 60, 12: 10}},
    )

    by_id = {task["id"]: task for task in result["optimized_schedule"]}
    assert by_id["a"]["optimized_hour"] == 9
    assert "optimized_schedule_warning" not in by_id["a"]
    assert "capacity_warning" not in by_id["a"]


def test_missing_fields_use_backward_compatible_defaults(engine: OptimizationEngine) -> None:
    result = engine.optimize_schedule([{"id": "a"}], {})

    optimized = result["optimized_schedule"][0]
    assert optimized["optimized_hour"] == 10
    assert optimized["optimized_end_hour"] == 11.0
    assert optimized["hour_productivity_score"] == 0.0
    assert result["projected_productivity_gain"] == 0.0


def test_large_schedule_is_deterministic_and_numeric(engine: OptimizationEngine) -> None:
    scheduled_tasks = [
        {
            "id": f"task-{index}",
            "scheduled_hour": 8 + (index % 12),
            "predicted_productivity": index % 100,
            "schedule_score": float(index % 10),
            "estimated_duration": 1,
        }
        for index in range(150)
    ]
    patterns = {"hourly_productivity": {hour: hour * 2 for hour in range(8, 20)}}

    first = engine.optimize_schedule(scheduled_tasks, patterns)
    second = engine.optimize_schedule(scheduled_tasks, patterns)

    assert first == second
    assert len(first["optimized_schedule"]) == 150
    assert isinstance(first["projected_productivity_gain"], float)
