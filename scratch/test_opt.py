import sys
sys.path.insert(0, ".")
from pathlib import Path
import pandas as pd
from backend.app.ai_models.productivity_model import ProductivityModel
from backend.app.domain.optimization_input_contract import adapt_task_for_optimization
from backend.app.domain.prediction_matrix import build_prediction_matrix
from backend.app.domain.classical_optimizer import ClassicalOptimizer
from backend.app.domain.assignment_qubo_ising import AssignmentQuboIsingBuilder
from backend.app.domain.quantum_suitability import QuantumSuitabilityAnalyzer
from backend.app.domain.hybrid_comparison import HybridComparator
from backend.app.engines.prediction_engine import PredictionEngine
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine
from backend.app.database.db import SessionLocal

session = SessionLocal()
behavior = BehaviorIntelligenceEngine(session)
p = Path("data/model_artifacts/productivity_benchmark_candidate_uci-garment-productivity.joblib")
model = ProductivityModel(model_path=str(p))
behavior.productivity_model = model

frame1 = pd.DataFrame([{"hour_of_day": 9.0, "task_type": "writing", "duration": 1.0}])
frame2 = pd.DataFrame([{"hour_of_day": 9.0, "task_type": "coding", "duration": 1.5}])
print("X1:", model._prepare_features(frame1))
print("X2:", model._prepare_features(frame2))
print("Classes:", model.task_type_encoder.classes_)
print("Pred 1:", model.predict(9, "writing", 1.0))
print("Pred 2:", model.predict(9, "coding", 1.5))


tasks_raw = [
    {"id": 1, "title": "Write report", "task_type": "writing", "priority": 3, "estimated_duration": 60, "estimated_duration_unit": "minutes", "estimated_duration_source": "task_api", "lifecycle_state": "created", "completed": False},
    {"id": 2, "title": "Code module", "task_type": "coding", "priority": 4, "estimated_duration": 90, "estimated_duration_unit": "minutes", "estimated_duration_source": "task_api", "lifecycle_state": "created", "completed": False},
]

opt_tasks = tuple(adapt_task_for_optimization(t, estimated_duration_unit="minutes", duration_source="task_api") for t in tasks_raw)
actions = (9, 10, 11, 14, 15)

pred_engine = PredictionEngine()
matrix = build_prediction_matrix(pred_engine, behavior, opt_tasks, actions)
for c in matrix.cells:
    print(f"Task {c.task_id} @ hour {c.candidate_start_hour}: value={c.value}")
print("Matrix nontriviality:", matrix.nontriviality)
print("Matrix contrast:", matrix.assignment_contrast)

classical = ClassicalOptimizer().optimize(matrix)
print("Classical candidate total objective:", classical.total_objective)
print("Classical assignments:", [(a.task_id, a.assigned_hour, a.prediction_score) for a in classical.assignments])

formulation = AssignmentQuboIsingBuilder().build(matrix)
print("QUBO variables:", len(formulation.variables))

suitability = QuantumSuitabilityAnalyzer().assess(matrix, classical, formulation)
print("Quantum suitability status:", suitability.status)
