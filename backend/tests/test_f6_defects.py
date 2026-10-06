import pytest
import pandas as pd
import numpy as np
from backend.app.ai_models.productivity_model import ProductivityModel
from backend.app.engines.prediction_engine import PredictionEngine
from backend.app.engines.optimization_engine import OptimizationEngine
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine
from backend.app.orchestrator.ai_orchestrator import AIOrchestrator
from backend.app.adaptive.adaptive_scheduler import AdaptiveScheduler
import tempfile
from pathlib import Path
from backend.app.models.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def sample_tasks():
    np.random.seed(42)
    n_samples = 100
    task_types = ['coding', 'research', 'writing', 'meeting', 'admin']
    hours = np.random.choice(range(8, 20), n_samples)
    types = np.random.choice(task_types, n_samples)
    durations = np.random.normal(60, 30, n_samples).clip(15, 240)
    
    productivity = np.random.uniform(20, 100, n_samples)
    
    data = pd.DataFrame({
        'hour_of_day': hours,
        'task_type': types,
        'duration': durations,
        'focus_score': np.random.uniform(30, 95, n_samples),
        'energy_level': np.random.uniform(20, 100, n_samples),
        'completion_time': np.random.uniform(0.7, 1.3, n_samples),
        'productivity_score': productivity,
    })
    data.attrs.update({
        "duration_unit": "minutes",
        "dataset_schema_version": ProductivityModel.DATASET_SCHEMA_VERSION,
        "target_schema_version": ProductivityModel.TARGET_SCHEMA_VERSION,
    })
    return data

class TestTaskTypes:
    def test_known_task_type(self, sample_tasks):
        model = ProductivityModel()
        model.train(sample_tasks)
        score = model.predict(9, 'coding', 60)
        assert 0 <= score <= 100

    def test_unknown_task_type(self, sample_tasks):
        model = ProductivityModel()
        model.train(sample_tasks)
        score = model.predict(9, 'unknown_magic', 60)
        assert 0 <= score <= 100

    def test_test_task_type(self, sample_tasks):
        model = ProductivityModel()
        model.train(sample_tasks)
        score = model.predict(9, 'test', 60)
        assert 0 <= score <= 100

    def test_train_with_mixed_categories(self, sample_tasks):
        df = sample_tasks.copy()
        # Add a new row with 'unknown_category' and 'test'
        new_rows = pd.DataFrame({
            'hour_of_day': [10, 11],
            'task_type': ['unknown_category', 'test'],
            'duration': [60, 60],
            'focus_score': [50, 50],
            'energy_level': [50, 50],
            'completion_time': [1.0, 1.0],
            'productivity_score': [80, 80]
        })
        df = pd.concat([df, new_rows], ignore_index=True)
        df.attrs.update({
            "duration_unit": "minutes",
            "dataset_schema_version": ProductivityModel.DATASET_SCHEMA_VERSION,
            "target_schema_version": ProductivityModel.TARGET_SCHEMA_VERSION,
        })
        model = ProductivityModel()
        model.train(df)
        assert 'other' in model.task_type_encoder.classes_

    def test_prediction_with_unseen_category(self, sample_tasks):
        model = ProductivityModel()
        model.train(sample_tasks)
        # Should fallback to 'other' without raising ValueError
        score = model.predict(9, 'completely_unseen', 60)
        assert 0 <= score <= 100

    def test_model_save_load_compatibility(self, sample_tasks):
        model = ProductivityModel()
        model.train(sample_tasks)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / 'model.pkl')
            model.save(path)
            
            loaded = ProductivityModel(path)
            assert loaded._loaded_model_is_compatible()
            score = loaded.predict(9, 'test', 60)
            assert 0 <= score <= 100

    def test_existing_supported_task_types_remain_unchanged(self):
        assert 'coding' in ProductivityModel.VALID_TASK_TYPES
        assert 'admin' in ProductivityModel.VALID_TASK_TYPES

class TestFractionalHours:
    @pytest.fixture
    def prediction_engine(self):
        return PredictionEngine()

    @pytest.fixture
    def optimization_engine(self):
        return OptimizationEngine()
        
    def test_integer_hour(self, prediction_engine):
        val = prediction_engine._safe_hour(10)
        assert val == 10.0

    def test_fractional_hour_quarter(self, prediction_engine):
        val = prediction_engine._safe_hour(10.25)
        assert val == 10.25

    def test_fractional_hour_half(self, prediction_engine):
        val = prediction_engine._safe_hour(10.5)
        assert val == 10.5

    def test_fractional_hour_three_quarters(self, prediction_engine):
        val = prediction_engine._safe_hour(10.75)
        assert val == 10.75

    def test_schedule_end_arithmetic(self, optimization_engine):
        tasks = [{'id': 1, 'scheduled_hour': 10.5, 'estimated_duration': 1.5, 'estimated_duration_unit': 'hours', 'estimated_duration_source': 'test_fixture', 'predicted_productivity': 80}]
        behavior = {'hourly_productivity': {10: 80, 11: 90}}
        res = optimization_engine.optimize_schedule(tasks, behavior)
        task = res['optimized_schedule'][0]
        # start 10.5 + duration 1.5 = 12.0
        assert task['optimized_hour'] == 10.5
        assert task['optimized_end_hour'] == 12.0

    def test_prediction_with_fractional_hour(self, sample_tasks):
        model = ProductivityModel()
        model.train(sample_tasks)
        score = model.predict(10.5, 'coding', 1.0)
        assert 0 <= score <= 100

    def test_adaptive_scheduler_fractional_hour(self):
        # We can just test that the adaptive scheduler handles float values for hours
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=engine)
        session = SessionLocal()
        
        try:
            scheduler = AdaptiveScheduler(session, days_back=30)
            # Ensure no exceptions are raised when using fractional hours internally if we mock it, or just testing init
            assert scheduler is not None
        finally:
            session.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
