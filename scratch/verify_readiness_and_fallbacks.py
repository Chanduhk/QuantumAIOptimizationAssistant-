"""Verify Stage 7 Model Readiness, Heuristic Fallbacks, and User Isolation.
"""
from backend.app.database.db import SessionLocal
from backend.app.ml.readiness import (
    assess_duration_model_readiness,
    assess_productivity_model_readiness,
    assess_rl_scheduler_readiness,
    assess_full_ml_system_readiness,
)
from backend.app.models.task import Task
import json

session = SessionLocal()
try:
    print("=== GLOBAL / SYSTEM-WIDE READINESS ===")
    system_readiness = assess_full_ml_system_readiness(session)
    print(f"Overall status: {system_readiness.overall_status}")
    for name, comp in system_readiness.components.items():
        print(f"  Component: {name}")
        print(f"    Status: {comp.status}")
        print(f"    Eligible: {comp.eligible_samples} / {comp.required_samples}")
        print(f"    Label source: {comp.ground_truth_label_source}")
        print(f"    Blocking: {comp.blocking_reasons}")

    # Inspect users in database
    users = session.query(Task.user_id).distinct().all()
    user_ids = [u[0] for u in users]
    print(f"\nDistinct users in DB: {user_ids}")

    for uid in user_ids:
        print(f"\n=== USER-SCOPED READINESS: User {uid} ===")
        dur_comp = assess_duration_model_readiness(session, user_id=uid)
        print(f"Duration Model: {dur_comp.status} ({dur_comp.eligible_samples}/{dur_comp.required_samples})")
        
        prod_comp = assess_productivity_model_readiness(session, user_id=uid)
        print(f"Productivity Model: {prod_comp.status} ({prod_comp.eligible_samples}/{prod_comp.required_samples})")

        rl_comp = assess_rl_scheduler_readiness(session, user_id=uid)
        print(f"RL Scheduler: {rl_comp.status} ({rl_comp.eligible_samples}/{rl_comp.required_samples})")

finally:
    session.close()
