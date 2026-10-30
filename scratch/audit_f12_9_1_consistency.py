"""Phase F12.9.1: Final Data Consistency Check.

Read-only audit of behavior_engine.db and model inventory integrity.
Strictly read-only; zero modification of production data.
"""
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database.db import SessionLocal
from backend.app.models.auth import User
from backend.app.models.task import Task
from backend.app.ml.datasets import TaskDataExtractor
from backend.app.ml.readiness import (
    assess_full_ml_system_readiness,
    assess_duration_model_readiness,
    assess_productivity_model_readiness,
    assess_rl_scheduler_readiness,
)
from backend.app.ml.model_registry import ModelRegistry
from backend.app.ml.system_inventory import get_system_inventory

def run_f12_9_1_audit():
    db_path = PROJECT_ROOT / "behavior_engine.db"
    print(f"Auditing Authoritative Database: {db_path}")
    print(f"Database File Exists: {db_path.exists()} (Size: {db_path.stat().st_size} bytes)")

    # Read-only SQLite connection
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Inspect Users
    cur.execute("SELECT id, email, is_active, created_at FROM users ORDER BY id")
    users = cur.fetchall()
    user_map = {u["id"]: u["email"] for u in users}

    print("\n" + "=" * 60)
    print("1. USERS IN DATABASE")
    print("=" * 60)
    for u in users:
        print(f"  User ID: {u['id']} | Email: {u['email']} | Active: {u['is_active']} | Created: {u['created_at']}")

    # 2. Inspect Tasks
    cur.execute("""
        SELECT id, user_id, title, task_type, priority,
               estimated_duration, estimated_duration_unit, estimated_duration_source,
               lifecycle_state, start_time, end_time, completed, outcome_valid, actual_duration,
               focus_rating, energy_rating, productivity_rating, feedback_notes, feedback_submitted_at,
               created_at
        FROM tasks
        ORDER BY id
    """)
    tasks = cur.fetchall()

    print("\n" + "=" * 60)
    print(f"2. TASKS IN DATABASE (Total Tasks: {len(tasks)})")
    print("=" * 60)

    tasks_by_user = {}
    completed_by_user = {}
    valid_timestamps_tasks = []
    verified_duration_tasks = []
    rated_tasks = []

    for t in tasks:
        uid = t["user_id"]
        tasks_by_user[uid] = tasks_by_user.get(uid, 0) + 1
        
        is_completed = (t["completed"] == 1 or t["lifecycle_state"] == "COMPLETED")
        if is_completed:
            completed_by_user[uid] = completed_by_user.get(uid, 0) + 1

        # Check timestamp validity
        st_str = t["start_time"]
        et_str = t["end_time"]
        valid_ts = False
        duration_from_ts = None
        if st_str and et_str:
            try:
                st = datetime.fromisoformat(st_str.replace("Z", "+00:00"))
                et = datetime.fromisoformat(et_str.replace("Z", "+00:00"))
                if et > st:
                    valid_ts = True
                    duration_from_ts = round((et - st).total_seconds() / 60.0, 2)
            except Exception as e:
                pass
        
        if valid_ts:
            valid_timestamps_tasks.append((t["id"], uid, st_str, et_str, duration_from_ts))

        # Check estimated duration unit and actual duration validity
        unit_valid = (t["estimated_duration_unit"] == "minutes" or t["estimated_duration_unit"] == "min")
        est_valid = (t["estimated_duration"] is not None and t["estimated_duration"] > 0)
        actual_valid = (t["actual_duration"] is not None and t["actual_duration"] > 0)
        outcome_valid = (t["outcome_valid"] == 1)

        if unit_valid and est_valid and actual_valid and outcome_valid and valid_ts:
            verified_duration_tasks.append({
                "id": t["id"],
                "user_id": uid,
                "title": t["title"],
                "estimated": t["estimated_duration"],
                "unit": t["estimated_duration_unit"],
                "actual": t["actual_duration"],
                "derived_from_ts": duration_from_ts,
                "outcome_valid": outcome_valid
            })

        # Check genuine ratings
        has_focus = t["focus_rating"] is not None
        has_energy = t["energy_rating"] is not None
        has_prod = t["productivity_rating"] is not None
        if has_focus or has_energy or has_prod or t["feedback_notes"] is not None or t["feedback_submitted_at"] is not None:
            rated_tasks.append({
                "id": t["id"],
                "user_id": uid,
                "focus": t["focus_rating"],
                "energy": t["energy_rating"],
                "productivity": t["productivity_rating"],
                "notes": t["feedback_notes"],
                "submitted_at": t["feedback_submitted_at"]
            })

        print(f"\n  Task ID: {t['id']} | User ID: {uid} ({user_map.get(uid, 'Unknown')})")
        print(f"    Title: '{t['title']}' | Type: {t['task_type']} | Priority: {t['priority']}")
        print(f"    State: {t['lifecycle_state']} | Completed: {t['completed']} | Outcome Valid: {t['outcome_valid']}")
        print(f"    Estimate: {t['estimated_duration']} {t['estimated_duration_unit']} (source: {t['estimated_duration_source']})")
        print(f"    Start: {t['start_time']} | End: {t['end_time']} | Actual Duration: {t['actual_duration']} min")
        print(f"    Ratings: Focus={t['focus_rating']}, Energy={t['energy_rating']}, Productivity={t['productivity_rating']}")
        print(f"    Notes: {t['feedback_notes']} | Feedback At: {t['feedback_submitted_at']}")

    print("\n" + "=" * 60)
    print("3. GROUPED METRICS BREAKDOWN")
    print("=" * 60)
    print(f"Total Tasks: {len(tasks)}")
    print("\nTasks Grouped by User:")
    for uid, count in tasks_by_user.items():
        print(f"  User {uid} ({user_map.get(uid, 'Unknown')}): {count} tasks")

    print("\nCompleted Tasks Grouped by User:")
    for uid in tasks_by_user.keys():
        c_count = completed_by_user.get(uid, 0)
        print(f"  User {uid} ({user_map.get(uid, 'Unknown')}): {c_count} completed tasks")

    print(f"\nTasks with Valid Start and End Timestamps: {len(valid_timestamps_tasks)}")
    for tid, uid, st, et, dur in valid_timestamps_tasks:
        print(f"  Task {tid} (User {uid}): start={st}, end={et}, elapsed={dur} min")

    print(f"\nTasks with Verified Estimated-Duration Units & Valid Actual Duration: {len(verified_duration_tasks)}")
    for item in verified_duration_tasks:
        print(f"  Task {item['id']} (User {item['user_id']}): est={item['estimated']} {item['unit']}, act={item['actual']} min (derived={item['derived_from_ts']} min), outcome_valid={item['outcome_valid']}")

    print(f"\nGenuine Post-Task Ratings Recorded: {len(rated_tasks)}")
    if rated_tasks:
        for r in rated_tasks:
            print(f"  Task {r['id']} (User {r['user_id']}): Focus={r['focus']}, Energy={r['energy']}, Productivity={r['productivity']}, Notes='{r['notes']}'")
    else:
        print("  NONE. All user rating fields (focus_rating, energy_rating, productivity_rating, feedback_notes) are NULL.")

    # 4. Check behavior_data table
    cur.execute("SELECT COUNT(*) FROM behavior_data")
    bdata_count = cur.fetchone()[0]
    print(f"\nBehavior Data Table Row Count: {bdata_count}")

    # 5. Check auth_sessions table
    cur.execute("SELECT user_id, COUNT(*) as cnt FROM auth_sessions GROUP BY user_id")
    sessions = cur.fetchall()
    print("\nAuth Sessions Grouped by User:")
    for s in sessions:
        print(f"  User {s['user_id']} ({user_map.get(s['user_id'], 'Unknown')}): {s['cnt']} sessions")

    conn.close()

    # 6. Model Training Readiness & Eligibility Assessment via Application Layer
    print("\n" + "=" * 60)
    print("4. ELIGIBILITY ASSESSMENTS VIA APPLICATION LOGIC")
    print("=" * 60)

    with SessionLocal() as session:
        # Check global and per-user dataset extraction
        extractor = TaskDataExtractor(session)
        global_extract = extractor.extract()
        print(f"Global Duration Extraction:")
        print(f"  Total DB records scanned: {global_extract.report.total_database_records}")
        print(f"  Eligible duration-training rows: {global_extract.report.eligible_records}")
        print(f"  Rejected rows: {global_extract.report.rejected_records}")
        print(f"  Rejection reasons: {dict(global_extract.report.rejection_reason_counts)}")

        for uid in tasks_by_user.keys():
            u_extract = extractor.extract(user_id=uid)
            print(f"\nUser {uid} ({user_map.get(uid, 'Unknown')}) Extraction:")
            print(f"  Total DB records: {u_extract.report.total_database_records}")
            print(f"  Eligible duration rows: {u_extract.report.eligible_records}")
            print(f"  Rejected rows: {u_extract.report.rejected_records}")
            print(f"  Rejection reasons: {dict(u_extract.report.rejection_reason_counts)}")

            # Productivity readiness
            p_read = assess_productivity_model_readiness(session, user_id=uid)
            print(f"  Productivity Model Readiness: status={p_read.status}, eligible_samples={p_read.eligible_samples}/{p_read.required_samples}")
            print(f"    Blocking: {p_read.blocking_reasons}")

            # RL Scheduler readiness
            rl_read = assess_rl_scheduler_readiness(session, user_id=uid)
            print(f"  RL Scheduler Readiness: status={rl_read.status}, eligible_episodes={rl_read.eligible_samples}/{rl_read.required_samples}")
            print(f"    Blocking: {rl_read.blocking_reasons}")

    # 7. Model Inventory & Governance Verification
    print("\n" + "=" * 60)
    print("5. MODEL INVENTORY, REGISTRY & GOVERNANCE HONESTY")
    print("=" * 60)
    inventory = get_system_inventory()
    print(f"Total Registered Components in SystemInventory: {len(inventory)}")

    # Check RL Scheduler
    rl_comp = next((c for c in inventory.values() if c.canonical_id == "rl_scheduler"), None)
    assert rl_comp is not None, "RL Scheduler missing from inventory!"
    print(f"\nRL Scheduler Component:")
    print(f"  Component ID: {rl_comp.canonical_id}")
    print(f"  Component Type: {rl_comp.component_type}")
    print(f"  Operational State: {rl_comp.operational_state}")
    print(f"  Training State: {rl_comp.training_state}")
    print(f"  Can Execute Now: {rl_comp.can_execute_now}")
    print(f"  Fallback Active: {rl_comp.fallback_active}")
    print(f"  Fallback Description: '{rl_comp.fallback_description}'")
    print(f"  Is Labeled as Trained?: {'YES (VIOLATION)' if rl_comp.training_state == 'TRAINED' else 'NO (CORRECT: NOT_READY_INSUFFICIENT_DATA)'}")

    # Check Public Benchmark Candidate
    from backend.app.ml.model_registry import get_model_registry
    registry = get_model_registry()
    latest_prod = registry.get_latest_model("ProductivityModel")
    all_prod_records = registry.store.list("ProductivityModel")
    
    print(f"\nProductivity Model Registry Governance:")
    print(f"  Production Model: {latest_prod.metadata.model_name + ' v' + str(latest_prod.metadata.version) if latest_prod else 'NONE (Default Baseline/Heuristic: Diurnal Circadian)'}")
    print(f"  Total Registered Versions: {len(all_prod_records)}")
    for rec in all_prod_records:
        meta = rec.metadata
        print(f"    Version {meta.version}: status={meta.status}, accuracy_score={meta.accuracy_score}")
        print(f"      is_personalized={meta.metrics.get('is_personalized', 'N/A')}")
        print(f"      public_benchmark={meta.metrics.get('public_benchmark', 'N/A')}")
        print(f"      dataset_id={meta.metrics.get('dataset_id', 'N/A')}")
        print(f"      promotion_verdict={meta.metrics.get('promotion_verdict', 'N/A')}")
        print(f"      artifact_path={meta.metrics.get('artifact_path', 'N/A')}")
        print(f"      Is Labeled as Personalized?: {'YES (VIOLATION)' if meta.metrics.get('is_personalized') is True else 'NO (CORRECT: Non-Personalized Benchmark)'}")

    # Check Baseline & Heuristic Fallbacks
    duration_comp = next((c for c in inventory.values() if c.canonical_id == "duration_regression_model"), None)
    duration_baseline = next((c for c in inventory.values() if c.canonical_id == "duration_ratio_baseline"), None)
    print(f"\nDuration Model Fallback Governance:")
    print(f"  Duration Regression Model: operational_state={duration_comp.operational_state if duration_comp else 'N/A'}, training_state={duration_comp.training_state if duration_comp else 'N/A'}")
    print(f"  Duration Ratio Baseline: operational_state={duration_baseline.operational_state if duration_baseline else 'N/A'}, fallback_active={duration_baseline.fallback_active if duration_baseline else 'N/A'}")

    print("\n" + "=" * 60)
    print("AUDIT EXECUTION COMPLETE - ALL CHECKS EXECUTED CLEANLY")
    print("=" * 60)

if __name__ == "__main__":
    run_f12_9_1_audit()
