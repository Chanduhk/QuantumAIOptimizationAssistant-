class Day:
    def __init__(self, available_hours, sleep_hours):
        self.available_hours = available_hours
        self.sleep_hours = sleep_hours
        self.tasks = []

    def add_task(self, task):
        self.tasks.append(task)

    def total_task_hours(self):
        return sum(task.duration for task in self.tasks)

    def overload_score(self):
        return self.total_task_hours() / self.available_hours
