"""Phase F13.2 — Read-only database audit script.
Inspects all discovered .db files without modifying any of them.
"""
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATHS = [
    r"e:\quantum_life_ai\behavior_engine.db",
    r"e:\quantum_life_ai\backend\behavior_engine.db",
    r"e:\quantum_life_ai\backend\behavior_engine_demo.db",
    r"e:\quantum_life_ai\data\quantum_life.db",
]

def audit_db(path: str) -> dict:
    result = {"path": path}
    p = Path(path)
    if not p.exists():
        result["exists"] = False
        return result
    result["exists"] = True
    result["size_bytes"] = p.stat().st_size
    result["last_modified"] = datetime.fromtimestamp(p.stat().st_mtime).isoformat()
    result["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
    except Exception as e:
        result["connection_error"] = str(e)
        return result

    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        result["integrity_check"] = integrity
    except Exception as e:
        result["integrity_check"] = f"ERROR: {e}"

    # List all tables
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        result["tables"] = tables
    except Exception as e:
        result["tables_error"] = str(e)
        conn.close()
        return result

    # Task count
    if "tasks" in tables:
        try:
            result["task_count"] = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            result["completed_task_count"] = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
            # Distinct users (show only count, no PII)
            result["distinct_user_count"] = conn.execute("SELECT COUNT(DISTINCT user_id) FROM tasks").fetchone()[0]
            # Tasks with valid start and end timestamps
            result["tasks_with_valid_timestamps"] = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE started_at IS NOT NULL AND completed_at IS NOT NULL"
            ).fetchone()[0]
            # Status breakdown
            statuses = conn.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY status").fetchall()
            result["task_status_breakdown"] = {s: c for s, c in statuses}
            # Per-user completed count (user_id only, no emails)
            per_user = conn.execute(
                "SELECT user_id, COUNT(*) FROM tasks WHERE status='completed' GROUP BY user_id"
            ).fetchall()
            result["completed_per_user"] = {str(uid): cnt for uid, cnt in per_user}
        except Exception as e:
            result["task_query_error"] = str(e)

    # Feedback / ratings
    if "task_feedback" in tables:
        try:
            result["feedback_count"] = conn.execute("SELECT COUNT(*) FROM task_feedback").fetchone()[0]
            # Feedback with all three ratings present
            result["feedback_with_all_ratings"] = conn.execute(
                "SELECT COUNT(*) FROM task_feedback WHERE focus_rating IS NOT NULL AND energy_rating IS NOT NULL AND productivity_rating IS NOT NULL"
            ).fetchone()[0]
        except Exception as e:
            result["feedback_query_error"] = str(e)
    else:
        # Check if feedback is stored directly in tasks table
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
            feedback_cols = [c for c in cols if "rating" in c.lower() or "feedback" in c.lower() or "focus" in c.lower() or "energy" in c.lower()]
            result["tasks_table_feedback_columns"] = feedback_cols
            if "focus_rating" in cols:
                result["tasks_with_focus_rating"] = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE focus_rating IS NOT NULL"
                ).fetchone()[0]
            if "energy_rating" in cols:
                result["tasks_with_energy_rating"] = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE energy_rating IS NOT NULL"
                ).fetchone()[0]
            if "productivity_rating" in cols:
                result["tasks_with_productivity_rating"] = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE productivity_rating IS NOT NULL"
                ).fetchone()[0]
        except Exception as e:
            result["feedback_column_error"] = str(e)

    # behavior_data table
    if "behavior_data" in tables:
        try:
            result["behavior_data_count"] = conn.execute("SELECT COUNT(*) FROM behavior_data").fetchone()[0]
        except Exception as e:
            result["behavior_data_error"] = str(e)

    # Duration observations
    if "tasks" in tables:
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
            result["tasks_columns"] = cols
            # Valid duration observation = completed task with start and end timestamps
            if "actual_duration_minutes" in cols:
                result["valid_duration_observations"] = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE status='completed' AND actual_duration_minutes IS NOT NULL AND actual_duration_minutes > 0"
                ).fetchone()[0]
            elif "started_at" in cols and "completed_at" in cols:
                result["valid_duration_observations"] = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE status='completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL"
                ).fetchone()[0]
        except Exception as e:
            result["duration_error"] = str(e)

    # RL episodes: completed tasks with feedback ratings from a specific user
    if "tasks" in tables:
        try:
            cols_set = set(result.get("tasks_columns", []))
            if {"focus_rating", "energy_rating", "productivity_rating"}.issubset(cols_set):
                rl_episodes = conn.execute(
                    "SELECT user_id, COUNT(*) FROM tasks WHERE status='completed' "
                    "AND focus_rating IS NOT NULL AND energy_rating IS NOT NULL AND productivity_rating IS NOT NULL "
                    "GROUP BY user_id"
                ).fetchall()
                result["rl_eligible_episodes_per_user"] = {str(uid): cnt for uid, cnt in rl_episodes}
                result["rl_total_eligible"] = sum(cnt for _, cnt in rl_episodes)
        except Exception as e:
            result["rl_episode_error"] = str(e)

    conn.close()
    return result

# Also compute what db.py resolves to
def compute_db_py_paths():
    """Show what the committed and modified db.py resolve to."""
    db_py = Path(r"e:\quantum_life_ai\backend\app\database\db.py")
    # Current (modified) version uses parents[3]
    current_root = db_py.resolve().parents[3]
    current_default = current_root / "behavior_engine.db"
    # Committed version used parents[2]
    committed_root = db_py.resolve().parents[2]
    committed_default = committed_root / "behavior_engine.db"
    return {
        "db_py_location": str(db_py.resolve()),
        "committed_parents_2_root": str(committed_root),
        "committed_default_sqlite_path": str(committed_default),
        "committed_default_sqlite_exists": committed_default.exists(),
        "modified_parents_3_root": str(current_root),
        "modified_default_sqlite_path": str(current_default),
        "modified_default_sqlite_exists": current_default.exists(),
    }

if __name__ == "__main__":
    print("=" * 80)
    print("PHASE F13.2 — DATABASE AUDIT (READ-ONLY)")
    print("=" * 80)

    print("\n--- db.py Path Resolution ---")
    paths_info = compute_db_py_paths()
    print(json.dumps(paths_info, indent=2))

    print("\n--- DATABASE_URL Environment Variable ---")
    db_url = os.environ.get("DATABASE_URL", "<NOT SET>")
    print(f"DATABASE_URL = {db_url}")

    for db_path in DB_PATHS:
        print(f"\n{'=' * 80}")
        print(f"AUDITING: {db_path}")
        print("=" * 80)
        info = audit_db(db_path)
        # Print all info except tasks_columns (too verbose), but include it
        print(json.dumps(info, indent=2, default=str))
