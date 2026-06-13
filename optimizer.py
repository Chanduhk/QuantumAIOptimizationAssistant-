import random
from evaluation import DayEvaluator

class ScheduleOptimizer:
    def __init__(self, day, scheduler):
        self.day = day
        self.scheduler = scheduler

    def find_best_schedule(self, iterations=100):
        best_score = -1
        best_schedule = None

        for i in range(iterations):
            # Random strategy each iteration
            schedule = self.scheduler.generate_with_strategy("random")

            evaluator = DayEvaluator(self.day, schedule)
            score = evaluator.total_score()

            if score > best_score:
                best_score = score
                best_schedule = schedule

        return best_schedule, best_score