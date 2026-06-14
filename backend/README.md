# Behavior Intelligence Engine

A production-ready machine learning system for analyzing user productivity patterns and behavioral characteristics. Part of a personal AI assistant backend built with **FastAPI** and **PostgreSQL**.

## Overview

The Behavior Intelligence Engine learns from historical task data to:

- **Detect best focus hours** - Identify when you're most productive
- **Predict task completion speed** - Estimate how long tasks actually take
- **Analyze productivity trends** - Understand patterns by task type and time
- **Model energy curves** - Recognize daily energy fluctuations
- **Predict future productivity** - Estimate productivity for any planned task

## Architecture

```
backend/
├── app/
│   ├── models/
│   │   ├── task.py              # Task database schema
│   │   └── behavior_data.py      # Behavioral insights model
│   ├── database/
│   │   └── db.py                # Database configuration
│   └── services/
│       └── behavior_engine.py    # Core intelligence engine
├── ai_models/
│   └── productivity_model.py     # ML model (RandomForestRegressor)
├── requirements.txt
├── .env.example
└── README.md
```

## Key Components

### 1. **Task Model** (`models/task.py`)

Stores completed tasks with metadata for behavioral analysis.

**Fields:**
- `id`: Unique task ID
- `user_id`: User identifier
- `title`: Task description
- `task_type`: Type (coding, research, writing, meeting, planning, admin, learning)
- `priority`: Priority level (1-5)
- `estimated_duration`: Expected time (minutes)
- `actual_duration`: Actual time taken (minutes)
- `start_time`: When task started
- `end_time`: When task completed
- `completed`: Success indicator

### 2. **BehaviorData Model** (`models/behavior_data.py`)

Processed behavioral analytics derived from tasks.

**Fields:**
- `id`: Record ID
- `user_id`: User identifier
- `task_id`: Referenced task
- `hour_of_day`: Hour of completion (0-23)
- `task_type`: Type of task
- `duration`: Actual duration (minutes)
- `focus_score`: Quality metric (0-100)
- `energy_level`: Energy at task time (0-100)
- `completion_time`: Ratio actual/estimated
- `productivity_score`: Composite metric (0-100)

### 3. **ProductivityModel** (`ai_models/productivity_model.py`)

Machine learning model using **RandomForestRegressor** to predict productivity.

**Features:**
- Hour of day (0-23)
- Task type (encoded)
- Task duration (minutes)

**Target:**
- Productivity score (0-100)

**Methods:**
- `train(data)` - Train on historical data
- `predict(hour, task_type, duration)` - Single prediction
- `predict_batch(tasks)` - Multiple predictions
- `save(path)` - Persist model to disk
- `load(path)` - Load saved model
- `get_feature_importance()` - Feature analysis

### 4. **BehaviorIntelligenceEngine** (`services/behavior_engine.py`)

Orchestrates the entire analysis pipeline.

**Core Methods:**

| Method | Purpose |
|--------|---------|
| `collect_behavior_data(user_id, days_back)` | Load historical tasks from database |
| `extract_features(df)` | Transform raw data into ML features |
| `train_productivity_model(df, test_size)` | Train RandomForest model |
| `get_user_patterns(user_id)` | Extract behavioral insights |
| `predict_task_productivity(hour, type, duration)` | Predict single task productivity |
| `generate_report()` | Human-readable analysis |

## Installation

### 1. Clone and Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Database

Copy environment template and configure:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# PostgreSQL (Production)
DATABASE_URL=postgresql://user:password@localhost:5432/behavior_db

# SQLite (Development)
DATABASE_URL=sqlite:///./behavior_engine.db
```

### 3. Initialize Database

```python
from app.database import init_db
from app.models import Task, BehaviorData

# Initialize with your database URL
db = init_db("sqlite:///./behavior_engine.db")

# Create tables
from app.models.task import Base as TaskBase
from app.models.behavior_data import Base as BehaviorBase

db.create_tables(TaskBase)
db.create_tables(BehaviorBase)
```

## Usage

### Quick Start: Training with Sample Data

```python
from backend.app.services import BehaviorIntelligenceEngine
from backend.app.services.behavior_engine import example_usage_with_sample_data

# Run complete example with generated sample data
engine = example_usage_with_sample_data()
```

This demonstrates:
1. Feature extraction
2. Model training
3. Pattern analysis
4. Predictions
5. Report generation

### Advanced Usage: With Database

```python
from backend.app.services import BehaviorIntelligenceEngine
from backend.app.database import get_db_instance

# Get database session
db = get_db_instance()
session = db.get_session()

# Create engine
engine = BehaviorIntelligenceEngine(session=session)

# Collect historical data (last 90 days)
engine.collect_behavior_data(user_id=1, days_back=90)

# Extract features
features = engine.extract_features()

# Train model
metrics = engine.train_productivity_model(features)
print(f"Model R² Score: {metrics['accuracy']:.3f}")

# Get patterns
patterns = engine.get_user_patterns()
print(f"Best focus hours: {patterns['best_focus_hours']}")
print(f"Preferred tasks: {patterns['preferred_task_types']}")

# Predict task productivity
score = engine.predict_task_productivity(
    hour=9,
    task_type='coding',
    duration=60
)
print(f"Predicted productivity: {score}/100")

# Save model
engine.productivity_model.save('./models/productivity.pkl')
```

### Feature Extraction Pipeline

The engine automatically extracts intelligent features:

```python
# Raw task data → Behavioral features
# 
# Input columns:
# - hour_of_day: When task occurred
# - task_type: Task category  
# - actual_duration: Time spent
# - estimated_duration: Time predicted
# - priority: Task importance
#
# Output features:
# - hour_of_day: Hour (0-23)
# - task_type_encoded: Numeric category
# - duration: Actual time
# - completion_ratio: actual/estimated
# - focus_score: Quality metric (0-100)
# - energy_level: Energy curve (0-100)
# - productivity_score: Composite metric (0-100)
```

### Machine Learning Model

The RandomForestRegressor learns patterns:

```
Hour of Day (9-18)
       ↓
Task Type (coding, research, etc)  → [Random Forest] → Productivity Score
       ↓                               (100 trees)      (0-100)
Duration (30-180 min)
```

**Model Parameters:**
- `n_estimators`: 100 trees
- `max_depth`: 15 levels
- `min_samples_split`: 5
- `min_samples_leaf`: 2

## Integration with FastAPI

### Basic Setup

```python
# main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db_instance
from app.services import BehaviorIntelligenceEngine

app = FastAPI(title="Behavior Intelligence API")

# Initialize database
db_config = get_db_instance()

@app.on_event("startup")
async def startup():
    # Initialize models, create tables, etc.
    from app.models.task import Base
    db_config.create_tables(Base)

# Dependency
def get_db():
    return db_config.get_session_dependency()

@app.post("/api/v1/behavior/train")
async def train_model(user_id: int, db: Session = Depends(get_db)):
    """Train productivity model for user."""
    try:
        engine = BehaviorIntelligenceEngine(session=db)
        engine.collect_behavior_data(user_id)
        features = engine.extract_features()
        metrics = engine.train_productivity_model(features)
        return {
            "status": "success",
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v1/behavior/patterns/{user_id}")
async def get_patterns(user_id: int, db: Session = Depends(get_db)):
    """Get user productivity patterns."""
    engine = BehaviorIntelligenceEngine(session=db)
    engine.collect_behavior_data(user_id)
    engine.extract_features()
    patterns = engine.get_user_patterns(user_id)
    return patterns

@app.post("/api/v1/behavior/predict")
async def predict_productivity(
    user_id: int,
    hour: int,
    task_type: str,
    duration: float,
    db: Session = Depends(get_db)
):
    """Predict productivity for hypothetical task."""
    engine = BehaviorIntelligenceEngine(session=db)
    score = engine.predict_task_productivity(hour, task_type, duration)
    return {
        "hour": hour,
        "task_type": task_type,
        "duration": duration,
        "predicted_productivity": score
    }

@app.get("/api/v1/behavior/report/{user_id}")
async def get_report(user_id: int, db: Session = Depends(get_db)):
    """Get human-readable behavior report."""
    engine = BehaviorIntelligenceEngine(session=db)
    engine.collect_behavior_data(user_id)
    engine.extract_features()
    engine.get_user_patterns(user_id)
    report = engine.generate_report()
    return {"report": report}
```

### Running FastAPI Server

```bash
# Development
uvicorn main:app --reload

# Production
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

## Output Examples

### User Patterns

```python
{
    "best_focus_hours": [9, 10, 11],
    "peak_hours": [10, 11, 9],
    "low_energy_hours": [14, 15, 13],
    "average_task_duration": 67.8,
    "average_duration_by_type": {
        "coding": 85.3,
        "research": 72.1,
        "writing": 45.6
    },
    "preferred_task_types": ["coding", "research", "writing"],
    "completion_rates": {
        "coding": 92.5,
        "research": 88.3,
        "writing": 95.1
    },
    "energy_curve": {
        0: 30.0, 1: 25.0, ..., 23: 35.0
    },
    "productivity_trend": "increasing",
    "total_tasks_analyzed": 200,
    "analysis_timestamp": "2024-01-15T10:23:45.123456"
}
```

### Predictions

```python
# Predict task productivity
predictions = engine.predict_batch([
    {"hour": 9, "task_type": "coding", "duration": 90},     # → 78.5
    {"hour": 14, "task_type": "meeting", "duration": 30},  # → 42.1
    {"hour": 16, "task_type": "writing", "duration": 60},  # → 71.3
])
```

### Generated Report

```
================== USER BEHAVIOR ANALYSIS REPORT ==================

Analysis Timestamp: 2024-01-15T10:23:45.123456
Total Tasks Analyzed: 200

PRODUCTIVITY PATTERNS
--------------------------------------------------
Best Focus Hours: 9, 10, 11:00
Low Energy Hours: 14, 15, 13:00
Productivity Trend: INCREASING

TASK ANALYSIS
--------------------------------------------------
Average Task Duration: 67.8 minutes
Preferred Task Types: coding, research, writing

Duration by Task Type:
  coding: 85.3
  research: 72.1
  writing: 45.6

Completion Rates by Type:
  coding: 92.5%
  research: 88.3%
  writing: 95.1%

ENERGY PROFILE
--------------------------------------------------
Peak Energy Hours: 10, 11, 9:00
  08:00 │████████████████    │ 80%
  11:00 │████████████████████│ 100%
  14:00 │██████              │ 60%
  17:00 │████████████████    │ 80%
```

## Extension Points

The architecture is designed for easy extension:

### Add New Features

```python
# In behavior_engine.py extract_features()
features['my_metric'] = compute_metric(df)
```

### Add New ML Models

```python
# Create models/performance_model.py
class PerformanceModel:
    def __init__(self):
        self.model = XGBRegressor()  # Different model
    
    def train(self, X, y):
        self.model.fit(X, y)
    
    def predict(self, X):
        return self.model.predict(X)
```

### Custom Analytics

```python
class AdvancedEngine(BehaviorIntelligenceEngine):
    def get_focus_score(self):
        """Custom focus analysis."""
        pass
    
    def predict_best_schedule(self):
        """Generate optimal daily schedule."""
        pass
```

## Production Considerations

### Database

- Use **PostgreSQL** in production
- Enable connection pooling
- Set up regular backups
- Monitor query performance

### Model Management

- Retrain models periodically (weekly/monthly)
- Version saved models with timestamps
- A/B test new model architectures
- Monitor prediction accuracy over time

### Performance

- Cache user patterns (Redis/Memcached)
- Use async database queries
- Batch predictions where possible
- Monitor API response times

### Monitoring

- Log all predictions for audit trail
- Track model drift
- Monitor feature distributions
- Alert on anomalies

## Troubleshooting

### Insufficient Data

**Error:** "Need at least 10 samples for training"

**Solution:** Ensure user has completed at least 10 tasks in database

### Model Not Trained

**Error:** "Model must be trained before making predictions"

**Solution:** Call `train_productivity_model()` before `predict_task_productivity()`

### Unknown Task Type

**Warning:** "Unknown task type: xyz, using most common"

**Solution:** Only use predefined task types or extend TaskType enum

## Future Enhancements

- [ ] Time series forecasting (LSTM/Prophet)
- [ ] Clustering users with similar patterns
- [ ] Real-time productivity monitoring
- [ ] Context-aware recommendations
- [ ] Multi-factor authentication
- [ ] Privacy-preserving analytics
- [ ] Mobile app integration
- [ ] Calendar sync and auto-scheduling

## Dependencies

- **FastAPI**: Web framework
- **SQLAlchemy**: ORM
- **PostgreSQL**: Production database
- **Pandas**: Data processing
- **NumPy**: Numerical computing
- **Scikit-learn**: Machine learning
- **Joblib**: Model serialization

## License

MIT License - See LICENSE file

## Support

For issues, questions, or contributions:
1. Check existing issues
2. Create detailed bug reports
3. Include sample data for reproducibility
4. Follow code style guidelines

---

**Created:** 2024-01-15  
**Version:** 1.0.0  
**Status:** Production Ready
