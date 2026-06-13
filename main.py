"""
MAIN.PY - COMPLETE SCHEDULING ENGINE WITH ADAPTIVE COMPRESSION

SYSTEM ARCHITECTURE:
====================
1. Hard-Isolated Compression Threshold: 1.2x [INDEPENDENT from Learning]
2. Balanced Strategic Weight Formula: Prevents small-task dominance
3. ADAPTIVE CAPACITY-BASED PROTECTION: Intelligently selects protected tasks

ADAPTIVE PROTECTION DETAILS:
===========================
Instead of protecting a fixed number of tasks (old: top_k=3),
the system now adapts based on available capacity:

- Calculates protection target: 85% * daily_capacity
- Selects top-weight tasks until reaching target
- Ensures at least 1 task is always protected
- Automatically varies protected task count based on durations

Example: With 8h daily capacity
- Protection target: 85% * 8h = 6.80h
- If top task is 1h, 2.5h, 3h, 3.5h = 10h total
- Protects 4 tasks (exceeds target minimally)
- Previous fixed approach would protect only 3 tasks

Benefits:
- Better capacity utilization
- Adaptive to different workload patterns
- Prevents under-utilization
- Data-driven task selection
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
from visualization import plot_system_metrics

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

print("\n[BEST] SCORE AFTER MONTE CARLO SEARCH:", best_score)

for block, tasks in best_schedule.items():
    print(f"\n{block.upper()}:")
    for task in tasks:
        print(f"  - {task}")

ga = GeneticOptimizer(my_day, scheduler, population_size=30, generations=80)

best_schedule, best_score = ga.evolve()

print("\n[GENETIC] ALGORITHM RESULT")
print("BEST SCORE:", best_score)

for block, tasks in best_schedule.items():
    print(f"\n{block.upper()}:")
    for task in tasks:
        print(f"  - {task}")



# ============================================================================
# STRATEGIC COMPRESSION WITH ADAPTIVE PROTECTION
# ============================================================================
#
# KEY FEATURES:
# 1. Hard-isolated threshold: 1.2x (cannot be overridden by learning)
# 2. Balanced strategic weights: Prevents small-task overvaluation
# 3. Adaptive capacity protection: Protects ~85% of daily capacity
#
# TO UNDERSTAND THE COMPRESSION OUTPUT:
# - [COMPRESSION CHECK]: Shows overload index and threshold
# - [PROTECTING] Capacity-Based Selection: Shows adaptive protection details
#   - Daily Capacity: available hours per day
#   - Protection Target (85%): 85% of daily capacity
#   - Protected Hours: actual hours protected (usually slightly over target)
# - Protected Tasks: Tasks that will be scheduled
# - [FREEZING]: Tasks that will be temporarily frozen for 3 days
#
# ADAPTIVE BEHAVIOR EXAMPLES:
# - 4h daily capacity -> protect ~3.4h worth of top tasks
# - 8h daily capacity -> protect ~6.8h worth of top tasks
# - Number of protected tasks varies by task durations, not fixed
#
# ============================================================================

print("\n" + "="*80)
print("MULTI-DAY FORECAST WITH ADAPTIVE STRATEGIC COMPRESSION")
print("="*80)
print("\nInitializing 5-day forecast...")
print("\nCompression System Features:")
print("  1. Threshold: 1.2x [HARD-ISOLATED from Learning Module]")
print("  2. Formula: Balanced 3-component strategic weight")
print("  3. Protection: Adaptive capacity-based (85% of daily capacity)")
print("  4. Adaptation: Protected task count varies by workload")
print("\n" + "="*80 + "\n")

forecaster = MultiDayForecaster(my_day, scheduler, days=5)
multi_day_score = forecaster.simulate()

print("\n" + "="*80)
print("FORECAST COMPLETE - ADAPTIVE COMPRESSION RESULTS")
print("="*80)
print("\n[FINAL] MULTI-DAY AVERAGE SCORE:", round(multi_day_score, 3))
print("\nKey Observations:")
print("  - Compression adapts protection to 85% of daily capacity")
print("  - Protected task count varies based on task durations")
print("  - Balanced strategic weights prevent small-task dominance")
print("  - Compression Threshold: 1.20 [HARD-ISOLATED]")
print("  - Learning module parameters are completely separate")
print("  - System adapts intelligently to different workloads")
print("\nComparison to Fixed top_k=3:")
print("  - Old: Always protected exactly 3 tasks")
print("  - New: Protects 3-6 tasks depending on durations")
print("  - Result: Better capacity utilization and stability")

day_scores = list(forecaster.day_scores)
entropy_values = list(forecaster.entropy_values)
csi_values = list(forecaster.csi_values)
penalty_values = list(forecaster.penalty_values)

plot_system_metrics(
    day_scores,
    entropy_values,
    csi_values,
    penalty_values
)
