import math

import pytest

from backend.app.engines.prediction_engine import PredictionEngine


class FakeBehaviorEngine:
    def __init__(self, base_score: object = 80.0) -> None:
        self.base_score = base_score
        self.calls: list[dict[str, object]] = []

    def predict_task_productivity(
        self,
        hour_of_day: int,
        task_type: str,
        duration: float,
    ) -> object:
        self.calls.append(
            {
                "hour_of_day": hour_of_day,
                "task_type": task_type,
                "duration": duration,
            }
        )
        if not isinstance(self.base_score, (int, float)):
            return self.base_score
        return self.base_score + hour_of_day - duration


@pytest.fixture
def engine() -> PredictionEngine:
    return PredictionEngine()


def test_predicts_single_task_with_complete_output_schema(engine: PredictionEngine) -> None:
    behavior_engine = FakeBehaviorEngine()
    task = {"id": "t1", "task_type": "coding", "priority": 4, "estimated_duration": 120, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture", "hour_of_day": 9}

    result = engine.predict_productivity(behavior_engine, task, {})

    assert result["id"] == "t1"
    assert result["prediction_hour"] == 9
    assert result["predicted_productivity"] == 87.0
    assert 0.05 <= result["task_success_probability"] <= 0.99
    assert result["completion_time_prediction"] >= 0.25
    assert behavior_engine.calls == [{"hour_of_day": 9, "task_type": "coding", "duration": 2.0}]


def test_predict_batch_cycles_through_focus_hours(engine: PredictionEngine) -> None:
    behavior_engine = FakeBehaviorEngine(base_score=70)
    tasks = [{"id": key, "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"} for key in ("a", "b", "c")]

    result = engine.predict_batch(behavior_engine, tasks, {"best_focus_hours": [9, 11]})

    assert [task["prediction_hour"] for task in result] == [9, 11, 9]
    assert all("predicted_productivity" in task for task in result)
    assert all("task_success_probability" not in task for task in result)


def test_optimized_hour_overrides_scheduled_and_explicit_hour(engine: PredictionEngine) -> None:
    behavior_engine = FakeBehaviorEngine()
    task = {"id": "t1", "optimized_hour": 14, "scheduled_hour": 12, "hour_of_day": 9, "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"}

    result = engine.predict_productivity(behavior_engine, task, {"best_focus_hours": [8]})

    assert result["prediction_hour"] == 14


def test_scheduled_hour_overrides_explicit_hour(engine: PredictionEngine) -> None:
    behavior_engine = FakeBehaviorEngine()
    task = {"id": "t1", "scheduled_hour": 12, "hour_of_day": 9, "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"}

    result = engine.predict_productivity(behavior_engine, task, {"best_focus_hours": [8]})

    assert result["prediction_hour"] == 12


def test_invalid_explicit_hour_fields_are_rejected(engine: PredictionEngine) -> None:
    behavior_engine = FakeBehaviorEngine()

    with pytest.raises(ValueError, match="hour_of_day must be an hour from 0 to 24."):
        engine.predict_productivity(behavior_engine, {"id": "focused", "hour_of_day": 99, "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"}, {})

    with pytest.raises(ValueError, match="scheduled_hour must be an hour from 0 to 24."):
        engine.predict_productivity(behavior_engine, {"id": "scheduled", "scheduled_hour": 99, "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"}, {})


def test_missing_hour_falls_back_to_focus_hours_then_default(engine: PredictionEngine) -> None:
    behavior_engine = FakeBehaviorEngine()

    estimate = {"estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"}
    focused = engine.predict_productivity(behavior_engine, {"id": "focused", **estimate}, {"best_focus_hours": [7, 15]})
    defaulted = engine.predict_productivity(behavior_engine, {"id": "defaulted", **estimate}, {})

    assert focused["prediction_hour"] == 7
    assert defaulted["prediction_hour"] == 10


def test_rejects_non_positive_duration(engine: PredictionEngine) -> None:
    with pytest.raises(ValueError, match="duration must be greater than zero"):
        engine.predict_productivity(FakeBehaviorEngine(), {"id": "t1", "estimated_duration": -5, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"}, {})


def test_success_probability_is_bounded(engine: PredictionEngine) -> None:
    high = engine._estimate_success_probability(500, 10)
    low = engine._estimate_success_probability(-100, 0)

    assert high == 0.99
    assert low == 0.05


def test_prediction_is_deterministic(engine: PredictionEngine) -> None:
    task = {"id": "t1", "task_type": "coding", "estimated_duration": 120, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture", "hour_of_day": 10}

    first = engine.predict_productivity(FakeBehaviorEngine(), task, {})
    second = engine.predict_productivity(FakeBehaviorEngine(), task, {})

    assert first == second


def test_rejects_invalid_single_task(engine: PredictionEngine) -> None:
    with pytest.raises(ValueError, match="task must be a dictionary"):
        engine.predict_productivity(FakeBehaviorEngine(), None, {})

    with pytest.raises(ValueError, match="behavior_patterns must be a dictionary"):
        engine.predict_productivity(FakeBehaviorEngine(), {"id": "t1"}, None)

    with pytest.raises(ValueError, match="behavior_engine must provide"):
        engine.predict_productivity(None, {"id": "t1"}, {})


def test_rejects_invalid_batch_inputs(engine: PredictionEngine) -> None:
    with pytest.raises(ValueError, match="tasks must be a list"):
        engine.predict_batch(FakeBehaviorEngine(), None, {})

    with pytest.raises(ValueError, match="tasks must be a list"):
        engine.predict_batch(FakeBehaviorEngine(), {"id": "bad"}, {})

    with pytest.raises(ValueError, match="behavior_patterns must be a dictionary"):
        engine.predict_batch(FakeBehaviorEngine(), [], None)

    with pytest.raises(ValueError, match="Each task must be a dictionary"):
        engine.predict_batch(FakeBehaviorEngine(), [{"id": "valid", "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"}, "bad"], {})


def test_missing_fields_use_backward_compatible_defaults(engine: PredictionEngine) -> None:
    behavior_engine = FakeBehaviorEngine(base_score=50)

    with pytest.raises(ValueError, match="estimated_duration is required"):
        engine.predict_productivity(behavior_engine, {"id": "t1", "actual_duration": 30}, {})


@pytest.mark.parametrize("priority", ["bad", math.nan, math.inf, -math.inf, -1])
def test_rejects_invalid_priority_values(engine: PredictionEngine, priority: object) -> None:
    with pytest.raises(ValueError):
        engine.predict_productivity(FakeBehaviorEngine(), {"id": "t1", "priority": priority}, {})


@pytest.mark.parametrize("duration", [0, -1, math.nan, math.inf, -math.inf, "bad"])
def test_rejects_invalid_duration_values(engine: PredictionEngine, duration: object) -> None:
    with pytest.raises(ValueError):
        engine.predict_productivity(FakeBehaviorEngine(), {"id": "t1", "estimated_duration": duration, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"}, {})


@pytest.mark.parametrize(
    "task",
    [
        {"id": "a", "optimized_hour": 25, "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"},
        {"id": "a", "scheduled_hour": "invalid", "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"},
        {"id": "a", "hour_of_day": 99, "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"},
    ],
)
def test_rejects_invalid_hour_fields(engine: PredictionEngine, task: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        engine.predict_productivity(FakeBehaviorEngine(), task, {})


def test_rejects_invalid_focus_hours(engine: PredictionEngine) -> None:
    with pytest.raises(ValueError, match="best_focus_hours must be a list"):
        engine.predict_productivity(FakeBehaviorEngine(), {"id": "a"}, {"best_focus_hours": "9"})

    with pytest.raises(ValueError, match="best_focus_hours must contain hours from 0 to 24"):
        engine.predict_productivity(FakeBehaviorEngine(), {"id": "a"}, {"best_focus_hours": [99]})


@pytest.mark.parametrize("prediction", [math.nan, math.inf, -math.inf, "bad"])
def test_rejects_non_numeric_or_non_finite_model_predictions(
    engine: PredictionEngine,
    prediction: object,
) -> None:
    with pytest.raises(ValueError):
        engine.predict_productivity(FakeBehaviorEngine(base_score=prediction), {"id": "a"}, {})


def test_clamps_negative_model_prediction_to_zero(engine: PredictionEngine) -> None:
    result = engine.predict_productivity(FakeBehaviorEngine(base_score=-50), {"id": "a", "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"}, {})

    assert result["predicted_productivity"] == 0.0
    assert result["task_success_probability"] == 0.15


def test_clamps_model_prediction_above_one_hundred(engine: PredictionEngine) -> None:
    result = engine.predict_productivity(FakeBehaviorEngine(base_score=500), {"id": "a", "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"}, {})

    assert result["predicted_productivity"] == 100.0
    assert result["task_success_probability"] == 0.9


def test_completion_time_rejects_malformed_average(engine: PredictionEngine) -> None:
    with pytest.raises(ValueError, match="average_completion_time"):
        engine.predict_productivity(
            FakeBehaviorEngine(),
            {"id": "a", "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"},
            {"average_completion_time": "bad"},
        )


@pytest.mark.parametrize(
    "args",
    [
        ("bad", 1),
        (50, "bad"),
        (math.nan, 1),
        (50, math.nan),
    ],
)
def test_success_probability_rejects_malformed_inputs(
    engine: PredictionEngine,
    args: tuple[object, object],
) -> None:
    with pytest.raises(ValueError):
        engine._estimate_success_probability(args[0], args[1])


@pytest.mark.parametrize(
    "args",
    [
        ("bad", 50, {}),
        (1, "bad", {}),
        (1, 50, {"average_completion_time": math.inf}),
    ],
)
def test_completion_time_rejects_malformed_inputs(
    engine: PredictionEngine,
    args: tuple[object, object, dict[str, object]],
) -> None:
    with pytest.raises(ValueError):
        engine._estimate_completion_time(args[0], args[1], args[2])


def test_batch_prediction_empty_list_returns_empty_list(engine: PredictionEngine) -> None:
    assert engine.predict_batch(FakeBehaviorEngine(), [], {}) == []


def test_batch_prediction_preserves_order(engine: PredictionEngine) -> None:
    tasks = [
        {"id": "a", "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"},
        {"id": "b", "scheduled_hour": 11, "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"},
        {"id": "c", "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "test_fixture"},
    ]

    result = engine.predict_batch(FakeBehaviorEngine(), tasks, {"best_focus_hours": [8]})

    assert [task["id"] for task in result] == ["a", "b", "c"]
    assert [task["prediction_hour"] for task in result] == [8, 11, 8]
