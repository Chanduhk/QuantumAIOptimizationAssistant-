"""Day evaluation metrics and scoring."""
from typing import Any, Dict


class DayEvaluator:
    """Evaluate the quality of a day's schedule across multiple metrics."""

    def __init__(self, day: Any, schedule: Dict[str, Any]) -> None:
        """Initialize the evaluator with a day and schedule.
        
        Args:
            day: Day object with tasks and available_hours
            schedule: Dictionary mapping time blocks to task lists
        """
        self.day = day
        self.schedule = schedule

    def productivity_score(self) -> float:
        """Calculate productivity score based on task hours filled.
        
        Returns:
            Score between 0 and 1 representing task hours / available hours
        """
        return min(self.day.total_task_hours() / self.day.available_hours, 1)

    def priority_score(self) -> float:
        """Calculate priority score based on scheduled priority vs total priority.
        
        Returns:
            Score between 0 and 1 representing priority fulfillment
        """
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

    def energy_alignment_score(self) -> float:
        """Calculate how well tasks align with energy blocks.
        
        Returns:
            Score between 0 and 1 representing alignment quality
        """
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

    def stress_penalty(self) -> float:
        """Calculate stress penalty for overloaded days.
        
        Returns:
            Penalty between 0 (no overload) and 1 (extreme overload)
        """
        overload = self.day.overload_score()
        if overload <= 1:
            return 0
        return min(overload - 1, 1)

    def total_score(self) -> float:
        """Calculate weighted total score across all metrics.
        
        Returns:
            Score between 0 and 1, rounded to 3 decimals
        """
        productivity = self.productivity_score()
        priority = self.priority_score()
        alignment = self.energy_alignment_score()
        stress = self.stress_penalty()

        # Weighted combination: 30% productivity, 30% priority, 30% alignment, -30% stress
        score = (
            0.3 * productivity +
            0.3 * priority +
            0.3 * alignment -
            0.3 * stress
        )

        return round(score, 3)
