"""
Fatigue-Based Capacity Modeling

Adapts daily task capacity based on system performance and fatigue signals.

When the planning system (or human executing the plan) shows signs of being
overwhelmed:
  • Previous day score drops below 0.4
  • High deferral count (tasks repeatedly pushed aside)
  • Inability to complete planned tasks

The system proactively reduces next day capacity to:
  • Focus on quality over quantity
  • Prevent cascading failures
  • Allow recovery period
  • Enable sustainable long-term planning

When conditions improve:
  • Previous day score > 0.75 (healthy)
  • Low deferral count (good prioritization)
  • Tasks completing on schedule

The system gradually restores capacity toward original level.

This creates a self-regulating planning system that adapts to real capability.
"""

from typing import Optional
from day_model import Day


class FatigueModelingEngine:
    """
    Manage adaptive capacity adjustment based on fatigue signals.
    
    Monitors system performance (day scores, deferral patterns, completed tasks)
    and adjusts next-day capacity to maintain sustainable planning.
    
    Key Insight: Fatigue is not just about hours worked, but about
    quality of execution and accumulation of deferred work.
    
    Attributes:
        original_capacity: Initial daily available hours (reference point)
        poor_score_threshold: Below this, reduce capacity (default 0.4)
        good_score_threshold: Above this, restore capacity (default 0.75)
        min_capacity: Floor (default 4 hours, safety minimum)
        max_capacity: Ceiling (default original)
        reduction_factor: How much to reduce (default -20%)
        recovery_factor: How much to restore (default +5%)
    """
    
    def __init__(
        self,
        original_capacity: float,
        poor_score_threshold: float = 0.4,
        good_score_threshold: float = 0.75,
        min_capacity: float = 4.0,
        reduction_factor: float = 0.20,
        recovery_factor: float = 0.05
    ):
        """
        Initialize Fatigue Modeling Engine.
        
        Args:
            original_capacity: Initial daily capacity (e.g., 8 hours)
            poor_score_threshold: Score below this triggers capacity reduction
                                 (default 0.4 = 40% quality)
            good_score_threshold: Score above this triggers restoration
                                 (default 0.75 = 75% quality)
            min_capacity: Minimum allowed capacity floor (default 4 hours)
            reduction_factor: Fraction to reduce (0.20 = 20% reduction)
            recovery_factor: Fraction to restore per recovery day (0.05 = 5%)
        """
        self.original_capacity = original_capacity
        self.current_capacity = original_capacity
        
        self.poor_score_threshold = poor_score_threshold
        self.good_score_threshold = good_score_threshold
        self.min_capacity = min_capacity
        self.max_capacity = original_capacity  # Never exceed original
        
        self.reduction_factor = reduction_factor
        self.recovery_factor = recovery_factor
        
        # History tracking
        self.previous_day_score = None
        self.consecutive_poor_days = 0
        self.consecutive_good_days = 0

    def get_adjusted_capacity(
        self,
        day_score: Optional[float],
        deferral_count: int = 0
    ) -> float:
        """
        Calculate adjusted capacity for next day based on fatigue signals.
        
        Fatigue signals considered:
        1. Previous day score (quality of execution)
        2. Deferral count (accumulated backlog pressure)
        3. Consecutive poor/good days (trend matters)
        
        Algorithm:
          If score < 0.4 (poor):
            → Reduce capacity by reduction_factor
            → Increase consecutive_poor_days
            → Handle heavy deferral as extra fatigue signal
          
          If score > 0.75 (good) and no deferrals:
            → Gradually restore capacity
            → Increase consecutive_good_days
          
          Else (middle range):
            → Hold capacity stable
            → Wait for clear signal
        
        Args:
            day_score: Previous day's quality score (0.0-1.0)
            deferral_count: Number of tasks deferred today
            
        Returns:
            Adjusted capacity for next day (hours)
        """
        if day_score is None:
            # First day, use original
            return self.current_capacity
        
        # Fatigue Signal 1: Day Quality
        if day_score < self.poor_score_threshold:
            # System showing signs of overwhelm
            self._reduce_capacity(deferral_count)
        
        elif day_score > self.good_score_threshold and deferral_count == 0:
            # System healthy and sustainable
            self._restore_capacity()
        
        else:
            # Middle zone: stable but not improving
            self._hold_capacity()
        
        self.previous_day_score = day_score
        return self.current_capacity

    def _reduce_capacity(self, deferral_count: int) -> None:
        """
        Reduce capacity due to poor performance or high deferral pressure.
        
        Reduction is applied immediately and can cascade:
        - First poor day: 20% reduction
        - Repeated poor days: compound reduction
        - High deferrals: amplify reduction (extra fatigue signal)
        
        Args:
            deferral_count: Number of deferred tasks (fatigue signal)
        """
        self.consecutive_poor_days += 1
        self.consecutive_good_days = 0
        
        # Base reduction
        reduction = self.current_capacity * self.reduction_factor
        
        # Amplify reduction if many tasks deferred (extra exhaustion signal)
        if deferral_count > 3:
            reduction *= 1.5  # 50% more aggressive reduction
        
        self.current_capacity -= reduction
        self.current_capacity = max(self.current_capacity, self.min_capacity)

    def _restore_capacity(self) -> None:
        """
        Gradually restore capacity after system shows improvement.
        
        Recovery is slow and steady:
        - Each good day: recover 5% of gap toward original
        - Multiple consecutive good days: accelerate recovery
        - Stops at original_capacity (never exceed baseline)
        
        This models: "System is handling load well, can take more"
        """
        self.consecutive_good_days += 1
        self.consecutive_poor_days = 0
        
        # Accelerate recovery if multiple consecutive good days
        recovery = self.recovery_factor
        if self.consecutive_good_days > 2:
            recovery *= 1.5  # 50% faster after 3+ good days
        
        gap = self.max_capacity - self.current_capacity
        restoration = gap * recovery
        
        self.current_capacity += restoration
        self.current_capacity = min(self.current_capacity, self.max_capacity)

    def _hold_capacity(self) -> None:
        """
        Keep capacity stable when in transition zone.
        
        Used when score is in middle range (0.4-0.75):
        - Not poor enough to trigger reduction
        - Not good enough to trigger restoration
        - Wait for clearer signal
        
        Still tracks consecutive day counts for trend detection.
        """
        # Reset consecutive counters (middle zone means trend broke)
        if self.consecutive_poor_days > 0:
            self.consecutive_poor_days = 0
        if self.consecutive_good_days > 0:
            self.consecutive_good_days = 0

    def apply_adjustment_to_day(
        self,
        day: Day,
        day_score: Optional[float],
        deferral_count: int = 0
    ) -> None:
        """
        Apply fatigue-based capacity adjustment directly to Day object.
        
        Convenience method for forecast.py integration:
        
        Usage in forecast loop:
          fatigue_engine.apply_adjustment_to_day(simulated_day, previous_score, deferral_count)
          # Now simulated_day.available_hours is adjusted
        
        Args:
            day: Day object to adjust in-place
            day_score: Previous day's score (None on first day)
            deferral_count: Number of tasks deferred today
        """
        adjusted_capacity = self.get_adjusted_capacity(day_score, deferral_count)
        day.available_hours = adjusted_capacity

    def get_status_report(self) -> str:
        """
        Generate human-readable fatigue status report.
        
        Shows:
        - Current capacity vs original
        - Fatigue indicators (consecutive poor/good days)
        - Restoration progress
        
        Useful for debugging and understanding system state.
        
        Returns:
            Formatted status string
        """
        capacity_pct = (self.current_capacity / self.original_capacity) * 100
        gap = self.max_capacity - self.current_capacity
        
        status = (
            f"FATIGUE STATUS:\n"
            f"  Capacity: {self.current_capacity:.1f}h / {self.original_capacity:.1f}h "
            f"({capacity_pct:.0f}%)\n"
        )
        
        if self.consecutive_poor_days > 0:
            status += f"  Consecutive poor days: {self.consecutive_poor_days} "
            status += "(reducing capacity)\n"
        
        if self.consecutive_good_days > 0:
            status += f"  Consecutive good days: {self.consecutive_good_days} "
            status += "(restoring capacity)\n"
        
        if gap > 0.1:
            status += f"  Gap to restore: {gap:.1f}h\n"
        
        return status

    def reset(self) -> None:
        """
        Reset fatigue engine to initial state.
        
        Use when starting new planning cycle or clearing system.
        """
        self.current_capacity = self.original_capacity
        self.previous_day_score = None
        self.consecutive_poor_days = 0
        self.consecutive_good_days = 0
