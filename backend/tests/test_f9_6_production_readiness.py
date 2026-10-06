"""F9.6 gate tests; fake training-frame counts are gate doubles, not model data."""

from types import SimpleNamespace

import pandas as pd
import pytest

from backend.app.orchestrator.ai_orchestrator import AIOrchestrator


def test_insufficient_history_keeps_model_and_production_pipeline_not_ready():
    model = SimpleNamespace(is_trained=False, compatibility_status="UNTRAINED", metadata=None)
    behavior = SimpleNamespace(
        productivity_model=model,
        active_user_id=17,
        raw_tasks_df=pd.DataFrame([{"unit_test_only": True}]),
        _build_training_frame=lambda: pd.DataFrame(index=range(4)),
        train_productivity_model=lambda: pytest.fail("must not train with fewer than five eligible rows"),
    )
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.behavior_engine = behavior
    with pytest.raises(ValueError, match="insufficient eligible real training history: 4/5"):
        orchestrator._ensure_optimization_model_ready()


def test_existing_versioned_training_path_is_used_when_real_builder_meets_threshold():
    model = SimpleNamespace(is_trained=False, compatibility_status="UNTRAINED", metadata=None)
    behavior = SimpleNamespace(
        productivity_model=model,
        active_user_id=17,
        raw_tasks_df=pd.DataFrame([{"unit_test_only": True}]),
        _build_training_frame=lambda: pd.DataFrame(index=range(5)),
    )

    def train_existing_path():
        model.is_trained = True
        model.compatibility_status = "OPTIMIZATION_COMPATIBLE"
        model.metadata = {"training_sample_count": 5}

    behavior.train_productivity_model = train_existing_path
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.behavior_engine = behavior
    assert orchestrator._ensure_optimization_model_ready() is model


def test_current_production_evidence_fails_closed_without_model_history():
    model = SimpleNamespace(is_trained=False, compatibility_status="UNTRAINED", metadata=None)
    behavior = SimpleNamespace(
        productivity_model=model,
        active_user_id=17,
        raw_tasks_df=pd.DataFrame([{"unit_test_only": True}]),
        _build_training_frame=lambda: pd.DataFrame(index=range(0)),
        train_productivity_model=lambda: pytest.fail("insufficient data cannot train"),
    )
    orchestrator = AIOrchestrator.__new__(AIOrchestrator)
    orchestrator.behavior_engine = behavior
    evidence = orchestrator._build_hybrid_optimization_evidence([])
    assert evidence["prediction_matrix_status"] == "NOT_READY"
    assert evidence["nontriviality_status"] == "NOT_PROVEN"
    assert evidence["quantum_suitability"]["status"] == "NOT_READY"
    assert evidence["quantum_candidate"]["candidate"] is None
    assert "0/5" in evidence["quantum_suitability"]["reasons"][0]
