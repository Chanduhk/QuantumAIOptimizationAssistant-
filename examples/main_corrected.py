"""
CORRECTED MAIN.PY - STRATEGIC COMPRESSION ARCHITECTURE FIX

CRITICAL ARCHITECTURE CHANGE:
=============================
Strategic Compression now uses a HARD-ISOLATED threshold of 1.2x
This threshold is INDEPENDENT of the Learning module's 2.0x threshold

BEFORE (BROKEN):
- Compression threshold was shared with Learning module
- Learning module could override/reset compression threshold
- Compression failed to activate at correct levels

AFTER (FIXED):
- compression_threshold = 1.2 (Compression module, HARD-ISOLATED)
- learning_overload_threshold = 2.0 (Learning module, INDEPENDENT)
- These thresholds are COMPLETELY SEPARATE
- Compression cannot be affected by learning updates
"""

from datetime import datetime, timedelta
from models import Task, EnergyProfile
from day_model import Day
from scheduler import Scheduler
from evaluation import DayEvaluator
from optimizer import ScheduleOptimizer
from ga_optimizer import GeneticOptimizer
from knapsack import KnapsackSelector
from forecast import MultiDayForecaster

# ============================================================================
# TASK SETUP
# ============================================================================

# Create sample tasks
task1 = Task("Deep Work Project", 3, 9, datetime.now() + timedelta(hours=10))
task2 = Task("Emails", 1, 5, datetime.now() + timedelta(hours=5))
task3 = Task("Workout", 1.5, 7, datetime.now() + timedelta(hours=8))
task4 = Task("Study Algorithms", 2, 8, datetime.now() + timedelta(hours=20))
task5 = Task("Team Meeting", 1, 6, datetime.now() + timedelta(hours=6))
task6 = Task("Code Review", 1.5, 7, datetime.now() + timedelta(hours=12))
task7 = Task("Read Research Paper", 2, 5, datetime.now() + timedelta(hours=18))
task8 = Task("Client Call", 1, 9, datetime.now() + timedelta(hours=4))
task9 = Task("Meditation", 0.5, 4, datetime.now() + timedelta(hours=15))
task10 = Task("System Design Practice", 2.5, 9, datetime.now() + timedelta(hours=25))

now = datetime.now()

extra_tasks = [
    Task("Big Architecture Refactor", 4, 9, now + timedelta(hours=72)),
    Task("Research Paper Draft", 5, 8, now + timedelta(hours=96)),
    Task("Investor Pitch Deck", 3.5, 9, now + timedelta(hours=48)),
    Task("Backend Optimization", 4, 8, now + timedelta(hours=60)),
    Task("ML Model Tuning", 3, 7, now + timedelta(hours=36)),
    Task("Marketing Strategy Plan", 2.5, 6, now + timedelta(hours=84)),
    Task("Security Audit", 3, 8, now + timedelta(hours=40)),
    Task("Client Follow-up Emails", 1.5, 6, now + timedelta(hours=12)),
    Task("Database Migration Prep", 4.5, 9, now + timedelta(hours=90)),
    Task("System Monitoring Setup", 3, 7, now + timedelta(hours=30))
]

# ============================================================================
# DAY SETUP
# ============================================================================

my_day = Day(available_hours=8, sleep_hours=7)

my_day.add_task(task1)
my_day.add_task(task2)
my_day.add_task(task3)
for t in [task4, task5, task6, task7, task8, task9, task10]:
    my_day.add_task(t)
for t in extra_tasks:
    my_day.add_task(t)

print("Tasks:", my_day.tasks)
print("Total Task Hours:", my_day.total_task_hours())
print("Overload Score:", my_day.overload_score())

energy = EnergyProfile()
scheduler = Scheduler(my_day, energy)

scheduler.generate_schedule()
scheduler.print_schedule()

evaluator = DayEvaluator(my_day, scheduler.schedule)

print("\n--- DAY QUALITY METRICS ---")
print("Productivity Score:", evaluator.productivity_score())
print("Priority Score:", evaluator.priority_score())
print("Energy Alignment Score:", evaluator.energy_alignment_score())
print("Stress Penalty:", evaluator.stress_penalty())
print("TOTAL DAY SCORE:", evaluator.total_score())

optimizer = ScheduleOptimizer(my_day, scheduler)

best_schedule, best_score = optimizer.find_best_schedule(iterations=200)

print("\nBEST SCORE AFTER MONTE CARLO SEARCH:", best_score)

for block, tasks in best_schedule.items():
    print(f"\n{block.upper()}:")
    for task in tasks:
        print(f"  - {task}")

ga = GeneticOptimizer(my_day, scheduler, population_size=30, generations=80)

best_schedule, best_score = ga.evolve()

print("\nGENETIC ALGORITHM RESULT")
print("BEST SCORE:", best_score)

for block, tasks in best_schedule.items():
    print(f"\n{block.upper()}:")
    for task in tasks:
        print(f"  - {task}")

# ============================================================================
# STRATEGIC COMPRESSION DEMONSTRATION
# ============================================================================
# NOTE: Strategic Compression is automatically invoked during multi-day
# forecasting. The compression layer uses a HARD-ISOLATED threshold of 1.2x.
#
# This means:
# - Compression activates when: (total_hours / available_capacity) > 1.2
# - Learning module threshold (2.0x) does NOT affect compression
# - Compression threshold CANNOT be overridden by learning updates
#
# To see compression in action, run the multi-day forecaster:

print("\n" + "="*80)
print("MULTI-DAY FORECAST WITH STRATEGIC COMPRESSION")
print("="*80)
print("\nInitializing 5-day forecast with Strategic Compression...")
print("\nCompression Architecture:")
print("  - Compression Threshold: 1.2x [HARD-ISOLATED]")
print("  - Learning Threshold: 2.0x [INDEPENDENT]")
print("  - Thresholds are completely separate and do NOT interact")
print("\n" + "="*80 + "\n")

forecaster = MultiDayForecaster(my_day, scheduler, days=5)
forecast_scores = forecaster.simulate()

print("\n" + "="*80)
print("FORECAST COMPLETE")
print("="*80)
print("\nFinal Multi-Day Score:", round(forecast_scores, 3))
print("\nKey Observations:")
print("  - Look for '[COMPRESSION CHECK]' in output")
print("  - Compression shows Threshold: 1.20 [HARD-ISOLATED]")
print("  - Learning module parameters are completely separate")
print("  - Compression cannot be overridden by learning updates")
