import copy
from knapsack import KnapsackSelector
from evaluation import DayEvaluator


class TwoDaySimulator:
    def __init__(self, scheduler):
        self.scheduler = scheduler

    def simulate(self, day, selected_today):
        # --- Simulate Day 1 ---
        day1 = copy.deepcopy(day)
        day1.tasks = selected_today

        schedule1 = self.scheduler.generate_from_order(selected_today)
        evaluator1 = DayEvaluator(day1, schedule1)
        score1 = evaluator1.total_score()

        # --- Build remaining backlog ---
        remaining = [
            t for t in day.tasks
            if t.name not in [x.name for x in selected_today]
        ]

        # Increase delay for remaining tasks
        for task in remaining:
            task.delay_count += 1
            task.advance_time(24)

        if not remaining:
            return score1

        # --- Simulate Day 2 ---
        day2 = copy.deepcopy(day)
        day2.tasks = remaining

        selector2 = KnapsackSelector(day2)
        selected_day2 = selector2.select_tasks()

        day2.tasks = selected_day2

        schedule2 = self.scheduler.generate_from_order(selected_day2)
        evaluator2 = DayEvaluator(day2, schedule2)
        score2 = evaluator2.total_score()

        gamma = 0.6
        return score1 + gamma * score2
