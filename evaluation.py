class DayEvaluator:
    def __init__(self, day, schedule):
        self.day = day
        self.schedule = schedule

    def productivity_score(self):
        return min(self.day.total_task_hours() / self.day.available_hours, 1)

    def priority_score(self):
        scheduled_tasks = [
            task
            for block in self.schedule.values()
            for task in block
        ]

        scheduled_priority = sum(task.priority for task in scheduled_tasks)
        total_priority = sum(task.priority for task in self.day.tasks)

        if total_priority == 0:
           return 0

        return scheduled_priority / total_priority


    def energy_alignment_score(self):
        score = 0
        total = 0

        for block, tasks in self.schedule.items():
            for task in tasks:
                total += 1
                if block == "morning" and task.priority >= 8:
                    score += 1
                elif block == "afternoon" and 5 <= task.priority < 8:
                    score += 1
                elif block == "evening" and task.priority < 5:
                    score += 1

        if total == 0:
            return 0

        return score / total

    def stress_penalty(self):
        overload = self.day.overload_score()
        if overload <= 1:
            return 0
        return min(overload - 1, 1)

    def total_score(self):
        productivity = self.productivity_score()
        priority = self.priority_score()
        alignment = self.energy_alignment_score()
        stress = self.stress_penalty()

        # Weighted combination
        score = (
            0.3 * productivity +
            0.3 * priority +
            0.3 * alignment -
            0.3 * stress
        )

        return round(score, 3)
