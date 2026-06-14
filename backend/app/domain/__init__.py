"""Domain models for AI scheduling and behavior analysis.

Contains core data structures and evaluation logic for daily planning:

Classes:
    Day: Represents a single day with available hours and tasks
    DayEvaluator: Evaluates day schedules against multiple metrics
    
Functions:
    compute_overload_index: Calculate task load vs capacity
    compute_strategic_weight: Calculate task importance score
    apply_strategic_compression: Apply soft-freeze penalties during overload

Import directly from submodules:
    from backend.app.domain.day_model import Day
    from backend.app.domain.evaluation import DayEvaluator
    from backend.app.domain.strategic_compression import compute_overload_index
"""

__all__ = []
