"""
Stochastic Uncertainty Modeling - Stage 6

Models uncertainty in task execution, schedule variability, and system robustness.
Uses Monte Carlo simulation to evaluate solution robustness under varied conditions.

Key Features:
  - Task duration uncertainty (variability in execution time)
  - Fatigue impact uncertainty (non-linear effects)
  - System capacity uncertainty (fatigue affects differently on different days)
  - Monte Carlo robust evaluation
  - Risk quantification (failure probability)
  - Confidence intervals around plan quality
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from collections import deque
import random
import statistics
from datetime import datetime


@dataclass
class TaskUncertainty:
    """Model uncertainty in a single task's execution."""
    
    task_id: str
    base_duration: float  # Nominal duration in hours
    duration_std_dev: float  # Standard deviation (uncertainty magnitude)
    base_load: float  # Nominal load on quality scale (0-1)
    interruption_probability: float  # P(task interrupted during execution)
    failure_probability: float  # P(task fails and needs restart)
    
    # Derived properties
    duration_mean: float = field(init=False)
    
    def __post_init__(self):
        """Calculate duration mean."""
        self.duration_mean = self.base_duration
    
    def sample_duration(self) -> float:
        """
        Sample task duration from normal distribution.
        Realistic model: durations vary but cluster around mean.
        """
        # Duration = mean ± std_dev (approximately 68% within 1-sigma)
        sampled = random.gauss(self.duration_mean, self.duration_std_dev)
        # Clamp to reasonable bounds (min 10% of base, max 300% of base)
        return max(self.base_duration * 0.1, 
                   min(sampled, self.base_duration * 3.0))
    
    def sample_load(self, fatigue_factor: float = 1.0) -> float:
        """
        Sample task load, affected by fatigue.
        Higher fatigue → higher load (harder to complete)
        """
        # Base load + uncertainty
        load_uncertainty = random.gauss(0, 0.05)
        base = self.base_load + fatigue_factor * 0.1
        return max(0.0, min(base + load_uncertainty, 1.0))
    
    def check_interruption(self) -> bool:
        """Probabilistically determine if task interrupted."""
        return random.random() < self.interruption_probability
    
    def check_failure(self) -> bool:
        """Probabilistically determine if task fails (needs restart)."""
        return random.random() < self.failure_probability
    
    def get_distribution_info(self) -> Dict:
        """Return distribution parameters for analysis."""
        return {
            "task_id": self.task_id,
            "duration_mean": self.duration_mean,
            "duration_std_dev": self.duration_std_dev,
            "duration_range": (self.base_duration * 0.1, self.base_duration * 3.0),
            "interruption_prob": self.interruption_probability,
            "failure_prob": self.failure_probability,
            "base_load": self.base_load,
        }


@dataclass
class UncertaintyBounds:
    """Confidence intervals for plan quality."""
    
    mean_quality: float  # Expected quality
    median_quality: float  # Median of outcomes
    std_dev: float  # Standard deviation
    percentile_5: float  # 5th percentile (worst case)
    percentile_95: float  # 95th percentile (best case)
    min_quality: float  # Worst observed outcome
    max_quality: float  # Best observed outcome
    failure_rate: float  # P(plan fails) = scores < 0.3
    
    def get_confidence_interval(self) -> Tuple[float, float]:
        """Return 90% confidence interval."""
        return (self.percentile_5, self.percentile_95)
    
    def risk_level(self) -> str:
        """Assess risk based on failure rate and variability."""
        if self.failure_rate > 0.30:
            return "high_risk"
        elif self.failure_rate > 0.10:
            return "medium_risk"
        elif self.std_dev > 0.15:
            return "uncertain"
        else:
            return "robust"


class UncertaintyModel:
    """
    Main uncertainty modeling engine.
    
    Simulates task execution with uncertainty to evaluate:
      - Plan robustness (performance across scenarios)
      - Failure probability (chance of dropping below threshold)
      - Confidence intervals around expected quality
      - Sensitivity to uncertainty sources
    """
    
    def __init__(self, num_simulations: int = 1000):
        """
        Initialize uncertainty model.
        
        Args:
            num_simulations: Number of Monte Carlo trials (higher = more accurate)
        """
        self.num_simulations = num_simulations
        self.task_uncertainties: Dict[str, TaskUncertainty] = {}
        self.simulation_results: List[float] = []
        self.failure_count = 0
        self.simulation_history: deque = deque(maxlen=10)
    
    def register_task(self, task: TaskUncertainty) -> None:
        """Register a task with its uncertainty model."""
        self.task_uncertainties[task.task_id] = task
    
    def register_tasks(self, tasks: List[TaskUncertainty]) -> None:
        """Register multiple tasks at once."""
        for task in tasks:
            self.register_task(task)
    
    def clear_tasks(self) -> None:
        """Clear all registered tasks."""
        self.task_uncertainties.clear()
    
    def simulate_task_execution(
        self, 
        task: TaskUncertainty, 
        fatigue_factor: float = 1.0,
        capacity_available: float = 24.0
    ) -> Dict:
        """
        Simulate single task execution with uncertainty.
        
        Args:
            task: Task to simulate
            fatigue_factor: How much fatigue affects execution
            capacity_available: Hours available in day
            
        Returns:
            Dict with execution details (duration_used, success, quality)
        """
        # Sample duration with uncertainty
        duration_used = task.sample_duration()
        
        # Check for interruptions
        interrupted = task.check_interruption()
        if interrupted:
            duration_used *= 1.5  # Interruption adds 50% overhead
        
        # Check for failures
        failed = task.check_failure()
        if failed:
            duration_used *= 2.0  # Failure requires re-execution
        
        # Check if we have enough capacity
        fits_in_day = duration_used <= capacity_available
        
        # Sample load with fatigue influence
        load = task.sample_load(fatigue_factor)
        
        return {
            "task_id": task.task_id,
            "duration_planned": task.base_duration,
            "duration_actual": duration_used,
            "fits": fits_in_day,
            "interrupted": interrupted,
            "failed": failed,
            "load": load,
            "capacity_available": capacity_available,
        }
    
    def simulate_day_plan(
        self,
        plan_quality: float,
        num_tasks: int = 5,
        avg_task_duration: float = 2.0,
        fatigue_factor: float = 1.0,
        daily_capacity: float = 8.0
    ) -> float:
        """
        Simulate execution of day's plan with uncertainty.
        
        Args:
            plan_quality: Base quality of plan (before uncertainty)
            num_tasks: Number of tasks planned
            avg_task_duration: Average task duration
            fatigue_factor: Fatigue impact multiplier
            daily_capacity: Available work capacity (hours)
            
        Returns:
            Quality score after uncertainty simulation
        """
        # Track what actually happens
        total_duration = 0.0
        completion_issues = 0
        load_impacts = []
        
        for i in range(num_tasks):
            # Sample task properties
            duration = random.gauss(avg_task_duration, avg_task_duration * 0.3)
            duration = max(0.5, min(duration, avg_task_duration * 2.0))
            
            # Check for issues
            interrupted = random.random() < 0.05  # 5% chance
            failed = random.random() < 0.02  # 2% chance
            
            if interrupted:
                duration *= 1.5
            if failed:
                duration *= 2.0
            
            # Track capacity usage
            total_duration += duration
            if total_duration > daily_capacity:
                completion_issues += 1
            
            # Track load impact (with fatigue)
            load = random.gauss(0.5, 0.1) * (1 + fatigue_factor * 0.2)
            load_impacts.append(min(load, 1.0))
        
        # Calculate quality degradation
        capacity_pressure = min(total_duration / daily_capacity, 1.5)
        overload_penalty = max(0, (capacity_pressure - 1.0) * 0.3)
        
        interruption_penalty = len([1 for _ in range(num_tasks) 
                                    if random.random() < 0.05]) * 0.02
        
        # Final quality = base - uncertainty impacts
        degraded_quality = plan_quality - overload_penalty - interruption_penalty
        return max(0.0, min(degraded_quality, 1.0))
    
    def evaluate_plan_robustness(
        self,
        base_plan_quality: float,
        num_tasks: int = 5,
        avg_task_duration: float = 2.0,
        fatigue_factor: float = 1.0,
        daily_capacity: float = 8.0
    ) -> UncertaintyBounds:
        """
        Run Monte Carlo simulation to evaluate plan robustness.
        
        Args:
            base_plan_quality: Expected quality without uncertainty
            num_tasks: Number of tasks in plan
            avg_task_duration: Average task duration
            fatigue_factor: Fatigue impact
            daily_capacity: Available capacity
            
        Returns:
            UncertaintyBounds with confidence intervals
        """
        self.simulation_results = []
        self.failure_count = 0
        
        # Run Monte Carlo trials
        for _ in range(self.num_simulations):
            quality = self.simulate_day_plan(
                plan_quality=base_plan_quality,
                num_tasks=num_tasks,
                avg_task_duration=avg_task_duration,
                fatigue_factor=fatigue_factor,
                daily_capacity=daily_capacity
            )
            self.simulation_results.append(quality)
            
            # Count failures (low quality)
            if quality < 0.30:
                self.failure_count += 1
        
        # Calculate statistics
        results = sorted(self.simulation_results)
        mean_quality = statistics.mean(results)
        median_quality = statistics.median(results)
        std_dev = statistics.stdev(results) if len(results) > 1 else 0.0
        
        n = len(results)
        percentile_5_idx = max(0, int(n * 0.05))
        percentile_95_idx = min(n - 1, int(n * 0.95))
        
        bounds = UncertaintyBounds(
            mean_quality=mean_quality,
            median_quality=median_quality,
            std_dev=std_dev,
            percentile_5=results[percentile_5_idx],
            percentile_95=results[percentile_95_idx],
            min_quality=results[0],
            max_quality=results[-1],
            failure_rate=self.failure_count / self.num_simulations
        )
        
        # Store in history
        self.simulation_history.append({
            "timestamp": datetime.now(),
            "base_quality": base_plan_quality,
            "bounds": bounds,
            "num_simulations": self.num_simulations
        })
        
        return bounds
    
    def compare_plans(
        self,
        plans: List[Tuple[str, float]],  # List of (name, base_quality)
        **simulation_params
    ) -> Dict:
        """
        Compare multiple plans to find most robust.
        
        Args:
            plans: List of (plan_name, base_quality) tuples
            **simulation_params: Parameters for evaluate_plan_robustness
            
        Returns:
            Dict with ranked plans by robustness
        """
        results = {}
        
        for plan_name, plan_quality in plans:
            bounds = self.evaluate_plan_robustness(
                base_plan_quality=plan_quality,
                **simulation_params
            )
            
            # Robustness score: high mean + low variance + low failure rate
            robustness_score = (
                bounds.mean_quality * 0.4 +
                (1.0 - bounds.std_dev) * 0.3 +  # Lower variance is better
                (1.0 - bounds.failure_rate) * 0.3  # Lower failure rate is better
            )
            
            results[plan_name] = {
                "base_quality": plan_quality,
                "bounds": bounds,
                "robustness_score": robustness_score,
                "risk_level": bounds.risk_level(),
            }
        
        # Sort by robustness score
        ranked = sorted(
            results.items(),
            key=lambda x: x[1]["robustness_score"],
            reverse=True
        )
        
        return {
            "ranked_plans": ranked,
            "best_plan": ranked[0][0] if ranked else None,
            "best_robustness": ranked[0][1]["robustness_score"] if ranked else 0.0
        }
    
    def sensitivity_analysis(
        self,
        base_plan_quality: float,
        parameter_ranges: Dict[str, Tuple[float, float]] = None,
        **base_params
    ) -> Dict:
        """
        Analyze how uncertainty affects plan quality.
        Tests sensitivity to different sources of uncertainty.
        
        Args:
            base_plan_quality: Base quality to test
            parameter_ranges: Dict of {param: (min, max)} to vary
            **base_params: Base simulation parameters
            
        Returns:
            Dict with sensitivity results
        """
        if parameter_ranges is None:
            parameter_ranges = {
                "avg_task_duration": (1.0, 4.0),
                "fatigue_factor": (0.5, 2.0),
                "daily_capacity": (6.0, 10.0),
            }
        
        sensitivity = {}
        
        for param_name, (min_val, max_val) in parameter_ranges.items():
            test_params = base_params.copy()
            
            # Test at min, center, max
            results_at_values = {}
            for test_val in [min_val, (min_val + max_val) / 2, max_val]:
                test_params[param_name] = test_val
                bounds = self.evaluate_plan_robustness(
                    base_plan_quality=base_plan_quality,
                    **test_params
                )
                results_at_values[test_val] = bounds.mean_quality
            
            # Calculate sensitivity (change in quality per unit change in parameter)
            min_quality = results_at_values[min_val]
            max_quality = results_at_values[max_val]
            param_range = max_val - min_val
            sensitivity[param_name] = {
                "quality_at_min": min_quality,
                "quality_at_max": max_quality,
                "quality_delta": max_quality - min_quality,
                "sensitivity_per_unit": (max_quality - min_quality) / param_range if param_range > 0 else 0.0,
                "impact_magnitude": "high" if abs(max_quality - min_quality) > 0.15 else "medium" if abs(max_quality - min_quality) > 0.05 else "low"
            }
        
        return {
            "sensitivity_by_parameter": sensitivity,
            "most_sensitive": max(sensitivity.items(), 
                                  key=lambda x: abs(x[1]["quality_delta"]))[0]
            if sensitivity else None
        }
    
    def get_simulation_summary(self) -> Dict:
        """Get summary of recent simulations."""
        if not self.simulation_results:
            return {"status": "no_simulations_run"}
        
        return {
            "last_simulation": {
                "mean": statistics.mean(self.simulation_results),
                "median": statistics.median(self.simulation_results),
                "std_dev": statistics.stdev(self.simulation_results) if len(self.simulation_results) > 1 else 0.0,
                "min": min(self.simulation_results),
                "max": max(self.simulation_results),
                "num_trials": len(self.simulation_results),
            },
            "failure_rate": self.failure_count / self.num_simulations if self.simulation_results else 0.0,
            "simulations_run": len(self.simulation_history),
            "num_registered_tasks": len(self.task_uncertainties),
        }
    
    def get_uncertainty_report(self) -> str:
        """Generate human-readable uncertainty analysis report."""
        summary = self.get_simulation_summary()
        
        if summary.get("status") == "no_simulations_run":
            return "No simulations run yet."
        
        last = summary.get("last_simulation", {})
        
        report = f"""
UNCERTAINTY ANALYSIS REPORT
═══════════════════════════════════════════════════

Last Simulation Results:
  Mean Quality:     {last.get('mean', 0.0):.3f}
  Median Quality:   {last.get('median', 0.0):.3f}
  Std Deviation:    {last.get('std_dev', 0.0):.3f}
  Range:            {last.get('min', 0.0):.3f} - {last.get('max', 0.0):.3f}
  
Failure Analysis:
  Failure Rate:     {summary.get('failure_rate', 0.0):.1%}
  (Plans scoring < 0.30)
  
Simulation Summary:
  Trials Run:       {last.get('num_trials', 0)}
  Scenarios Tested: {summary.get('simulations_run', 0)}
  Tasks Modeled:    {summary.get('num_registered_tasks', 0)}
"""
        return report
    
    def reset_simulations(self) -> None:
        """Clear simulation history."""
        self.simulation_results = []
        self.failure_count = 0
        self.simulation_history.clear()


class RobustnessAdvisor:
    """
    Provides recommendations for improving plan robustness under uncertainty.
    """
    
    def __init__(self, uncertainty_model: UncertaintyModel):
        """Initialize advisor with uncertainty model."""
        self.model = uncertainty_model
    
    def get_recommendations(self, bounds: UncertaintyBounds) -> List[str]:
        """
        Generate actionable recommendations based on uncertainty bounds.
        
        Args:
            bounds: UncertaintyBounds from simulation
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # High failure rate
        if bounds.failure_rate > 0.20:
            recommendations.append(
                f"❌ High failure rate ({bounds.failure_rate:.1%}): Plan may fail frequently. "
                "Consider reducing scope or increasing buffers."
            )
        
        # High variability
        if bounds.std_dev > 0.20:
            recommendations.append(
                f"⚠️  High variability (σ={bounds.std_dev:.3f}): Plan quality unpredictable. "
                "Consider building robustness through buffers or contingency planning."
            )
        
        # Wide confidence interval
        interval = bounds.percentile_95 - bounds.percentile_5
        if interval > 0.30:
            recommendations.append(
                f"📊 Wide confidence interval ({interval:.2f}): "
                "Plan outcomes range from {bounds.percentile_5:.2f} to {bounds.percentile_95:.2f}. "
                "Consider two-plan approach (aggressive + conservative)."
            )
        
        # Low median quality
        if bounds.median_quality < 0.50:
            recommendations.append(
                f"📉 Low median quality ({bounds.median_quality:.3f}): "
                "Plan likely underperforms. Reassess scope or capacity."
            )
        
        # Bimodal distribution (some very good, some very bad)
        if bounds.failure_rate > 0.05 and bounds.max_quality > 0.80:
            recommendations.append(
                "🎲 Bimodal outcomes: Plan sometimes succeeds, sometimes fails. "
                "Identify and mitigate key risk factors."
            )
        
        if not recommendations:
            recommendations.append(
                "✅ Plan appears robust under uncertainty. Failure rate low, "
                "variability acceptable, confidence intervals tight."
            )
        
        return recommendations
    
    def get_mitigation_strategies(self, bounds: UncertaintyBounds) -> Dict[str, str]:
        """
        Get specific strategies to mitigate identified risks.
        
        Args:
            bounds: UncertaintyBounds from simulation
            
        Returns:
            Dict mapping risk type to mitigation strategy
        """
        strategies = {}
        
        if bounds.failure_rate > 0.15:
            strategies["high_failure"] = (
                "MITIGATION: Reduce daily load by 20-30%, add buffer tasks, "
                "or increase capacity allocation."
            )
        
        if bounds.std_dev > 0.15:
            strategies["high_variability"] = (
                "MITIGATION: Standardize task execution, reduce complexity, "
                "or use staged approach (try → adjust → complete)."
            )
        
        if bounds.percentile_5 < 0.30:
            strategies["worst_case_failure"] = (
                "MITIGATION: Implement contingency plan for worst-case scenario, "
                "pre-identify what can be deferred if needed."
            )
        
        if not strategies:
            strategies["success"] = "Plan robust: Monitor execution but no major mitigations needed."
        
        return strategies
