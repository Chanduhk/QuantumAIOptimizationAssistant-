"""Day model representing a single day with available hours and tasks."""


class Day:
    """Represents a single day with available hours and scheduled tasks."""

    def __init__(self, available_hours, sleep_hours):
        """Initialize a Day.
        
        Args:
            available_hours: Total hours available for tasks (excluding sleep)
            sleep_hours: Hours allocated for sleep
        """
        self.available_hours = available_hours
        self.sleep_hours = sleep_hours
        self.tasks = []

    def add_task(self, task):
        """Add a task to the day.
        
        Args:
            task: Task object with duration attribute
        """
        self.tasks.append(task)

    def total_task_hours(self):
        """Calculate total hours of all tasks.
        
        Returns:
            Sum of duration for all tasks
        """
        return sum(task.duration for task in self.tasks)

    def overload_score(self):
        """Calculate how much the day is overloaded.
        
        Returns:
            Ratio of total task hours to available hours
        """
        return self.total_task_hours() / self.available_hours
