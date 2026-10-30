"""Phase F13.2 — Detailed read-only comparison of the two substantive databases."""
import json
import sqlite3
from pathlib import Path

DBS = {
    "ROOT": r"e:\quantum_life_ai\behavior_engine.db",
    "BACKEND": r"e:\quantum_life_ai\backend\behavior_engine.db",
}

def inspect(label: str, path: str):
    print(f"\n{'='*80}")
    print(f"DATABASE: {label} — {path}")
    print(f"{'='*80}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # Task summary (no PII — only user_id, not emails)
    rows = conn.execute(
        "SELECT id, user_id, title, task_type, priority, lifecycle_state, completed, "
        "start_time, end_time, actual_duration, estimated_duration, estimated_duration_unit, "
        "focus_rating, energy_rating, productivity_rating, feedback_submitted_at, outcome_valid "
        "FROM tasks ORDER BY id"
    ).fetchall()
    print(f"\nTotal tasks: {len(rows)}")
    print(f"{'ID':>4} | {'User':>12} | {'State':>12} | {'Done':>5} | {'Start':>20} | {'End':>20} | {'ActDur':>8} | {'F':>2} | {'E':>2} | {'P':>2} | Title")
    print("-" * 140)
    for r in rows:
        uid = str(r["user_id"])[-4:] if r["user_id"] else "?"
        state = r["lifecycle_state"] or "-"
        done = "Y" if r["completed"] else "N"
        start = str(r["start_time"] or "-")[:19]
        end = str(r["end_time"] or "-")[:19]
        dur = str(r["actual_duration"] or "-")[:8]
        f = str(r["focus_rating"] or "-")
        e = str(r["energy_rating"] or "-")
        p = str(r["productivity_rating"] or "-")
        title = (r["title"] or "")[:30]
        print(f"{r['id']:>4} | ...{uid:>8} | {state:>12} | {done:>5} | {start:>20} | {end:>20} | {dur:>8} | {f:>2} | {e:>2} | {p:>2} | {title}")

    # Counts
    completed = sum(1 for r in rows if r["completed"])
    with_start_end = sum(1 for r in rows if r["start_time"] and r["end_time"])
    with_duration = sum(1 for r in rows if r["actual_duration"] and r["actual_duration"] > 0)
    with_feedback = sum(1 for r in rows if r["focus_rating"] is not None and r["energy_rating"] is not None and r["productivity_rating"] is not None)
    with_completed_and_feedback = sum(1 for r in rows if r["completed"] and r["focus_rating"] is not None and r["energy_rating"] is not None and r["productivity_rating"] is not None)

    print(f"\n--- Summary ---")
    print(f"  Completed tasks (boolean): {completed}")
    print(f"  Tasks with start+end timestamps: {with_start_end}")
    print(f"  Tasks with actual_duration > 0: {with_duration}")
    print(f"  Tasks with all 3 feedback ratings: {with_feedback}")
    print(f"  Completed tasks with all 3 feedback ratings (RL eligible): {with_completed_and_feedback}")

    # Distinct users
    users = conn.execute("SELECT DISTINCT user_id FROM tasks").fetchall()
    print(f"  Distinct users: {len(users)}")
    for u in users:
        uid = str(u[0])[-4:]
        user_completed = sum(1 for r in rows if r["user_id"] == u[0] and r["completed"])
        user_with_fb = sum(1 for r in rows if r["user_id"] == u[0] and r["completed"] and r["focus_rating"] is not None)
        user_with_dur = sum(1 for r in rows if r["user_id"] == u[0] and r["completed"] and r["start_time"] and r["end_time"])
        print(f"    User ...{uid}: {user_completed} completed, {user_with_fb} with feedback, {user_with_dur} with timestamps")

    # behavior_data
    bd_count = conn.execute("SELECT COUNT(*) FROM behavior_data").fetchone()[0]
    print(f"  behavior_data rows: {bd_count}")
    if bd_count > 0:
        bd_cols = [r[1] for r in conn.execute("PRAGMA table_info(behavior_data)").fetchall()]
        print(f"  behavior_data columns: {bd_cols}")

    # auth_sessions
    if "auth_sessions" in [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
        sess = conn.execute("SELECT COUNT(*) FROM auth_sessions").fetchone()[0]
        print(f"  auth_sessions rows: {sess}")

    # Users table
    if "users" in [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        print(f"  users table rows: {user_count}")

    conn.close()

if __name__ == "__main__":
    for label, path in DBS.items():
        inspect(label, path)
