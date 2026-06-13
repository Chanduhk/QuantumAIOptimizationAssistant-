"""
Quick test script to verify Strategic Compression Layer is activated.
This is a minimal test that bypasses the full GA/Monte Carlo pipeline.
"""

from datetime import datetime, timedelta
from models import Task, EnergyProfile
from day_model import Day
from scheduler import Scheduler
from forecast import MultiDayForecaster

print("=" * 70)
print("COMPRESSION LAYER FIX VERIFICATION TEST")
print("=" * 70)

# Create tasks that will trigger overload
# Need 80+ hours to exceed 2.0x with 5-day horizon
# 80 / (8 x 5) = 2.0x - at threshold
# 87 / (8 x 5) = 2.175x - exceeds threshold!
now = datetime.now()

tasks = [
    Task("Research Deep Dive", 9, 9, now + timedelta(hours=72)),
    Task("Architecture Design", 9, 9, now + timedelta(hours=48)),
    Task("Database Migration", 8, 9, now + timedelta(hours=96)),
    Task("Code Refactoring", 8, 8, now + timedelta(hours=60)),
    Task("Project Planning", 8, 8, now + timedelta(hours=84)),
    Task("Performance Tuning", 8, 7, now + timedelta(hours=36)),
    Task("Security Audit", 8, 7, now + timedelta(hours=40)),
    Task("Documentation", 6, 6, now + timedelta(hours=30)),
    Task("Team Review", 6, 6, now + timedelta(hours=25)),
    Task("System Testing", 6, 5, now + timedelta(hours=15)),
    Task("Admin Work", 5, 3, now + timedelta(hours=20)),
]

total_hours = sum(t.duration for t in tasks)
print("\nTEST SETUP (Overload Scenario):")
print("Total Tasks: " + str(len(tasks)))
print("Total Hours: " + str(total_hours) + "h")
print("Daily Capacity: 8h")
print("Planning Horizon: 5 days")
print("Available Capacity: 40h")
overload_ratio = total_hours / (8 * 5)
print("Expected Overload: {:.2f}x".format(overload_ratio))
print("Compression Threshold: 2.0x")
should_activate = "SHOULD ACTIVATE" if overload_ratio > 2.0 else "WILL NOT ACTIVATE"
print("Status: " + should_activate)

# Create day and add tasks
day = Day(available_hours=8, sleep_hours=7)
for task in tasks:
    day.add_task(task)

# Create scheduler and energy profile
energy = EnergyProfile()
scheduler = Scheduler(day, energy)

# Run forecaster - compression should activate BEFORE the loop
print("\nRunning MultiDayForecaster with compression...")
print("(Look for [COMPRESSION MODE ACTIVATED] in output)\n")

forecaster = MultiDayForecaster(day, scheduler, days=5)

# This will trigger compression in simulate()
score = forecaster.simulate()

print("\nFinal Score: {:.3f}".format(score))
print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
