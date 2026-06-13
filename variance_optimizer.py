"""
Variance Minimization Objective with Learning-Based Parameter Tuning

Adaptive parameter optimization that learns from execution history.

The planning system has many tunable parameters:
  • Fatigue thresholds (poor_score_threshold, good_score_threshold)
  • Reduction/recovery factors (how aggressively to adapt)
  • Deferral sensitivity (overload_threshold)
  • MCL strategies (number of candidates)

Rather than manually tune these, this module:
  1. Tracks day scores and variance over time
  2. Tests parameter variations
  3. Measures impact on variance
  4. Recommends optimal settings
  5. Applies improvements automatically

Goal: Minimize score variance (smooth performance) while maintaining quality
      (high average score). Optimal planning is consistent, not erratic.

Key Insight: A system that scores 0.50 every day is more reliable than
one that scores 0.40, 0.60, 0.40, 0.60. The latter creates execution
anxiety and unpredictability.
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from collections import deque
import math


@dataclass
class ParameterConfig:
    """Configuration container for all tunable parameters."""
    
    # Fatigue parameters
    poor_score_threshold: float = 0.4
    good_score_threshold: float = 0.75
    min_capacity: float = 4.0
    reduction_factor: float = 0.20
    recovery_factor: float = 0.05
    
    # Deferral parameters
    overload_threshold: float = 2.0
    deferral_reduction: float = 0.7
    fairness_window: int = 3
    max_deferrals_per_task: int = 2
    
    # MCL parameters
    num_candidates: int = 3
    
    # Variance optimization parameters
    variance_window_size: int = 5  # Track last N days
    target_variance: float = 0.02  # Ideal variance (lower is better)
    target_avg_score: float = 0.70  # Maintain this quality level minimum


class VarianceOptimizer:
    """
    Learn optimal parameters through variance minimization.
    
    Tracks historical day scores, calculates variance, and recommends
    parameter adjustments that reduce variance while maintaining quality.
    
    Attributes:
        current_config (ParameterConfig): Active parameter settings
        history (deque): Last N day scores for variance calculation
        variance_history (list): Historical variance values
        adjustment_history (list): Parameter adjustments tried
        learning_rate (float): How aggressively to adjust (0.05-0.15)
    """
    
    def __init__(self, initial_config: Optional[ParameterConfig] = None):
        """
        Initialize variance optimizer.
        
        Args:
            initial_config: Starting parameter configuration
                           Default: ParameterConfig() with defaults
        """
        self.current_config = initial_config or ParameterConfig()
        self.history = deque(maxlen=self.current_config.variance_window_size)
        self.variance_history = []
        self.adjustment_history = []
        self.learning_rate = 0.08  # 8% adjustment per iteration
        
        # Tracking for convergence
        self.stable_iterations = 0
        self.last_variance = None
        self.improvement_threshold = 0.0001  # Min variance improvement

    def record_day_score(self, score: float) -> None:
        """
        Record today's score for variance tracking.
        
        Args:
            score: Day quality score (0.0-1.0)
        """
        self.history.append(score)
        
        if len(self.history) >= 3:  # Need at least 3 days for meaningful variance
            variance = self.calculate_variance()
            self.variance_history.append(variance)

    def calculate_variance(self) -> float:
        """
        Calculate variance of recent day scores.
        
        Measures how much scores swing around their mean.
        Lower = more consistent (good)
        Higher = more erratic (bad)
        
        Returns:
            Variance value (0.0+ where 0 = perfect consistency)
        """
        if len(self.history) < 2:
            return float('inf')  # Can't calculate variance with <2 samples
        
        scores = list(self.history)
        mean = sum(scores) / len(scores)
        squared_diffs = [(s - mean) ** 2 for s in scores]
        variance = sum(squared_diffs) / len(scores)
        
        return variance

    def calculate_average_score(self) -> float:
        """
        Calculate average score (quality metric).
        
        Returns:
            Average of recent scores
        """
        if not self.history:
            return 0.0
        return sum(self.history) / len(self.history)

    def should_optimize(self) -> bool:
        """
        Determine if we should attempt parameter optimization.
        
        Wait until enough history to make good decisions.
        
        Returns:
            True if ready to optimize, False otherwise
        """
        return len(self.history) >= self.current_config.variance_window_size

    def analyze_variance_pattern(self) -> Dict:
        """
        Analyze patterns in variance to identify problems.
        
        Returns:
            Dict with analysis results and root causes
        """
        if len(self.history) < 3:
            return {"status": "insufficient_history"}
        
        scores = list(self.history)
        variance = self.calculate_variance()
        avg = self.calculate_average_score()
        
        # Identify patterns
        high_scores = sum(1 for s in scores if s > 0.7)
        low_scores = sum(1 for s in scores if s < 0.4)
        
        # Classify variance type
        if low_scores >= 2 and high_scores >= 2:
            pattern = "alternating_performance"  # Swings between good/bad
            cause = "May need less aggressive fatigue adjustment"
        elif low_scores >= 3:
            pattern = "consistently_poor"
            cause = "Fatigue thresholds too strict or workload unrealistic"
        elif high_scores >= 3:
            pattern = "consistently_good"
            cause = "System may be under-challenged, increase complexity"
        else:
            pattern = "mixed_performance"
            cause = "Unclear - more data needed"
        
        return {
            "pattern": pattern,
            "cause": cause,
            "current_variance": variance,
            "average_score": avg,
            "low_score_days": low_scores,
            "high_score_days": high_scores
        }

    def recommend_adjustments(self) -> Tuple[ParameterConfig, Dict]:
        """
        Recommend parameter adjustments to minimize variance.
        
        Uses variance patterns to suggest parameter changes:
        - High variance with low averages: Fatigue reduction too aggressive
        - High variance with oscillation: Recovery too fast
        - Consistent lows: Unrealistic capacity assumptions
        
        Returns:
            Tuple of (adjusted_config, explanation)
        """
        if not self.should_optimize():
            return self.current_config, {"status": "waiting_for_history"}
        
        analysis = self.analyze_variance_pattern()
        adjusted_config = ParameterConfig(**vars(self.current_config))
        explanation = {
            "analysis": analysis,
            "adjustments": []
        }
        
        # Apply adjustments based on pattern
        pattern = analysis.get("pattern")
        avg_score = analysis.get("average_score", 0)
        
        if pattern == "alternating_performance":
            # Swing between good and bad - fatigue adjustment too aggressive
            explanation["adjustments"].append(
                "Reducing fatigue adjustment aggressiveness"
            )
            adjusted_config.reduction_factor *= (1 - self.learning_rate)
            adjusted_config.recovery_factor *= (1 + self.learning_rate * 0.5)
        
        elif pattern == "consistently_poor":
            # All low scores - need help
            if avg_score < 0.3:
                explanation["adjustments"].append(
                    "Capacity expectations unrealistic - relaxing thresholds"
                )
                adjusted_config.poor_score_threshold = max(0.2, adjusted_config.poor_score_threshold - 0.05)
                adjusted_config.min_capacity = min(adjusted_config.min_capacity + 0.5, 6.0)
        
        # Quality check: maintain average score
        if avg_score < 0.35:
            explanation["adjustments"].append(
                "Average score below 0.35 - enabling less aggressive deferral"
            )
            adjusted_config.overload_threshold *= 1.1  # More lenient on deferral
            adjusted_config.deferral_reduction = min(0.8, adjusted_config.deferral_reduction + 0.1)
        
        # If no specific adjustments, try fine-tuning
        if not explanation["adjustments"]:
            if self.variance_history and len(self.variance_history) >= 2:
                last_variance = self.variance_history[-1]
                prev_variance = self.variance_history[-2]
                
                if last_variance > prev_variance * 1.1:  # Variance increased
                    explanation["adjustments"].append(
                        "Variance increased - adjusting recovery speed"
                    )
                    adjusted_config.recovery_factor *= (1 - self.learning_rate)
        
        self.adjustment_history.append({
            "config": adjusted_config,
            "reason": explanation,
            "timestamp": len(self.variance_history)
        })
        
        return adjusted_config, explanation

    def apply_adjustment(self, new_config: ParameterConfig) -> None:
        """
        Apply parameter adjustment to current config.
        
        Args:
            new_config: New configuration to use
        """
        self.current_config = new_config
        self.stable_iterations = 0  # Reset stability counter

    def get_convergence_status(self) -> Dict:
        """
        Check if system has converged to stable parameters.
        
        Returns:
            Dict with convergence metrics
        """
        if len(self.variance_history) < 2:
            return {"status": "insufficient_data"}
        
        recent = self.variance_history[-3:]  # Last 3 variance measurements
        
        if len(recent) < 3:
            return {
                "status": "learning",
                "samples": len(self.variance_history)
            }
        
        # Check if variance is stable (not improving)
        changes = [abs(recent[i+1] - recent[i]) for i in range(len(recent)-1)]
        avg_change = sum(changes) / len(changes)
        
        if avg_change < self.improvement_threshold:
            self.stable_iterations += 1
            status = "converged" if self.stable_iterations >= 2 else "converging"
        else:
            status = "learning"
        
        return {
            "status": status,
            "current_variance": recent[-1],
            "avg_change": avg_change,
            "stable_iterations": self.stable_iterations
        }

    def get_optimization_report(self) -> str:
        """
        Generate human-readable optimization report.
        
        Shows:
        - Current score distribution
        - Variance trend
        - Active parameters
        - Convergence progress
        
        Returns:
            Formatted report string
        """
        if len(self.history) < 2:
            return "OPTIMIZATION REPORT:\n  Insufficient history (need 2+ days)"
        
        scores = list(self.history)
        variance = self.calculate_variance() if len(self.history) >= 2 else None
        avg = self.calculate_average_score()
        
        report = "OPTIMIZATION REPORT:\n"
        report += f"  Recent scores: {[f'{s:.2f}' for s in scores[-5:]]}\n"
        report += f"  Average: {avg:.3f}\n"
        
        if variance is not None:
            report += f"  Variance: {variance:.4f}\n"
        
        # Convergence status
        conv = self.get_convergence_status()
        report += f"  Status: {conv.get('status', 'unknown')}\n"
        
        # Active parameters (most important ones)
        report += f"  Parameters:\n"
        report += f"    - Poor threshold: {self.current_config.poor_score_threshold:.2f}\n"
        report += f"    - Good threshold: {self.current_config.good_score_threshold:.2f}\n"
        report += f"    - Reduction factor: {self.current_config.reduction_factor:.2%}\n"
        report += f"    - Recovery factor: {self.current_config.recovery_factor:.2%}\n"
        report += f"    - Overload threshold: {self.current_config.overload_threshold:.2f}\n"
        
        return report

    def export_config(self) -> Dict:
        """
        Export optimized config for use in other modules.
        
        Returns:
            Dict of current configuration
        """
        return {
            "fatigue": {
                "poor_score_threshold": self.current_config.poor_score_threshold,
                "good_score_threshold": self.current_config.good_score_threshold,
                "min_capacity": self.current_config.min_capacity,
                "reduction_factor": self.current_config.reduction_factor,
                "recovery_factor": self.current_config.recovery_factor
            },
            "deferral": {
                "overload_threshold": self.current_config.overload_threshold,
                "deferral_reduction": self.current_config.deferral_reduction,
                "fairness_window": self.current_config.fairness_window,
                "max_deferrals_per_task": self.current_config.max_deferrals_per_task
            },
            "mcl": {
                "num_candidates": self.current_config.num_candidates
            }
        }

    def reset(self) -> None:
        """Reset all learning history and revert to defaults."""
        self.history.clear()
        self.variance_history.clear()
        self.adjustment_history.clear()
        self.current_config = ParameterConfig()
        self.stable_iterations = 0
