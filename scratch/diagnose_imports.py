import time

def step(msg):
    global last_t
    now = time.time()
    print(f"[{now - t0:6.2f}s] (+{now - last_t:5.2f}s) {msg}", flush=True)
    last_t = now

t0 = time.time()
last_t = t0

step("Start")
import os
import numpy as np
step("Imported numpy")
from fastapi import FastAPI
step("Imported FastAPI")
from backend.app.database.db import create_tables, get_db
step("Imported db")
from backend.app.adaptive import AdaptiveScheduler
step("Imported AdaptiveScheduler")
from backend.app.engines import QuantumLifeBrain
step("Imported QuantumLifeBrain")
from backend.app.interface import AIInteractionLayer
step("Imported AIInteractionLayer")
from backend.app.memory import VectorMemorySystem
step("Imported VectorMemorySystem")
from backend.app.learning import AutonomousLearningLoop
step("Imported AutonomousLearningLoop")
from backend.app.orchestrator import AIOrchestrator
step("Imported AIOrchestrator")
from backend.app.pipeline import DecisionPipeline
step("Imported DecisionPipeline")
from backend.app.recommendation import RecommendationEngine
step("Imported RecommendationEngine")
from backend.app.services.behavior_engine import BehaviorIntelligenceEngine
step("Imported BehaviorIntelligenceEngine")
from backend.app.services.task_lifecycle_service import TaskLifecycleService
step("Imported TaskLifecycleService")
from backend.app.ml.datasets import DatasetQualityAuditor, TaskCollectionReporter, TaskDataExtractor
step("Imported ml datasets")
from backend.app.services.auth_service import register_user
step("Imported auth_service")
import backend.main
step("Imported backend.main")
print("Done!")
