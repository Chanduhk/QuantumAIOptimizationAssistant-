import sqlite3

con = sqlite3.connect("behavior_engine.db")
cur = con.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

total_tasks = cur.execute("SELECT count(*) FROM tasks").fetchone()[0]
print("Total tasks:", total_tasks)

for table in tables:
    cols = cur.execute(f"PRAGMA table_info({table})").fetchall()
    print(f"\nSchema for {table}:")
    for col in cols:
        print(f"  {col[1]} ({col[2]})")

print("\n--- Tasks Dump ---")
tasks = cur.execute("SELECT * FROM tasks").fetchall()
print(f"Total rows in tasks: {len(tasks)}")
for t in tasks:
    print(t)

print("\n--- Behavior Data Dump ---")
bdata = cur.execute("SELECT * FROM behavior_data").fetchall()
print(f"Total rows in behavior_data: {len(bdata)}")
for b in bdata:
    print(b)


print("\n--- Users (id, is_active) ---")
users = cur.execute("SELECT id, is_active FROM users").fetchall()
print(users)
con.close()
