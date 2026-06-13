from asyncio import tasks



class KnapsackSelector:
    def __init__(self, day):
        self.day = day
    

    def select_tasks(self):
        tasks = self.day.tasks
        n = len(tasks)

        scale = 2  # convert 0.5 increments to integers
        capacity = int(self.day.available_hours * scale)

        weights = [int(task.duration * scale) for task in tasks]
        gamma = 0.6  # lookahead weight

        values = []
        for task in tasks:
            today_value = task.urgency_score()

            # simulate delay effect
            simulated_delay = task.delay_count + 1
            delay_factor = 0.25

            tomorrow_value = today_value * (1 + delay_factor * simulated_delay)

            lookahead_value = today_value + gamma * tomorrow_value

            values.append(lookahead_value)


        # DP table
        dp = [[0 for _ in range(capacity + 1)] for _ in range(n + 1)]

        # Build table
        for i in range(1, n + 1):
            for w in range(capacity + 1):
                if weights[i - 1] <= w:
                    dp[i][w] = max(
                        values[i - 1] + dp[i - 1][w - weights[i - 1]],
                        dp[i - 1][w]
                    )
                else:
                    dp[i][w] = dp[i - 1][w]

        # Backtrack to find selected tasks
        selected_tasks = []
        w = capacity
        for i in range(n, 0, -1):
            if dp[i][w] != dp[i - 1][w]:
                selected_tasks.append(tasks[i - 1])
                w -= weights[i - 1]

        return selected_tasks[::-1]

