import sqlite3

def audit():
    for db_path in ['behavior_engine.db', 'backend/behavior_engine.db']:
        print(f"=== {db_path} ===")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        integrity = cur.execute("PRAGMA integrity_check;").fetchone()[0]
        print(f"Integrity: {integrity}")
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        print("Tables:", tables)
        for t in tables:
            cnt = cur.execute(f"SELECT COUNT(*) FROM {t};").fetchone()[0]
            print(f"  {t}: {cnt} rows")

if __name__ == "__main__":
    audit()
