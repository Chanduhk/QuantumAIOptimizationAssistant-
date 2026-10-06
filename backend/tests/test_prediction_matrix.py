from __future__ import annotations

import pytest

from backend.app.domain.optimization_input_contract import normalize_duration
from backend.app.domain.prediction_matrix import validate_prediction_matrix
from backend.app.domain.prediction_provenance import PredictionResult, PredictionStatus


def cell(task_id: str, hour: int, value: float) -> PredictionResult:
    return PredictionResult(
        task_id=task_id,
        candidate_start_hour=hour,
        value=value,
        score_unit="productivity_points",
        prediction_source=PredictionStatus.TRAINED_MODEL,
        model_trained=True,
        history_count=12,
        history_count_status="AVAILABLE",
        model_version="productivity-rf-v1",
        model_version_status="AVAILABLE",
        fallback_used=False,
        duration_input=normalize_duration(60, "minutes", "test_only_fixture"),
        validity=True,
        status=PredictionStatus.TRAINED_MODEL,
        optimizer_eligibility="ELIGIBLE_HEURISTIC_PROXY",
        feature_schema_version="productivity-features-v1",
        target_schema_version="heuristic-productivity-v1",
    )


def test_complete_nontrivial_matrix_validates_and_detects_assignment_interaction() -> None:
    result = validate_prediction_matrix(
        [cell("a", 9, 80), cell("a", 10, 70), cell("b", 9, 60), cell("b", 10, 85)],
        ["a", "b"], [9, 10],
    )
    assert result.nontriviality == "PASS"
    assert result.optimizer_eligible
    assert result.assignment_contrast == pytest.approx(35.0)


def test_separable_matrix_is_valid_but_not_proven_nontrivial() -> None:
    result = validate_prediction_matrix(
        [cell("a", 9, 80), cell("a", 10, 70), cell("b", 9, 60), cell("b", 10, 50)],
        ["a", "b"], [9, 10],
    )
    assert result.nontriviality == "NOT_PROVEN"
    assert not result.optimizer_eligible


def test_matrix_rejects_missing_or_cold_start_cells() -> None:
    with pytest.raises(ValueError, match="incomplete"):
        validate_prediction_matrix([cell("a", 9, 80)], ["a"], [9, 10])

    cold = PredictionResult(
        task_id="a", candidate_start_hour=10, value=80, score_unit="productivity_points",
        prediction_source=PredictionStatus.COLD_START_HEURISTIC, model_trained=False,
        history_count=0, history_count_status="AVAILABLE", model_version=None,
        model_version_status="MODEL_VERSION_NOT_AVAILABLE", fallback_used=True,
        duration_input=normalize_duration(60, "minutes", "test_only_fixture"), validity=True,
        status=PredictionStatus.COLD_START_HEURISTIC, optimizer_eligibility="COLD_START_NOT_ELIGIBLE",
    )
    with pytest.raises(ValueError, match="trained-model"):
        validate_prediction_matrix([cold], ["a"], [10])


def test_matrix_rejects_insufficient_or_inconsistent_training_evidence() -> None:
    insufficient = cell("a", 9, 80)
    insufficient = PredictionResult(
        **{**insufficient.__dict__, "history_count": 4}
    )
    with pytest.raises(ValueError, match="at least 5 verified training samples"):
        validate_prediction_matrix([insufficient], ["a"], [9])

    with pytest.raises(ValueError, match="mixes training sample evidence"):
        validate_prediction_matrix(
            [cell("a", 9, 80), PredictionResult(**{**cell("a", 10, 70).__dict__, "history_count": 13})],
            ["a"], [9, 10],
        )
