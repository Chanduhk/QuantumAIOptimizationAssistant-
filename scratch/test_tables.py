import sys
print("Step 1: start", flush=True)

import sqlite3
print("Step 2: sqlite3 imported", flush=True)

from backend.app.models.base import Base
from backend.app.models.plan_proposal import PlanProposal
from backend.app.models.task import Task
from backend.app.models.behavior_data import BehaviorData
from backend.app.models.auth import User, AuthSession
print("Step 3: models imported", flush=True)

from backend.app.database.db import engine
print("Step 4: engine imported", flush=True)

Base.metadata.create_all(bind=engine)
print("Step 5: Base.metadata.create_all done", flush=True)

conn = sqlite3.connect("behavior_engine.db")
tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Current tables:", tables, flush=True)
conn.close()
print("All done!", flush=True)
