import sqlite3
import os

dbs = [
    './behavior_engine.db',
    './backend/behavior_engine.db',
    './backend/behavior_engine_demo.db',
    './data/quantum_life.db'
]

for db in dbs:
    if os.path.exists(db):
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        tables = [t[0] for t in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() if not t[0].startswith('sqlite_')]
        counts = {}
        for t in tables:
            counts[t] = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"=== {db} (size: {os.path.getsize(db)} bytes) ===")
        print(counts)
        if "tasks" in tables:
            try:
                tasks = cur.execute("SELECT id, title, lifecycle_state, actual_duration, outcome_valid, focus_rating FROM tasks").fetchall()
                print("Tasks sample/all:", tasks[:10])
            except Exception as e:
                print("Tasks schema variation:", e)
                cols = [c[1] for c in cur.execute("PRAGMA table_info(tasks)").fetchall()]
                print("Columns:", cols)
        conn.close()
    else:
        print(f"=== {db} DOES NOT EXIST ===")
