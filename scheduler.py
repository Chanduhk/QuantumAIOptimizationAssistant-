from datetime import datetime


class Scheduler:
    def __init__(self, day, energy_profile):
        self.day = day
        self.energy = energy_profile
        self.schedule = {
            "morning": [],
            "afternoon": [],
            "evening": []
        }

        self.block_hours = {
            "morning": 3,
            "afternoon": 3,
            "evening": 2
        }

    def generate_schedule(self):
        tasks_sorted = sorted(
            self.day.tasks,
            key=lambda t: t.urgency_score(),
            reverse=True
        )

        for task in tasks_sorted:

            # Energy-aware preference
            if task.priority >= 8:
                preferred_blocks = ["morning", "afternoon", "evening"]
            elif task.priority >= 5:
                preferred_blocks = ["afternoon", "morning", "evening"]
            else:
                preferred_blocks = ["evening", "afternoon", "morning"]

            for block in preferred_blocks:
                if task.duration <= self.block_hours[block]:
                    self.schedule[block].append(task)
                    self.block_hours[block] -= task.duration
                    break

        return self.schedule

    def print_schedule(self):
        for block, tasks in self.schedule.items():
            print(f"\n{block.upper()}:")
            for task in tasks:
                print(f"  - {task}")

    
    # 👇 THIS MUST BE INDENTED INSIDE CLASS
    def generate_with_strategy(self, strategy="urgency"):
        import random
        import copy

        self.schedule = {
            "morning": [],
            "afternoon": [],
            "evening": []
        }

        self.block_hours = {
            "morning": 3,
            "afternoon": 3,
            "evening": 2
        }

        if strategy == "urgency":
            tasks_sorted = sorted(
                self.day.tasks,
                key=lambda t: t.urgency_score(),
                reverse=True
            )

        elif strategy == "priority":
            tasks_sorted = sorted(
                self.day.tasks,
                # Use effective priority so deferred tasks can climb over time.
                key=lambda t: t.effective_priority(),
                reverse=True
            )

        elif strategy == "random":
            tasks_sorted = self.day.tasks[:]
            random.shuffle(tasks_sorted)

        elif strategy == "reverse":
            tasks_sorted = sorted(
                self.day.tasks,
                key=lambda t: t.urgency_score()
            )

        else:
            tasks_sorted = self.day.tasks[:]

        for task in tasks_sorted:
            for block in ["morning", "afternoon", "evening"]:
                if task.duration <= self.block_hours[block]:
                    self.schedule[block].append(task)
                    self.block_hours[block] -= task.duration
                    break

        return copy.deepcopy(self.schedule)
    
    def generate_from_order(self, ordered_tasks):
        import copy
        self.schedule = {
            "morning": [],
            "afternoon": [],
            "evening": []
        }

        self.block_hours = {
            "morning": 3,
            "afternoon": 3,
            "evening": 2
        }

        for task in ordered_tasks:
            for block in ["morning", "afternoon", "evening"]:
                if task.duration <= self.block_hours[block]:
                   self.schedule[block].append(task)
                   self.block_hours[block] -= task.duration
                   break

        return copy.deepcopy(self.schedule)

        

    
