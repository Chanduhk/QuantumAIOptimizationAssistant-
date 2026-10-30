"""Phase F13.3 — Read-only audit of existing duration records in authoritative DB."""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = r"e:\quantum_life_ai\behavior_engine.db"

def audit():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("""
        SELECT id, user_id, title, task_type, priority,
               lifecycle_state, completed, outcome_valid,
               estimated_duration, estimated_duration_unit, estimated_duration_source,
               start_time, end_time, actual_duration,
               focus_rating, energy_rating, productivity_rating,
               feedback_notes, feedback_submitted_at, created_at
        FROM tasks
        ORDER BY id
    """).fetchall()
    
    print(f"Total tasks in {DB_PATH}: {len(rows)}")
    print("=" * 100)
    for r in rows:
        uid = str(r["user_id"])
        masked_uid = f"...{uid[-4:]}" if len(uid) >= 4 else uid
        print(f"\nTask ID: {r['id']} | User: {masked_uid} | Title: '{r['title']}'")
        print(f"  State: {r['lifecycle_state']} | Completed: {r['completed']} | Outcome Valid: {r['outcome_valid']}")
        print(f"  Created: {r['created_at']}")
        print(f"  Start:   {r['start_time']}")
        print(f"  End:     {r['end_time']}")
        print(f"  Estimate: {r['estimated_duration']} {r['estimated_duration_unit']} (source: {r['estimated_duration_source']})")
        print(f"  Actual:   {r['actual_duration']} min")
        
        # Calculate wall-clock duration if timestamps exist
        st = r['start_time']
        et = r['end_time']
        if st and et:
            try:
                st_dt = datetime.fromisoformat(st)
                et_dt = datetime.fromisoformat(et)
                elapsed_sec = (et_dt - st_dt).total_seconds()
                elapsed_min = elapsed_sec / 60.0
                elapsed_hr = elapsed_min / 60.0
                elapsed_days = elapsed_hr / 24.0
                print(f"  Elapsed wall-clock: {elapsed_min:.2f} min ({elapsed_hr:.2f} hours / {elapsed_days:.2f} days)")
                if r['estimated_duration']:
                    ratio = (r['actual_duration'] or elapsed_min) / float(r['estimated_duration'])
                    print(f"  Duration Ratio (actual/est): {ratio:.4f}")
            except Exception as exc:
                print(f"  Timestamp parse error: {exc}")
                
        print(f"  Feedback: Focus={r['focus_rating']}, Energy={r['energy_rating']}, Productivity={r['productivity_rating']}")
        print(f"  Notes: '{r['feedback_notes']}' | Feedback At: {r['feedback_submitted_at']}")

    conn.close()

if __name__ == "__main__":
    audit()
