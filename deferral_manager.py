"""
Strategic Deferral Layer

When backlog overload is detected, this module:
1. Identifies lowest-value tasks as deferral candidates
2. Explicitly marks them as "deferred"
3. Reduces their artificially-inflated urgency
4. Re-enables them after fairness window (prevents permanent deferral)
5. Preserves long-term scheduling fairness

This prevents urgency explosion where delayed tasks become artificially
critical, enabling the system to make rational decisions about what can
safely wait without injecting false urgency.

Design Principles:
- Defer only when overload threshold exceeded
- Defer lowest-value tasks first (priority + lookahead value)
- Re-enable after 3+ day fairness window
- Reduce urgency by 70% while deferred (not 0%, for safety)
- Prevent permanent deferral via fairness tracking
"""

from typing import List, Tuple
from datetime import datetime, timedelta
from models import Task
from day_model import Day


class DeferralManager:
    """
    Manage strategic task deferral to reduce urgency explosion.
    
    When the backlog becomes overloaded (total_hours > capacity × 2+),
    this manager identifies and defers the lowest-value tasks,
    reducing their false urgency while preserving fairness through
    automatic re-enablement after a fairness window.
    
    Attributes:
        overload_threshold: Ratio of total_hours/capacity triggering deferral
        deferral_reduction: Urgency reduction factor while deferred (0.0-1.0)
        fairness_window: Days before automatically re-enabling deferred task
        max_deferrals_per_task: Maximum consecutive deferrals to prevent permanent deferral
    """
    
    def __init__(
        self, 
        overload_threshold: float = 2.0,
        deferral_reduction: float = 0.7,
        fairness_window: int = 3,
        max_deferrals_per_task: int = 2
    ):
        """
        Initialize Strategic Deferral Manager.
        
        Args:
            overload_threshold: Backlog ratio (hours/capacity) triggering deferral
                               (default 2.0 = 200% overload)
            deferral_reduction: Multiply urgency by (1 - reduction) while deferred
                               (default 0.7 = reduce to 30% of urgency)
            fairness_window: Days before automatically re-enabling deferred task
                            (default 3 days)
            max_deferrals_per_task: Prevent permanent deferral after N consecutive
                                   deferrals (default 2)
        """
        self.overload_threshold = overload_threshold
        self.deferral_reduction = deferral_reduction
        self.fairness_window = fairness_window
        self.max_deferrals_per_task = max_deferrals_per_task

    def should_defer(self, day: Day, backlog: List[Task]) -> bool:
        """
        Determine if backlog is overloaded enough to warrant deferral.
        
        Deferral is triggered when:
            total_backlog_hours / available_capacity > overload_threshold
        
        Example: If 16 hours of work and 8 hours available, ratio is 2.0
        With default threshold 2.0, deferral is triggered.
        
        Args:
            day: Day object with available_hours capacity
            backlog: Current task backlog
            
        Returns:
            True if deferral should be considered, False otherwise
        """
        if not backlog:
            return False
        
        total_hours = sum(task.duration for task in backlog)
        ratio = total_hours / day.available_hours
        
        return ratio > self.overload_threshold

    def identify_deferral_candidates(
        self,
        backlog: List[Task]
    ) -> List[Tuple[Task, float]]:
        """
        Identify tasks suitable for deferral, ranked by deferral value.
        
        Deferral candidates are lowest-value tasks that can be safely
        deferred without breaking critical path. Ranked by:
        1. Already deferred? (deferred tasks preferred, update expiry)
        2. Low urgency score (defer what's least urgent)
        3. Low priority (defer low-importance work)
        4. Not yet at max deferrals (prevent permanent deferral)
        
        Args:
            backlog: Current task backlog
            
        Returns:
            List of (Task, deferral_score) tuples, ranked by deferral score
            (higher score = better candidate for deferral)
        """
        candidates = []
        
        for task in backlog:
            # Don't defer if already at max deferrals (fairness)
            if task.deferral_count >= self.max_deferrals_per_task:
                continue
            
            # Calculate deferral score
            # Prefer low priority + low urgency
            urgency = task.urgency_score()
            priority = task.priority
            
            # Already deferred? Give highest priority to just extend vs. new deferral
            if task.deferred:
                # Boost score to keep existing deferrals (less disruptive)
                deferral_score = 100.0 + (10.0 - priority)
            else:
                # New deferral candidate
                deferral_score = (10.0 - priority) * (1.0 / (1.0 + urgency))
            
            candidates.append((task, deferral_score))
        
        # Sort by deferral score (descending = best candidates first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates

    def mark_deferred(
        self, 
        task: Task, 
        reason: str = "backlog_overload"
    ) -> None:
        """
        Mark a task as deferred and reduce its urgency.
        
        When a task is marked deferred:
        1. Set deferred flag to True
        2. Record deferral start time
        3. Increment deferral count
        4. Log reason for visibility
        
        The urgency reduction happens automatically in Task.urgency_score()
        when it checks the deferred flag.
        
        Args:
            task: Task to defer
            reason: Reason for deferral (for logging/debugging)
        """
        if not task.deferred:
            task.deferred = True
            task.deferral_start_time = datetime.now()
            task.deferral_count += 1
            task.deferral_reason = reason

    def check_fairness_window(self, task: Task) -> bool:
        """
        Check if a deferred task's fairness window has expired.
        
        After fairness_window days of deferral, the task is automatically
        re-enabled to prevent permanent deferral. The system will have time
        to address it or it will become urgent via normal decay.
        
        Args:
            task: Potentially deferred task
            
        Returns:
            True if deferral window expired (should re-enable), False if current
        """
        if (
            not task.deferred
            or not hasattr(task, 'deferral_start_time')
            or task.deferral_start_time is None
        ):
            return False
        
        days_deferred = (datetime.now() - task.deferral_start_time).days
        return days_deferred > self.fairness_window

    def revert_deferral(self, task: Task) -> None:
        """
        Re-enable a task after fairness window expires.
        
        Fairness window is critical: prevents permanent deferral of
        low-priority work while ensuring system revisits all tasks
        periodically. Task becomes eligible for selection again.
        
        Args:
            task: Deferred task to re-enable
        """
        if task.deferred:
            task.deferred = False
            task.deferral_start_time = None

    def apply_deferral_strategy(
        self, 
        day: Day, 
        backlog: List[Task],
        deferral_count_target: int = 2
    ) -> Tuple[List[Task], int]:
        """
        Apply deferral strategy: identify overload, defer lowest-value tasks.
        
        Main entry point for deferral logic. When overload is detected:
        1. Identify deferral candidates
        2. Defer lowest-value tasks until backlog becomes manageable
        3. Return updated backlog with deferred flags set
        4. Caller removes deferred tasks from selection
        
        Ensures deferrals don't accumulate - only applies when needed.
        
        Args:
            day: Day object with capacity
            backlog: Current task backlog
            deferral_count_target: Target number of tasks to defer
                                  (default 2, tunable based on severity)
            
        Returns:
            Tuple of:
            - Updated backlog (with deferred flags set)
            - Number of tasks actually deferred
        """
        # Check: Is deferral warranted?
        if not self.should_defer(day, backlog):
            # Check fairness windows anyway (re-enable if time passed)
            for task in backlog:
                if self.check_fairness_window(task):
                    self.revert_deferral(task)
            return backlog, 0
        
        # Get candidates ranked by deferral value
        candidates = self.identify_deferral_candidates(backlog)
        
        if not candidates:
            return backlog, 0
        
        # Defer top N candidates
        deferred_count = 0
        for task, score in candidates[:deferral_count_target]:
            self.mark_deferred(task, reason="backlog_overload")
            deferred_count += 1
        
        # Re-enable any whose fairness window expired
        for task in backlog:
            if self.check_fairness_window(task):
                self.revert_deferral(task)
        
        return backlog, deferred_count

    def get_deferral_status_report(self, backlog: List[Task]) -> str:
        """
        Generate human-readable report of current deferral status.
        
        Useful for debugging and understanding system behavior:
        - Which tasks are deferred?
        - How long have they been deferred?
        - Why were they deferred?
        
        Args:
            backlog: Current task backlog
            
        Returns:
            Formatted string status report
        """
        deferred_tasks = [t for t in backlog if t.deferred]
        
        if not deferred_tasks:
            return "No tasks currently deferred."
        
        report = f"DEFERRAL STATUS ({len(deferred_tasks)} deferred):\n"
        
        for task in deferred_tasks:
            d_time = 0
            if hasattr(task, 'deferral_start_time') and task.deferral_start_time:
                d_time = (datetime.now() - task.deferral_start_time).days
            
            reason = getattr(task, 'deferral_reason', 'unknown')
            
            report += (f"  • {task.name} (defer count: {task.deferral_count}, "
                      f"days deferred: {d_time}, reason: {reason})\n")
        
        return report
