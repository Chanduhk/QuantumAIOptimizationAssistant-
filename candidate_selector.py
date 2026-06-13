"""
Multi-Candidate Lookahead Selection

Instead of selecting tasks via a single knapsack solution, this module generates
3-5 high-value candidate subsets using different strategies and selects the one
with the best future-adjusted (2-day lookahead) score.

Computation is bounded by limiting candidate generation strategies to:
1. Standard knapsack (optimal value-weight)
2. Priority-weighted variant (emphasize high-priority tasks)
3. Deadline-first variant (emphasize urgent deadlines)

This keeps the search space manageable while capturing diverse selection strategies.
"""

from typing import List, Tuple
import copy
from knapsack import KnapsackSelector
from lookahead import TwoDaySimulator
from models import Task
from day_model import Day


class MultiCandidateLookahead:
    """
    Generate and evaluate multiple high-value task subset candidates.
    
    This class generates 3-5 candidate subsets using different selection strategies
    and evaluates each using 2-day lookahead simulation. The candidate with the
    highest future-adjusted score is returned.
    
    Attributes:
        scheduler: Scheduler instance for generating schedules from task orders
        num_candidates: Maximum number of candidates to generate (capped at 5)
    """
    
    def __init__(self, scheduler, num_candidates: int = 3):
        """
        Initialize Multi-Candidate Lookahead selector.
        
        Args:
            scheduler: Scheduler instance for generating schedules
            num_candidates: Target number of candidates (default 3, capped at 5)
        """
        self.scheduler = scheduler
        self.num_candidates = min(num_candidates, 5)

    def generate_candidates(self, day: Day) -> List[List[Task]]:
        """
        Generate multiple high-value task subsets using different strategies.
        
        Generates candidates via:
        1. Standard knapsack (optimal value-weight ratio)
        2. Priority-weighted variant (emphasizes high-priority tasks)
        3. Deadline-first variant (emphasizes time-critical tasks)
        
        This bounded approach balances diversity with computational efficiency.
        
        Args:
            day: Day object with tasks to select from
            
        Returns:
            List of candidate task subsets, where each subset is a list of Task objects.
            Each candidate represents a different selection strategy.
        """
        candidates = []
        
        # Candidate 1: Standard knapsack (optimal value-weight)
        selector = KnapsackSelector(day)
        candidate1 = selector.select_tasks()
        candidates.append(candidate1)
        
        if len(candidates) >= self.num_candidates:
            return candidates
        
        # Candidate 2: Priority-weighted variant
        # Emphasizes high-priority tasks more heavily than urgency decay
        candidate2 = self._generate_priority_variant(day)
        if candidate2 and self._is_different_subset(candidate2, candidate1):
            candidates.append(candidate2)
        
        if len(candidates) >= self.num_candidates:
            return candidates
        
        # Candidate 3: Deadline-first variant
        # Prioritizes tasks with nearest deadlines
        candidate3 = self._generate_deadline_variant(day)
        if candidate3 and self._is_different_subset(candidate3, candidate1):
            candidates.append(candidate3)
        
        return candidates

    def _generate_priority_variant(self, day: Day) -> List[Task]:
        """
        Generate candidate by emphasizing task priority over urgency decay.
        
        Uses modified knapsack with values dominated by priority (1.5x weight)
        and minimal lookahead factor. Useful when high-importance tasks should
        not be deferred.
        
        Args:
            day: Day object with tasks
            
        Returns:
            List of selected Task objects based on priority variant
        """
        tasks = day.tasks
        n = len(tasks)
        
        if n == 0:
            return []
        
        scale = 2
        capacity = int(day.available_hours * scale)
        weights = [int(task.duration * scale) for task in tasks]
        
        # Values: effective-priority dominant to include urgency decay.
        # This prevents medium-priority tasks from being permanently outranked.
        values = [task.effective_priority() * 1.5 for task in tasks]
        
        # DP table for modified knapsack
        dp = [[0 for _ in range(capacity + 1)] for _ in range(n + 1)]
        
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
        selected = []
        w = capacity
        for i in range(n, 0, -1):
            if dp[i][w] != dp[i - 1][w]:
                selected.append(tasks[i - 1])
                w -= weights[i - 1]
        
        return selected[::-1]

    def _generate_deadline_variant(self, day: Day) -> List[Task]:
        """
        Generate candidate by emphasizing deadline proximity.
        
        Greedily selects tasks with nearest deadlines first, respecting capacity.
        Useful for deadline-driven scenarios where temporal urgency dominates.
        
        Args:
            day: Day object with tasks
            
        Returns:
            List of selected Task objects sorted by deadline
        """
        if not day.tasks:
            return []
        
        # Sort by deadline (nearest first)
        sorted_tasks = sorted(day.tasks, key=lambda t: t.deadline)
        
        selected = []
        remaining_capacity = day.available_hours
        
        for task in sorted_tasks:
            if task.duration <= remaining_capacity:
                selected.append(task)
                remaining_capacity -= task.duration
        
        return selected

    def select_best_candidate(
        self, 
        day: Day, 
        backlog: List[Task]
    ) -> Tuple[List[Task], float]:
        """
        Generate candidates and select the one with highest 2-day lookahead score.
        
        This is the main entry point. Generates multiple candidates using different
        strategies and evaluates each using TwoDaySimulator (2-day future projection).
        Returns the candidate with the best future-adjusted score.
        
        Important: Uses deep copies internally to avoid mutating task state during
        evaluation of multiple candidates.
        
        Args:
            day: Original Day object (used for capacity and reference)
            backlog: Current backlog of tasks to select from
            
        Returns:
            Tuple of (best_candidate_tasks, lookahead_score) where:
            - best_candidate_tasks: List of Task objects selected
            - lookahead_score: 2-day future-adjusted score of that selection
        """
        if not backlog:
            return [], 0.0
        
        # Create evaluation copy to avoid mutations
        eval_day = copy.deepcopy(day)
        eval_day.tasks = copy.deepcopy(backlog)
        
        # Generate candidates using different strategies
        candidates = self.generate_candidates(eval_day)
        
        if not candidates:
            return [], 0.0
        
        # Evaluate each candidate using 2-day lookahead
        best_candidate = None
        best_score = -float('inf')
        
        simulator = TwoDaySimulator(self.scheduler)
        
        for candidate in candidates:
            # Create fresh copy for each candidate evaluation
            eval_copy = copy.deepcopy(day)
            eval_copy.tasks = copy.deepcopy(backlog)
            
            # Simulate the 2-day impact of this candidate
            lookahead_score = simulator.simulate(eval_copy, candidate)
            
            if lookahead_score > best_score:
                best_score = lookahead_score
                best_candidate = candidate
        
        # Return best candidate (fallback to first if all failed)
        return best_candidate if best_candidate else candidates[0], best_score

    @staticmethod
    def _is_different_subset(subset_a: List[Task], subset_b: List[Task]) -> bool:
        """
        Check if two subsets are meaningfully different.
        
        Two subsets are considered different if they contain different tasks.
        
        Args:
            subset_a: First task subset
            subset_b: Second task subset
            
        Returns:
            True if subsets differ, False if identical
        """
        names_a = {task.name for task in subset_a}
        names_b = {task.name for task in subset_b}
        return names_a != names_b
