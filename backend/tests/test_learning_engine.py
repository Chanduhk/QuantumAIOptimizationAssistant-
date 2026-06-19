from typing import Any

import math
import pandas as pd
import pytest

from backend.app.engines.learning_engine import LearningEngine


_UNSET = object()


class FakeBehaviorEngine:
    def __init__(
        self,
        productivity_scores: list[float],
        *,
        task_history: Any = _UNSET,
        feature_frame: Any = _UNSET,
        metrics: Any = _UNSET,
        patterns: Any = _UNSET,
        report: Any = _UNSET,
    ) -> None:
        self.productivity_scores = productivity_scores
        self.behavior_data_df = pd.DataFrame()
        self.task_history = task_history
        self.feature_frame = feature_frame
        self.metrics = metrics if metrics is not _UNSET else {"mae": 1.5, "r2": 0.8}
        self.patterns = patterns if patterns is not _UNSET else {"best_focus_hours": [9, 10]}
        self.report = report if report is not _UNSET else {"summary": "ok"}
        self.collect_calls: list[dict[str, Any]] = []
        self.extract_called = 0
        self.train_called = 0
        self.patterns_called = 0
        self.report_called = 0

    def collect_behavior_data(self, user_id: int, days_back: int = 90) -> pd.DataFrame:
        self.collect_calls.append({"user_id": user_id, "days_back": days_back})
        if self.task_history is not _UNSET:
            return self.task_history
        if not self.productivity_scores:
            self.behavior_data_df = pd.DataFrame()
        else:
            self.behavior_data_df = pd.DataFrame({"raw": range(len(self.productivity_scores))})
        return self.behavior_data_df

    def extract_features(self) -> pd.DataFrame:
        self.extract_called += 1
        if self.feature_frame is not _UNSET:
            self.behavior_data_df = self.feature_frame if isinstance(self.feature_frame, pd.DataFrame) else pd.DataFrame()
            return self.feature_frame
        self.behavior_data_df = pd.DataFrame({"productivity_score": self.productivity_scores})
        return self.behavior_data_df

    def train_productivity_model(self) -> Any:
        self.train_called += 1
        return self.metrics

    def get_user_patterns(self) -> Any:
        self.patterns_called += 1
        return self.patterns

    def generate_report(self) -> Any:
        self.report_called += 1
        return self.report


class FakeRLScheduler:
    def __init__(self, output: Any = _UNSET) -> None:
        self.calls: list[dict[str, Any]] = []
        self.output = output

    def train_agent(
        self,
        tasks: list[dict[str, Any]],
        behavior_patterns: dict[str, Any],
        episodes: int,
    ) -> Any:
        self.calls.append(
            {
                "tasks": tasks,
                "behavior_patterns": behavior_patterns,
                "episodes": episodes,
            }
        )
        if self.output is not _UNSET:
            return self.output
        return {"episodes": episodes, "updated": True}


@pytest.fixture
def engine() -> LearningEngine:
    return LearningEngine()


def test_detect_model_drift_reports_threshold_crossing(engine: LearningEngine) -> None:
    behavior_engine = FakeBehaviorEngine([50.0] * 10 + [70.0] * 10)

    result = engine.detect_model_drift(behavior_engine, user_id=7, days_back=30)

    assert result["user_id"] == 7
    assert result["drift_score"] == 10.0
    assert result["recent_average_productivity"] == 70.0
    assert result["historical_average_productivity"] == 60.0
    assert result["drift_detected"] is True
    assert behavior_engine.collect_calls == [{"user_id": 7, "days_back": 30}]


def test_detect_model_drift_accepts_valid_user_id(engine: LearningEngine) -> None:
    result = engine.detect_model_drift(FakeBehaviorEngine([50.0, 60.0]), user_id=1)

    assert result["user_id"] == 1


def test_detect_model_drift_below_threshold_is_false(engine: LearningEngine) -> None:
    behavior_engine = FakeBehaviorEngine([50.0] * 10 + [55.0] * 10)

    result = engine.detect_model_drift(behavior_engine, user_id=1)

    assert result["drift_score"] == 2.5
    assert result["drift_detected"] is False


def test_detect_model_drift_rejects_empty_history_and_invalid_window(engine: LearningEngine) -> None:
    with pytest.raises(ValueError, match="days_back must be greater than zero"):
        engine.detect_model_drift(FakeBehaviorEngine([50.0]), user_id=1, days_back=0)

    with pytest.raises(ValueError, match="No completed tasks"):
        engine.detect_model_drift(FakeBehaviorEngine([]), user_id=1)


@pytest.mark.parametrize("user_id", [0, -1, "1", math.nan, math.inf])
def test_rejects_invalid_user_id(engine: LearningEngine, user_id: object) -> None:
    with pytest.raises(ValueError, match="user_id must be a positive integer"):
        engine.detect_model_drift(FakeBehaviorEngine([50.0, 60.0]), user_id=user_id)


def test_rejects_missing_behavior_engine_dependency(engine: LearningEngine) -> None:
    with pytest.raises(ValueError, match="behavior_engine is required"):
        engine.detect_model_drift(None, user_id=1)


def test_rejects_behavior_engine_missing_required_methods(engine: LearningEngine) -> None:
    with pytest.raises(ValueError, match="behavior_engine missing required methods"):
        engine.detect_model_drift(object(), user_id=1)


def test_rejects_none_task_history(engine: LearningEngine) -> None:
    with pytest.raises(ValueError, match="Task history cannot be None"):
        engine.detect_model_drift(FakeBehaviorEngine([50.0, 60.0], task_history=None), user_id=1)


def test_rejects_malformed_task_history(engine: LearningEngine) -> None:
    behavior_engine = FakeBehaviorEngine([50.0, 60.0], task_history={"not": "a-frame"})

    with pytest.raises(ValueError, match="Task history must be a DataFrame-like object"):
        engine.detect_model_drift(behavior_engine, user_id=1)


def test_rejects_missing_productivity_column(engine: LearningEngine) -> None:
    behavior_engine = FakeBehaviorEngine(
        [50.0, 60.0],
        feature_frame=pd.DataFrame({"score": [50.0, 60.0]}),
    )

    with pytest.raises(ValueError, match="productivity_score"):
        engine.detect_model_drift(behavior_engine, user_id=1)


@pytest.mark.parametrize("score", [math.nan, math.inf, -math.inf, "bad"])
def test_rejects_malformed_productivity_values(engine: LearningEngine, score: object) -> None:
    behavior_engine = FakeBehaviorEngine(
        [50.0, 60.0],
        feature_frame=pd.DataFrame({"productivity_score": [50.0, score]}),
    )

    with pytest.raises(ValueError):
        engine.detect_model_drift(behavior_engine, user_id=1)


def test_rejects_insufficient_drift_history(engine: LearningEngine) -> None:
    with pytest.raises(ValueError, match="Insufficient productivity history"):
        engine.detect_model_drift(FakeBehaviorEngine([50.0]), user_id=1)


def test_retrain_productivity_model_returns_metrics_patterns_and_report(engine: LearningEngine) -> None:
    behavior_engine = FakeBehaviorEngine([60.0, 70.0])

    result = engine.retrain_productivity_model(behavior_engine, user_id=5, days_back=14)

    assert result["metrics"] == {"mae": 1.5, "r2": 0.8}
    assert result["patterns"] == {"best_focus_hours": [9, 10]}
    assert result["report"] == {"summary": "ok"}
    assert behavior_engine.train_called == 1
    assert behavior_engine.patterns_called == 1
    assert behavior_engine.report_called == 1


@pytest.mark.parametrize("metrics", [None, {}, {"mae": math.nan}, {"mae": math.inf}, {"mae": "bad"}])
def test_retraining_rejects_malformed_metrics(engine: LearningEngine, metrics: Any) -> None:
    behavior_engine = FakeBehaviorEngine([60.0, 70.0], metrics=metrics)

    with pytest.raises(ValueError):
        engine.retrain_productivity_model(behavior_engine, user_id=1)


def test_retraining_rejects_malformed_patterns(engine: LearningEngine) -> None:
    behavior_engine = FakeBehaviorEngine([60.0, 70.0], patterns=["bad"])

    with pytest.raises(ValueError, match="Behavior patterns must be a dictionary"):
        engine.retrain_productivity_model(behavior_engine, user_id=1)


@pytest.mark.parametrize("report", [None, 123])
def test_retraining_rejects_malformed_report(engine: LearningEngine, report: Any) -> None:
    behavior_engine = FakeBehaviorEngine([60.0, 70.0], report=report)

    with pytest.raises(ValueError, match="Behavior report"):
        engine.retrain_productivity_model(behavior_engine, user_id=1)


def test_retrain_productivity_model_rejects_empty_history(engine: LearningEngine) -> None:
    with pytest.raises(ValueError, match="No completed tasks"):
        engine.retrain_productivity_model(FakeBehaviorEngine([]), user_id=1)


def test_update_rl_policy_delegates_to_scheduler(engine: LearningEngine) -> None:
    scheduler = FakeRLScheduler()
    tasks = [{"id": "a"}]

    result = engine.update_rl_policy(scheduler, tasks, None, episodes=3)

    assert result == {"episodes": 3, "updated": True}
    assert scheduler.calls == [{"tasks": tasks, "behavior_patterns": {}, "episodes": 3}]


def test_update_rl_policy_rejects_missing_scheduler(engine: LearningEngine) -> None:
    with pytest.raises(ValueError, match="rl_scheduler must provide train_agent"):
        engine.update_rl_policy(None, [{"id": "a"}], {}, episodes=1)


def test_update_rl_policy_rejects_scheduler_missing_method(engine: LearningEngine) -> None:
    with pytest.raises(ValueError, match="rl_scheduler must provide train_agent"):
        engine.update_rl_policy(object(), [{"id": "a"}], {}, episodes=1)


def test_update_rl_policy_rejects_invalid_inputs(engine: LearningEngine) -> None:
    scheduler = FakeRLScheduler()

    with pytest.raises(ValueError, match="tasks must be a list"):
        engine.update_rl_policy(scheduler, None, {}, episodes=1)

    with pytest.raises(ValueError, match="episodes must be greater than zero"):
        engine.update_rl_policy(scheduler, [], {}, episodes=0)

    with pytest.raises(ValueError, match="Each task must be a dictionary"):
        engine.update_rl_policy(scheduler, [{"id": "valid"}, "bad"], {}, episodes=1)

    with pytest.raises(ValueError, match="behavior_patterns must be a dictionary"):
        engine.update_rl_policy(scheduler, [{"id": "a"}], "bad", episodes=1)

    with pytest.raises(ValueError, match="episodes must be greater than zero"):
        engine.update_rl_policy(scheduler, [], {}, episodes=1.5)


@pytest.mark.parametrize("output", [None, {}, [], {"average_reward": math.nan}, {"final_reward": math.inf}])
def test_update_rl_policy_rejects_malformed_outputs(engine: LearningEngine, output: Any) -> None:
    with pytest.raises(ValueError):
        engine.update_rl_policy(FakeRLScheduler(output=output), [{"id": "a"}], {}, episodes=1)


def test_update_model_combines_drift_retraining_and_rl_update(engine: LearningEngine) -> None:
    behavior_engine = FakeBehaviorEngine([50.0] * 10 + [70.0] * 10)
    scheduler = FakeRLScheduler()

    result = engine.update_model(
        behavior_engine,
        scheduler,
        user_id=3,
    )

    assert set(result) == {"drift", "retraining", "rl_policy_update"}
    assert result["drift"]["drift_detected"] is True
    assert result["retraining"]["metrics"] == {"mae": 1.5, "r2": 0.8}
    assert result["rl_policy_update"] == {"episodes": 25, "updated": True}
    assert scheduler.calls[0]["tasks"] == behavior_engine.behavior_data_df.to_dict(orient="records")
    assert scheduler.calls[0]["behavior_patterns"] == {"best_focus_hours": [9, 10]}


def test_update_model_propagates_drift_failure(engine: LearningEngine) -> None:
    with pytest.raises(ValueError, match="Insufficient productivity history"):
        engine.update_model(FakeBehaviorEngine([50.0]), FakeRLScheduler(), user_id=1)


def test_update_model_propagates_retraining_failure(engine: LearningEngine) -> None:
    behavior_engine = FakeBehaviorEngine([50.0, 60.0], metrics={"mae": math.nan})

    with pytest.raises(ValueError):
        engine.update_model(behavior_engine, FakeRLScheduler(), user_id=1)


def test_update_model_propagates_rl_failure(engine: LearningEngine) -> None:
    behavior_engine = FakeBehaviorEngine([50.0, 60.0])

    with pytest.raises(ValueError):
        engine.update_model(behavior_engine, FakeRLScheduler(output={"average_reward": math.nan}), user_id=1)


def test_learning_workflow_is_deterministic(engine: LearningEngine) -> None:
    first = engine.detect_model_drift(FakeBehaviorEngine([50.0] * 10 + [60.0] * 10), user_id=1)
    second = engine.detect_model_drift(FakeBehaviorEngine([50.0] * 10 + [60.0] * 10), user_id=1)

    assert first == second
