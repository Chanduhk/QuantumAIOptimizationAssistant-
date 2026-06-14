"""
Comprehensive Test Suite for Behavior Intelligence Engine

Tests all components including:
- Data collection and feature extraction
- Model training and predictions
- Pattern analysis and insights
- API integration
- Edge cases and error handling

Run with: python -m pytest test_behavior_engine.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.services.behavior_engine import (
    BehaviorIntelligenceEngine
)
from backend.app.ai_models.productivity_model import ProductivityModel
from backend.app.models.base import Base


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_tasks():
    """Create sample task data for testing."""
    np.random.seed(42)
    n_samples = 100
    
    task_types = ['coding', 'research', 'writing', 'meeting', 'admin']
    hours = np.random.choice(range(8, 20), n_samples)
    types = np.random.choice(task_types, n_samples)
    durations = np.random.normal(60, 30, n_samples).clip(15, 240)
    
    # Create productivity based on patterns
    productivity = np.zeros(n_samples)
    for i in range(n_samples):
        if 8 <= hours[i] <= 11:
            productivity[i] += 30
        elif 13 <= hours[i] <= 15:
            productivity[i] -= 15
        else:
            productivity[i] += 20
        
        if types[i] == 'coding':
            productivity[i] += 25
        elif types[i] == 'meeting':
            productivity[i] -= 10
    
    productivity = np.clip(productivity + 60, 20, 100)
    
    data = pd.DataFrame({
        'hour_of_day': hours,
        'task_type': types,
        'duration': durations,
        'focus_score': np.random.uniform(30, 95, n_samples),
        'energy_level': np.random.uniform(20, 100, n_samples),
        'completion_time': np.random.uniform(0.7, 1.3, n_samples),
        'productivity_score': productivity,
    })
    
    return data


@pytest.fixture
def sample_database():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def productivity_model():
    """Create a productivity model instance."""
    return ProductivityModel()


@pytest.fixture
def behavior_engine(sample_database):
    """Create a behavior engine instance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = BehaviorIntelligenceEngine(session=sample_database, model_directory=tmpdir)
        engine._set_active_user(1)
        yield engine


# ============================================================================
# PRODUCTIVITY MODEL TESTS
# ============================================================================

class TestProductivityModel:
    """Tests for the ProductivityModel class."""
    
    def test_model_initialization(self, productivity_model):
        """Test model initializes correctly."""
        assert productivity_model.model is None
        assert not productivity_model.is_trained
        assert productivity_model.feature_names is not None
    
    def test_model_training(self, productivity_model, sample_tasks):
        """Test model training works correctly."""
        metrics = productivity_model.train(sample_tasks)
        
        assert productivity_model.is_trained
        assert 'accuracy' in metrics
        assert 'mae' in metrics
        assert 'rmse' in metrics
        assert 0 <= metrics['accuracy'] <= 1
    
    def test_single_prediction(self, productivity_model, sample_tasks):
        """Test single task prediction."""
        productivity_model.train(sample_tasks)
        
        score = productivity_model.predict(hour=9, task_type='coding', duration=60)
        
        assert 0 <= score <= 100
        assert isinstance(score, float)
    
    def test_batch_prediction(self, productivity_model, sample_tasks):
        """Test batch prediction."""
        productivity_model.train(sample_tasks)
        
        tasks = [
            {'hour': 9, 'task_type': 'coding', 'duration': 60},
            {'hour': 14, 'task_type': 'meeting', 'duration': 30},
            {'hour': 16, 'task_type': 'writing', 'duration': 90},
        ]
        
        predictions = productivity_model.predict_batch(tasks)
        
        assert len(predictions) == 3
        assert all(0 <= p <= 100 for p in predictions)
    
    def test_invalid_hour(self, productivity_model, sample_tasks):
        """Test prediction with invalid hour."""
        productivity_model.train(sample_tasks)
        
        with pytest.raises(ValueError):
            productivity_model.predict(hour=25, task_type='coding', duration=60)
    
    def test_invalid_duration(self, productivity_model, sample_tasks):
        """Test prediction with invalid duration."""
        productivity_model.train(sample_tasks)
        
        with pytest.raises(ValueError):
            productivity_model.predict(hour=9, task_type='coding', duration=0)
    
    def test_feature_importance(self, productivity_model, sample_tasks):
        """Test feature importance extraction."""
        productivity_model.train(sample_tasks)
        
        importance = productivity_model.get_feature_importance()
        
        assert len(importance) > 0
        assert all(isinstance(v, float) for v in importance.values())
    
    def test_model_save_load(self, productivity_model, sample_tasks):
        """Test model persistence."""
        productivity_model.train(sample_tasks)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = str(Path(tmpdir) / "model.pkl")
            
            # Save
            productivity_model.save(model_path)
            assert Path(model_path).exists()
            
            # Load
            new_model = ProductivityModel(model_path)
            assert new_model.is_trained
            
            # Predictions should be identical
            pred1 = productivity_model.predict(9, 'coding', 60)
            pred2 = new_model.predict(9, 'coding', 60)
            assert pred1 == pred2


# ============================================================================
# BEHAVIOR ENGINE TESTS
# ============================================================================

class TestBehaviorIntelligenceEngine:
    """Tests for the BehaviorIntelligenceEngine class."""
    
    def test_engine_initialization(self, behavior_engine):
        """Test engine initializes correctly."""
        assert behavior_engine.session is not None
        assert behavior_engine.raw_tasks_df.empty
        assert behavior_engine.behavior_data_df.empty
    
    def test_feature_extraction(self, behavior_engine, sample_tasks):
        """Test feature extraction."""
        raw_tasks = pd.DataFrame({
            'id': range(1, len(sample_tasks) + 1),
            'user_id': [1] * len(sample_tasks),
            'title': [f'Task {i}' for i in range(1, len(sample_tasks) + 1)],
            'task_type': sample_tasks['task_type'],
            'priority': np.random.randint(1, 6, len(sample_tasks)),
            'estimated_duration': sample_tasks['duration'] * 0.9,
            'actual_duration': sample_tasks['duration'],
            'start_time': [datetime.now() - timedelta(hours=i) for i in range(len(sample_tasks))],
            'end_time': [datetime.now() - timedelta(hours=i-1) for i in range(len(sample_tasks))],
            'completed': [True] * len(sample_tasks),
            'hour_of_day': sample_tasks['hour_of_day'],
        })
        
        behavior_engine.raw_tasks_df = raw_tasks
        features = behavior_engine.extract_features()
        
        assert features is not None
        assert len(features) == len(sample_tasks)
        assert 'productivity_score' in features.columns
        assert 'focus_score' in features.columns
        assert 'energy_level' in features.columns
    
    def test_model_training(self, behavior_engine, sample_tasks):
        """Test model training through engine."""
        raw_tasks = pd.DataFrame({
            'id': range(1, len(sample_tasks) + 1),
            'user_id': [1] * len(sample_tasks),
            'title': [f'Task {i}' for i in range(1, len(sample_tasks) + 1)],
            'task_type': sample_tasks['task_type'],
            'priority': np.random.randint(1, 6, len(sample_tasks)),
            'estimated_duration': sample_tasks['duration'] * 0.9,
            'actual_duration': sample_tasks['duration'],
            'start_time': [datetime.now() for i in range(len(sample_tasks))],
            'end_time': [datetime.now() for i in range(len(sample_tasks))],
            'completed': [True] * len(sample_tasks),
            'hour_of_day': sample_tasks['hour_of_day'],
        })
        
        behavior_engine.raw_tasks_df = raw_tasks
        features = behavior_engine.extract_features()
        metrics = behavior_engine.train_productivity_model()
        
        assert metrics['accuracy'] is not None
        assert metrics['mae'] is not None
        assert metrics['rmse'] is not None
    
    def test_pattern_extraction(self, behavior_engine, sample_tasks):
        """Test pattern extraction."""
        raw_tasks = pd.DataFrame({
            'id': range(1, len(sample_tasks) + 1),
            'user_id': [1] * len(sample_tasks),
            'title': [f'Task {i}' for i in range(1, len(sample_tasks) + 1)],
            'task_type': sample_tasks['task_type'],
            'priority': np.random.randint(1, 6, len(sample_tasks)),
            'estimated_duration': sample_tasks['duration'] * 0.9,
            'actual_duration': sample_tasks['duration'],
            'start_time': [datetime.now() - timedelta(hours=i) for i in range(len(sample_tasks))],
            'end_time': [datetime.now() - timedelta(hours=i-1) for i in range(len(sample_tasks))],
            'completed': [True] * len(sample_tasks),
            'hour_of_day': sample_tasks['hour_of_day'],
        })
        
        behavior_engine.raw_tasks_df = raw_tasks
        behavior_engine.extract_features()
        patterns = behavior_engine.get_user_patterns()
        
        assert 'best_focus_hours' in patterns
        assert 'hourly_productivity' in patterns
        assert 'preferred_task_types' in patterns
        assert 'productivity_by_task_type' in patterns
        assert isinstance(patterns['best_focus_hours'], list)
    
    def test_predictions(self, behavior_engine, sample_tasks):
        """Test productivity predictions."""
        raw_tasks = pd.DataFrame({
            'id': range(1, len(sample_tasks) + 1),
            'user_id': [1] * len(sample_tasks),
            'title': [f'Task {i}' for i in range(1, len(sample_tasks) + 1)],
            'task_type': sample_tasks['task_type'],
            'priority': np.random.randint(1, 6, len(sample_tasks)),
            'estimated_duration': sample_tasks['duration'] * 0.9,
            'actual_duration': sample_tasks['duration'],
            'start_time': [datetime.now() for i in range(len(sample_tasks))],
            'end_time': [datetime.now() for i in range(len(sample_tasks))],
            'completed': [True] * len(sample_tasks),
            'hour_of_day': sample_tasks['hour_of_day'],
        })
        
        behavior_engine.raw_tasks_df = raw_tasks
        behavior_engine.extract_features()
        behavior_engine.train_productivity_model()
        
        score = behavior_engine.predict_task_productivity(9, 'coding', 60)
        
        assert 0 <= score <= 100
    
    def test_report_generation(self, behavior_engine, sample_tasks):
        """Test report generation."""
        raw_tasks = pd.DataFrame({
            'id': range(1, len(sample_tasks) + 1),
            'user_id': [1] * len(sample_tasks),
            'title': [f'Task {i}' for i in range(1, len(sample_tasks) + 1)],
            'task_type': sample_tasks['task_type'],
            'priority': np.random.randint(1, 6, len(sample_tasks)),
            'estimated_duration': sample_tasks['duration'] * 0.9,
            'actual_duration': sample_tasks['duration'],
            'start_time': [datetime.now() for i in range(len(sample_tasks))],
            'end_time': [datetime.now() for i in range(len(sample_tasks))],
            'completed': [True] * len(sample_tasks),
            'hour_of_day': sample_tasks['hour_of_day'],
        })
        
        behavior_engine.raw_tasks_df = raw_tasks
        behavior_engine.extract_features()
        behavior_engine.get_user_patterns()
        report = behavior_engine.generate_report()
        
        assert isinstance(report, str)
        assert len(report) > 0
        assert 'Quantum Life AI Behavior Report' in report


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_workflow(self, behavior_engine, sample_tasks):
        """Test complete analysis workflow."""
        # Setup
        raw_tasks = pd.DataFrame({
            'id': range(1, len(sample_tasks) + 1),
            'user_id': [1] * len(sample_tasks),
            'title': [f'Task {i}' for i in range(1, len(sample_tasks) + 1)],
            'task_type': sample_tasks['task_type'],
            'priority': np.random.randint(1, 6, len(sample_tasks)),
            'estimated_duration': sample_tasks['duration'] * 0.9,
            'actual_duration': sample_tasks['duration'],
            'start_time': [datetime.now() - timedelta(hours=i) for i in range(len(sample_tasks))],
            'end_time': [datetime.now() - timedelta(hours=i-1) for i in range(len(sample_tasks))],
            'completed': [True] * len(sample_tasks),
            'hour_of_day': sample_tasks['hour_of_day'],
        })
        
        # Complete workflow
        behavior_engine.raw_tasks_df = raw_tasks
        
        # 1. Extract features
        features = behavior_engine.extract_features()
        assert features is not None
        
        # 2. Train model
        metrics = behavior_engine.train_productivity_model()
        assert metrics['accuracy'] is not None
        
        # 3. Get patterns
        patterns = behavior_engine.get_user_patterns()
        assert patterns is not None
        
        # 4. Make predictions
        score = behavior_engine.predict_task_productivity(9, 'coding', 60)
        assert 0 <= score <= 100
        
        # 5. Generate report
        report = behavior_engine.generate_report()
        assert 'Quantum Life AI Behavior Report' in report
    
    def test_different_task_types(self, behavior_engine, sample_tasks):
        """Test engine handles various task types."""
        task_types = ['coding', 'research', 'writing', 'meeting', 'admin', 'planning']
        
        raw_tasks = pd.DataFrame({
            'id': range(1, len(sample_tasks) + 1),
            'user_id': [1] * len(sample_tasks),
            'title': [f'Task {i}' for i in range(1, len(sample_tasks) + 1)],
            'task_type': sample_tasks['task_type'],
            'priority': np.random.randint(1, 6, len(sample_tasks)),
            'estimated_duration': sample_tasks['duration'] * 0.9,
            'actual_duration': sample_tasks['duration'],
            'start_time': [datetime.now() for i in range(len(sample_tasks))],
            'end_time': [datetime.now() for i in range(len(sample_tasks))],
            'completed': [True] * len(sample_tasks),
            'hour_of_day': sample_tasks['hour_of_day'],
        })
        
        behavior_engine.raw_tasks_df = raw_tasks
        features = behavior_engine.extract_features()
        behavior_engine.train_productivity_model()
        
        # Predict for each task type
        for task_type in task_types:
            if task_type in sample_tasks['task_type'].values:
                score = behavior_engine.predict_task_productivity(9, task_type, 60)
                assert 0 <= score <= 100


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and edge cases."""
    
    def test_insufficient_training_data(self, productivity_model):
        """Test error when insufficient training data."""
        small_data = pd.DataFrame({
            'hour_of_day': [9, 10],
            'task_type': ['coding', 'writing'],
            'duration': [60, 45],
            'productivity_score': [80, 75],
        })
        
        with pytest.raises(ValueError):
            productivity_model.train(small_data)
    
    def test_predict_before_training(self, productivity_model):
        """Test error when predicting before training."""
        with pytest.raises(ValueError):
            productivity_model.predict(9, 'coding', 60)
    
    def test_missing_required_columns(self, behavior_engine, sample_tasks):
        """Test error with missing required columns."""
        incomplete_data = sample_tasks.drop(columns=['productivity_score'])
        behavior_engine.raw_tasks_df = incomplete_data
        
        with pytest.raises(ValueError):
            behavior_engine.extract_features()
    
    def test_empty_dataframe(self, behavior_engine):
        """Test error with empty dataframe."""
        empty_df = pd.DataFrame()
        behavior_engine.raw_tasks_df = empty_df
        
        with pytest.raises(ValueError):
            behavior_engine.extract_features()


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Tests for performance and scalability."""
    
    def test_large_dataset(self, productivity_model):
        """Test handling of large datasets."""
        # Create a large dataset (1000 samples)
        np.random.seed(42)
        large_data = pd.DataFrame({
            'hour_of_day': np.random.choice(range(8, 20), 1000),
            'task_type': np.random.choice(['coding', 'research', 'writing'], 1000),
            'duration': np.random.normal(60, 30, 1000).clip(15, 240),
            'focus_score': np.random.uniform(30, 95, 1000),
            'energy_level': np.random.uniform(20, 100, 1000),
            'completion_time': np.random.uniform(0.7, 1.3, 1000),
            'productivity_score': np.random.uniform(20, 100, 1000),
        })
        
        # Should train successfully
        metrics = productivity_model.train(large_data)
        assert metrics['samples'] > 800  # Most used for training
    
    def test_batch_predictions_performance(self, productivity_model, sample_tasks):
        """Test batch prediction performance."""
        productivity_model.train(sample_tasks)
        
        # Create 100 tasks to predict
        tasks = [
            {'hour': np.random.randint(8, 20), 'task_type': 'coding', 'duration': 60}
            for _ in range(100)
        ]
        
        predictions = productivity_model.predict_batch(tasks)
        assert len(predictions) == 100


if __name__ == "__main__":
    """Run tests with: python -m pytest test_behavior_engine.py -v"""
    pytest.main([__file__, "-v", "--tb=short"])
