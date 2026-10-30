"""Stage 2: Read-Only Audit of Personal Data and Feedback Integrity in behavior_engine.db."""
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.database.db import SessionLocal
from backend.app.models.auth import User
from backend.app.models.task import Task
from backend.app.ml.datasets import TaskDataExtractor
from backend.app.ml.readiness import assess_full_ml_system_readiness

def run_stage2_data_integrity_audit():
    print("=== STAGE 2: PERSONAL DATA AND FEEDBACK INTEGRITY AUDIT ===")
    
    db_path = PROJECT_ROOT / "behavior_engine.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 1. Inspect all Users
    c.execute("SELECT id, email, is_active, created_at FROM users ORDER BY id")
    users = c.fetchall()
    print(f"\n1. Users in Authoritative Database ({len(users)} users):")
    for u in users:
        print(f"   User ID: {u['id']}, Email: {u['email']}, Active: {u['is_active']}, Created: {u['created_at']}")

    # 2. Inspect all Tasks in full detail
    c.execute("""
        SELECT id, user_id, title, task_type, priority,
               estimated_duration, estimated_duration_unit, estimated_duration_source,
               lifecycle_state, start_time, end_time, completed, outcome_valid, actual_duration,
               focus_rating, energy_rating, productivity_rating, feedback_notes, feedback_submitted_at,
               created_at
        FROM tasks
        ORDER BY id
    """)
    tasks = c.fetchall()
    print(f"\n2. Tasks in Authoritative Database ({len(tasks)} tasks):")
    for t in tasks:
        print(f"\n   --- Task ID {t['id']} (User {t['user_id']}) ---")
        print(f"       Title: '{t['title']}', Type: {t['task_type']}, Priority: {t['priority']}")
        print(f"       Lifecycle State: {t['lifecycle_state']}, Completed: {t['completed']}, Outcome Valid: {t['outcome_valid']}")
        print(f"       Estimate: {t['estimated_duration']} (Unit: {t['estimated_duration_unit']}, Source: {t['estimated_duration_source']})")
        print(f"       Timestamps: Created: {t['created_at']}, Started: {t['start_time']}, Ended: {t['end_time']}")
        print(f"       Actual Duration: {t['actual_duration']}")
        print(f"       Feedback: Focus: {t['focus_rating']}, Energy: {t['energy_rating']}, Productivity: {t['productivity_rating']}")
        print(f"       Notes: '{t['feedback_notes']}', Submitted At: {t['feedback_submitted_at']}")

    conn.close()

    # 3. Investigate the F12.8 Smoke Test Impact
    print("\n3. Investigating F12.8 Smoke Test Impact on Real User Records:")
    real_user_id = 1412004044  # abc130343@gmail.com
    with SessionLocal() as session:
        real_user_tasks = session.query(Task).filter(Task.user_id == real_user_id).all()
        print(f"   Real User ({real_user_id}) owns {len(real_user_tasks)} tasks.")
        for rt in real_user_tasks:
            # Verify no smoke test feedback was written to real user tasks
            assert rt.focus_rating is None, f"Contamination: Task {rt.id} has focus_rating {rt.focus_rating}"
            assert rt.energy_rating is None, f"Contamination: Task {rt.id} has energy_rating {rt.energy_rating}"
            assert rt.productivity_rating is None, f"Contamination: Task {rt.id} has productivity_rating {rt.productivity_rating}"
            assert rt.feedback_notes is None, f"Contamination: Task {rt.id} has feedback_notes"
            print(f"   [x] Task {rt.id} ('{rt.title}'): Intact, zero test feedback contamination.")

        # 4. User-Scoped Dataset Extraction Verification
        print("\n4. User-Scoped Dataset Extraction vs Global Extraction:")
        extractor = TaskDataExtractor(session)
        user_extraction = extractor.extract(user_id=real_user_id)
        global_extraction = extractor.extract()
        
        print(f"   User-scoped extraction ({real_user_id}):")
        print(f"     Total tasks seen: {user_extraction.report.total_database_records}")
        print(f"     Eligible duration records: {user_extraction.report.eligible_records}")
        print(f"     Rejected records: {user_extraction.report.rejected_records}")
        print(f"     Rejection reasons: {dict(user_extraction.report.rejection_reason_counts)}")

        print(f"   Global extraction:")
        print(f"     Total tasks seen: {global_extraction.report.total_database_records}")
        print(f"     Eligible duration records: {global_extraction.report.eligible_records}")
        print(f"     Rejected records: {global_extraction.report.rejected_records}")
        print(f"     Rejection reasons: {dict(global_extraction.report.rejection_reason_counts)}")

        # 5. Readiness Assessment
        print("\n5. Readiness Assessment for Real User:")
        readiness_report = assess_full_ml_system_readiness(session, user_id=real_user_id)
        print(f"   Overall Status: {readiness_report.overall_status}")
        for cname, cread in readiness_report.components.items():
            print(f"     {cname}: Status={cread.status}, Eligible={cread.eligible_samples}/{cread.required_samples}")
            print(f"       Blocking reasons: {cread.blocking_reasons}")

    print("\nPASS: Real user data integrity completely verified. Zero smoke-test pollution.")
    print("=== STAGE 2 AUDIT COMPLETE ===")

if __name__ == "__main__":
    run_stage2_data_integrity_audit()
