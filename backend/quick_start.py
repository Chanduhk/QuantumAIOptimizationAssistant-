"""
Quick Start Guide for Behavior Intelligence Engine

This script demonstrates how to quickly set up and use the system
with minimal configuration.
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def quick_start_demo():
    """Run a quick demonstration of the system."""
    
    print("=" * 80)
    print("BEHAVIOR INTELLIGENCE ENGINE - QUICK START DEMO")
    print("=" * 80)
    print()
    
    # Import after path setup
    from backend.app.services import BehaviorIntelligenceEngine
    
    print("Step 1: Creating sample task data...")
    print("-" * 80)
    
    # Generate sample data
    np.random.seed(42)
    n_samples = 150
    
    task_types = ['coding', 'research', 'writing', 'meeting', 'admin']
    hours = np.random.choice(range(8, 20), n_samples)
    types = np.random.choice(task_types, n_samples)
    durations = np.random.normal(60, 30, n_samples).clip(15, 240)
    
    # Create productivity with realistic patterns
    productivity = np.zeros(n_samples)
    for i in range(n_samples):
        hour = hours[i]
        task_type = types[i]
        
        # Morning productivity boost
        if 8 <= hour <= 11:
            productivity[i] += 35
        # Post-lunch dip
        elif 13 <= hour <= 15:
            productivity[i] -= 20
        # Afternoon recovery
        elif 16 <= hour <= 18:
            productivity[i] += 25
        else:
            productivity[i] += 10
        
        # Task type preferences
        if task_type == 'coding':
            productivity[i] += 30
        elif task_type == 'research':
            productivity[i] += 20
        elif task_type == 'writing':
            productivity[i] += 10
        elif task_type == 'meeting':
            productivity[i] -= 15
        
        # Add realistic variation
        productivity[i] += np.random.normal(0, 8)
    
    productivity = np.clip(productivity + 55, 15, 100)
    
    # Create comprehensive sample data
    sample_data = pd.DataFrame({
        'hour_of_day': hours,
        'task_type': types,
        'duration': durations,
        'focus_score': np.random.uniform(25, 100, n_samples),
        'energy_level': np.random.uniform(15, 100, n_samples),
        'completion_time': np.random.uniform(0.6, 1.4, n_samples),
        'productivity_score': productivity,
    })
    
    print(f"✓ Created {len(sample_data)} sample tasks")
    print(f"  Task types: {', '.join(set(types))}")
    print(f"  Hours: {min(hours)}-{max(hours)}")
    print(f"  Durations: {min(durations):.0f}-{max(durations):.0f} minutes")
    print()
    
    # Create raw tasks dataframe for context
    raw_tasks = pd.DataFrame({
        'id': range(1, n_samples + 1),
        'user_id': [1] * n_samples,
        'title': [f'Task {i}' for i in range(1, n_samples + 1)],
        'task_type': types,
        'priority': np.random.randint(1, 6, n_samples),
        'estimated_duration': durations * np.random.uniform(0.8, 1.2, n_samples),
        'actual_duration': durations,
        'start_time': [datetime.now() - timedelta(hours=i // 5) for i in range(n_samples)],
        'end_time': [datetime.now() - timedelta(hours=i // 5 - 1) for i in range(n_samples)],
        'completed': [True] * n_samples,
        'hour_of_day': hours,
    })
    
    print("Step 2: Initializing Behavior Intelligence Engine...")
    print("-" * 80)
    
    # Create engine (without database for this demo)
    engine = BehaviorIntelligenceEngine()
    engine.raw_tasks_df = raw_tasks
    
    print("✓ Engine initialized")
    print()
    
    print("Step 3: Extracting behavioral features...")
    print("-" * 80)
    
    features = engine.extract_features(sample_data)
    
    print(f"✓ Extracted features for {len(features)} tasks")
    print(f"  Features: {list(features.columns)}")
    print(f"\n  Sample features (first 3 rows):")
    print(features.head(3).to_string(index=False))
    print()
    
    print("Step 4: Training productivity prediction model...")
    print("-" * 80)
    
    metrics = engine.train_productivity_model(sample_data)
    
    print(f"✓ Model training complete!")
    print(f"  R² Score: {metrics['accuracy']:.4f} (closer to 1.0 is better)")
    print(f"  MAE: {metrics['mae']:.2f} points")
    print(f"  RMSE: {metrics['rmse']:.2f} points")
    print(f"  Training samples: {metrics['n_samples']}")
    print()
    
    print("Step 5: Analyzing user behavior patterns...")
    print("-" * 80)
    
    patterns = engine.get_user_patterns()
    
    print(f"✓ Patterns identified!")
    print(f"  Best focus hours: {patterns['best_focus_hours']}")
    print(f"  Low energy hours: {patterns['low_energy_hours']}")
    print(f"  Average task duration: {patterns['average_task_duration']:.1f} minutes")
    print(f"  Most productive task types: {patterns['preferred_task_types']}")
    print(f"  Overall trend: {patterns['productivity_trend']}")
    print()
    
    print("Step 6: Making productivity predictions...")
    print("-" * 80)
    
    test_cases = [
        {"hour": 9, "task_type": "coding", "duration": 120, "label": "Morning coding session"},
        {"hour": 12, "task_type": "meeting", "duration": 60, "label": "Lunch time meeting"},
        {"hour": 14, "task_type": "research", "duration": 90, "label": "Post-lunch research"},
        {"hour": 17, "task_type": "writing", "duration": 45, "label": "Late afternoon writing"},
    ]
    
    print(f"\n{'Task':<30} {'Hour':>4} {'Type':<12} {'Duration':>8} {'Productivity':>12}")
    print("-" * 80)
    
    for test in test_cases:
        score = engine.predict_task_productivity(
            test['hour'],
            test['task_type'],
            test['duration']
        )
        print(f"{test['label']:<30} {test['hour']:4d} {test['task_type']:<12} "
              f"{test['duration']:8.0f}m {score:>11.1f}/100")
    
    print()
    
    print("Step 7: Getting model insights...")
    print("-" * 80)
    
    insights = engine.get_model_insights()
    
    print(f"✓ Model insights:")
    print(f"  Feature importance:")
    for feature, importance in insights['feature_importance'].items():
        bar = '█' * int(importance * 30)
        print(f"    {feature:<20} {bar:<30} {importance:.3f}")
    
    print()
    
    print("Step 8: Generating comprehensive report...")
    print("-" * 80)
    
    report = engine.generate_report()
    print(report)
    
    print("\n" + "=" * 80)
    print("QUICK START DEMO COMPLETE!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Set up database (PostgreSQL or SQLite)")
    print("2. Run: uvicorn main:app --reload")
    print("3. Visit: http://localhost:8000/api/docs")
    print("4. Load your actual task data")
    print("5. Train model with real data: POST /api/v1/behavior/train")
    print()


def main():
    """Main entry point."""
    try:
        quick_start_demo()
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
