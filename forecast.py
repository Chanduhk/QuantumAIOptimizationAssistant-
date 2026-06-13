from day_model import Day
from models import Task
import copy
from candidate_selector import MultiCandidateLookahead
from deferral_manager import DeferralManager
from fatigue_model import FatigueModelingEngine
from variance_optimizer import VarianceOptimizer, ParameterConfig
from stochastic_uncertainty import UncertaintyModel, RobustnessAdvisor
from config_system import ConfigManager, SystemConfig, ConfigProfile
from ga_optimizer import GeneticOptimizer
from evaluation import DayEvaluator
from lookahead import TwoDaySimulator
from strategic_compression import (
    compute_overload_index,
    apply_strategic_compression,
    update_penalty_recovery,
    compute_penalty_entropy,
    filter_active_tasks,
    ensure_feasible_task_set
)  # ensure_feasible_task_set is critical: prevents empty candidate deadlock


def compute_effective_terminal_risk_weight(base_risk_weight, remaining_days):
    """Compute terminal-damped risk weight near the end of the forecast horizon."""
    if remaining_days <= 2:
        damping_factor = 1.0 + (1.0 / (remaining_days + 1.0))
        return min(base_risk_weight * damping_factor, 0.25)
    return base_risk_weight


class MultiDayForecaster:
    def __init__(self, day, scheduler, days=3, config: SystemConfig = None):
        self.original_day = day
        self.scheduler = scheduler
        self.days = days
        
        # Initialize configuration system
        self.config_manager = ConfigManager()
        if config is None:
            self.config = self.config_manager.get_default_config()
        else:
            self.config = config
        
        # Override days from parameter if provided
        if days != 3:
            self.config.forecast.num_days = days
        
        # Initialize deferral manager using config
        self.deferral_manager = DeferralManager(
            overload_threshold=self.config.deferral.overload_threshold,
            deferral_reduction=self.config.deferral.deferral_reduction,
            fairness_window=self.config.deferral.fairness_window,
            max_deferrals_per_task=self.config.deferral.max_deferrals_per_task
        )
        
        # Initialize fatigue modeling using config
        self.fatigue_engine = FatigueModelingEngine(
            original_capacity=day.available_hours,
            poor_score_threshold=self.config.fatigue.poor_score_threshold,
            good_score_threshold=self.config.fatigue.good_score_threshold,
            min_capacity=self.config.fatigue.min_capacity
        )
        
        # Initialize variance optimizer for learning-based parameter tuning
        self.variance_optimizer = VarianceOptimizer()
        self.optimization_applied = False
        
        # Initialize uncertainty model using config
        self.uncertainty_model = UncertaintyModel(
            num_simulations=self.config.uncertainty.num_simulations
        )
        self.robustness_advisor = RobustnessAdvisor(self.uncertainty_model)
        self.day_scores = []
        self.entropy_values = []
        self.csi_values = []
        self.penalty_values = []

    def simulate(self):
        total_score = 0
        actual_days = 0
        initial_avg_penalty = None
        risk_weight = self.config.forecast.risk_weight
        consecutive_max_penalty_days = 0
        previous_day_score = None  # Track score for fatigue adjustment
        shock_pre_score = None
        shock_pending = False
        self.day_scores = []
        self.entropy_values = []
        self.csi_values = []
        self.penalty_values = []

        # Persistent backlog copy
        backlog = copy.deepcopy(self.original_day.tasks)

        # ===== STRATEGIC COMPRESSION LAYER (PRE-SIMULATION ACTIVATION) =====
        # Apply compression BEFORE the 5-day simulation loop starts
        # CRITICAL: Compression uses HARD-ISOLATED threshold (1.2)
        # Learning module CANNOT affect compression threshold
        
        capacity_per_day = self.original_day.available_hours
        planning_horizon = self.config.forecast.num_days
        
        # DEBUG: Calculate and display overload index
        overload_index = compute_overload_index(backlog, capacity_per_day, planning_horizon)
        print("\n[DEBUG] Overload Index Calculation:")
        print("   Overload Index: {:.2f}".format(overload_index))
        print("   Total Task Hours: {:.1f}h".format(sum(t.duration for t in backlog)))
        print("   Available Capacity: {:.1f}h".format(capacity_per_day * planning_horizon))
        print("   COMPRESSION THRESHOLD (Hard-Isolated): 1.2")
        print("   LEARNING THRESHOLD (Separate): 2.0")
        
        # Apply compression with EXPLICIT compression_threshold parameter
        # This threshold is INDEPENDENT and cannot be modified by learning module
        # Uses ADAPTIVE capacity-based protection (85% of daily capacity)
        compression_active = apply_strategic_compression(
            tasks=backlog,
            capacity_per_day=capacity_per_day,
            planning_horizon=planning_horizon,
            compression_threshold=1.2   # HARD-ISOLATED: Compression uses 1.2, not learning threshold
        )
        
        # Print penalized tasks if compression activated
        if compression_active:
            print("[COMPRESSION] Activation confirmed - Soft-Frozen Tasks:")
            penalized_tasks = [t for t in backlog if t.freeze_penalty_factor < 1.0]
            if penalized_tasks:
                for task in penalized_tasks:
                    print("   * {} (penalty {:.2f})".format(task.name, task.freeze_penalty_factor))
            else:
                print("   WARNING: No tasks penalized (unexpected compression state)")
        else:
            print("[COMPRESSION] No compression needed - overload within threshold")
        
        print("\n" + "="*70 + "\n")
        # ===== END COMPRESSION SETUP =====

        for d in range(self.config.forecast.num_days):
            print("\n[DAY]", d+1)
            remaining_days = self.config.forecast.num_days - (d + 1)

            if not backlog:
                print("No tasks remaining.")
                break

            # --- Shock injection on Day 3 ---
            if d == 2:
                from datetime import datetime, timedelta
                shock_task = Task(
                    "Critical Production Bug",
                    3,
                    10,
                    datetime.now() + timedelta(hours=8)
                )
                print("[WARNING] Shock Event Injected:", shock_task)
                backlog.append(shock_task)
                shock_pre_score = previous_day_score
                shock_pending = True

            # --- Fatigue-Based Capacity Adjustment ---
            # Reduce capacity if previous day was poor (< 40% quality)
            # Restore capacity gradually if system is handling load well (> 75%)
            # Heavy deferrals also signal fatigue and trigger reduction
            deferred_count_today = len([t for t in backlog if t.deferred])
            simulated_day = Day(self.original_day.available_hours, self.original_day.sleep_hours)
            self.fatigue_engine.apply_adjustment_to_day(simulated_day, previous_day_score, deferred_count_today)
            if previous_day_score is not None:
                print(f"[FATIGUE] Capacity adjusted to {simulated_day.available_hours:.1f}h (was {self.original_day.available_hours:.1f}h)")
                print(self.fatigue_engine.get_status_report())
            
            # CRITICAL: simulated_day.tasks stores ALL tasks for calculation purposes
            # But scheduling logic uses active_tasks only
            simulated_day.tasks = backlog

            # --- Strategic Deferral: Manage overload by deferring low-value tasks ---
            # When backlog exceeds 200% of daily capacity, defer lowest-priority work
            # This reduces artificial urgency explosion while preserving long-term fairness
            backlog, deferred_count = self.deferral_manager.apply_deferral_strategy(
                simulated_day, backlog, deferral_count_target=self.config.deferral.deferral_count_target
            )
            
            if deferred_count > 0:
                print(f"[DEFERRAL] Deferred {deferred_count} low-value task(s)")
                print(self.deferral_manager.get_deferral_status_report(backlog))

            # --- Adaptive soft-freeze recovery (daily, overload-aware) ---
            if compression_active:
                global_overload_index = compute_overload_index(
                    backlog,
                    simulated_day.available_hours,
                    self.config.forecast.num_days
                )
                update_penalty_recovery(
                    backlog,
                    overload_index=global_overload_index,
                    daily_capacity=simulated_day.available_hours,
                    remaining_days=remaining_days
                )
            
            # ===== CRITICAL: CREATE ACTIVE TASKS LIST =====
            # Feasibility guard runs AFTER penalty adjustments.
            active_tasks, _ = ensure_feasible_task_set(
                tasks=backlog,
                capacity_per_day=simulated_day.available_hours
            )
            
            # SAFETY ASSERTION: Verify active tasks fit in capacity
            active_hours = sum(t.duration for t in active_tasks)
            assert active_hours <= (capacity_per_day * 10), \
                f"ERROR: Active hours ({active_hours:.1f}h) exceeds realistic capacity!"
            
            # If no active tasks remain after guard, skip to avoid invalid scheduling state.
            if not active_tasks:
                print("[WARNING] No active tasks available after feasibility guard - skipping day")
                break

            # --- Select tasks using multi-candidate lookahead ---
            # Generates diverse candidate subsets and selects via lookahead simulation
            # IMPORTANT: Use ONLY active_tasks, never full backlog
            candidate_selector = MultiCandidateLookahead(
                self.scheduler, 
                num_candidates=self.config.mcl.num_candidates
            )
            selected_today, _ = candidate_selector.select_best_candidate(
                simulated_day, 
                active_tasks  # Use ONLY active tasks, never backlog directly
            )
            
            simulated_day.tasks = selected_today

            # --- Evaluate today's schedule ---
            if len(selected_today) >= 2:
                ga = GeneticOptimizer(
                    simulated_day,
                    self.scheduler,
                    population_size=self.config.ga.population_size,
                    generations=self.config.ga.generations
                )
                best_schedule, best_score = ga.evolve()
            else:
                best_schedule = self.scheduler.generate_from_order(selected_today)
                evaluator = DayEvaluator(simulated_day, best_schedule)
                best_score = evaluator.total_score()

            print("Day Score (before penalty):", round(best_score, 3))
            day_raw_score = best_score
            
            # --- Stochastic Uncertainty Analysis ---
            # Evaluate robustness of this plan to execution uncertainty
            num_tasks = len(selected_today)
            avg_task_duration = sum(t.duration for t in selected_today) / num_tasks if num_tasks > 0 else 2.0
            fatigue_factor = max(1.0, 2.0 - best_score)  # Fatigue increases with poor performance
            daily_capacity = simulated_day.available_hours
            
            uncertainty_bounds = self.uncertainty_model.evaluate_plan_robustness(
                base_plan_quality=best_score,
                num_tasks=num_tasks,
                avg_task_duration=avg_task_duration,
                fatigue_factor=fatigue_factor,
                daily_capacity=daily_capacity
            )
            
            # Apply robustness adjustment: plans with high failure rates get penalized
            robustness_factor = 1.0 - (uncertainty_bounds.failure_rate * 0.2)  # Up to 20% penalty
            robustness_adjusted_score = best_score * robustness_factor
            
            print(f"[UNCERTAINTY] Robustness Assessment:")
            print(f"  Base Quality:     {best_score:.3f}")
            print(f"  Failure Rate:     {uncertainty_bounds.failure_rate:.1%}")
            print(f"  Mean (sim):       {uncertainty_bounds.mean_quality:.3f}")
            print(f"  Confidence (90%): [{uncertainty_bounds.percentile_5:.3f}, {uncertainty_bounds.percentile_95:.3f}]")
            print(f"  Risk Level:       {uncertainty_bounds.risk_level()}")
            print("  Robustness Adj:   {:.3f}x -> {:.3f}".format(robustness_factor, robustness_adjusted_score))
            
            previous_day_score = best_score  # Track for next day's fatigue adjustment
            
            # --- Variance Minimization & Learning-Based Parameter Tuning ---
            # Record score in optimizer to track variance
            self.variance_optimizer.record_day_score(best_score)
            
            # Check if we should optimize parameters (every 5 days or when variance is high)
            if self.variance_optimizer.should_optimize() and not self.optimization_applied:
                recommended_config, explanation = self.variance_optimizer.recommend_adjustments()
                
                # Apply recommended configuration
                self.variance_optimizer.apply_adjustment(recommended_config)
                
                # Update fatigue engine with optimized parameters
                self.fatigue_engine.poor_score_threshold = recommended_config.poor_score_threshold
                self.fatigue_engine.good_score_threshold = recommended_config.good_score_threshold
                self.fatigue_engine.reduction_factor = recommended_config.reduction_factor
                self.fatigue_engine.recovery_factor = recommended_config.recovery_factor
                self.fatigue_engine.min_capacity = recommended_config.min_capacity
                
                # Update deferral manager with optimized parameters
                self.deferral_manager.overload_threshold = recommended_config.overload_threshold
                self.deferral_manager.deferral_reduction = recommended_config.deferral_reduction
                
                self.optimization_applied = True
                print("\n[LEARNING] Parameter optimization applied:")
                print(self.variance_optimizer.get_optimization_report())

            # --- Two-day simulation lookahead (informational) ---
            simulator = TwoDaySimulator(self.scheduler)
            lookahead_score = simulator.simulate(simulated_day, selected_today)
            print("Two-Day Lookahead Score:", round(lookahead_score, 3))

            # --- Adaptive Future Risk Penalty ---
            if backlog:
                base_risk_weight = risk_weight
                effective_risk_weight = compute_effective_terminal_risk_weight(
                    base_risk_weight,
                    remaining_days
                )
                if remaining_days <= 2:
                    print("[TERMINAL DAMPING ACTIVATED]")
                    print(f"Remaining Days: {remaining_days}")
                    print(f"Risk Weight Capped To: {effective_risk_weight:.3f}")

                total_urgency = sum(t.urgency_score() for t in backlog)
                normalized_risk = total_urgency / (len(backlog) * 15)

                raw_penalty = effective_risk_weight * (normalized_risk ** 2)

                # --- Adaptive penalty cap ---
                base_cap = 0.25
                max_penalty = base_cap * (effective_risk_weight / 0.2)

                risk_penalty = min(raw_penalty, max_penalty)

                print("Future Risk Penalty:", round(risk_penalty, 3))
                print("Current Risk Weight:", round(effective_risk_weight, 3))
                print("Current Penalty Cap:", round(max_penalty, 3))

                # --- Adaptive gain logic ---
                if risk_penalty >= max_penalty:
                    consecutive_max_penalty_days += 1
                else:
                    consecutive_max_penalty_days = 0

                if consecutive_max_penalty_days >= 2:
                    risk_weight *= self.config.forecast.risk_weight_decay
                    print("[CONFIG] Risk weight reduced to:", round(risk_weight, 3))
                    consecutive_max_penalty_days = 0

                # Gradual recovery if stable
                if risk_penalty < max_penalty * 0.5:
                    risk_weight = min(risk_weight * 1.05, 0.2)

                # Apply robustness-adjusted score instead of raw score
                best_score = robustness_adjusted_score - risk_penalty

            if shock_pending and shock_pre_score is not None:
                if shock_pre_score > 0:
                    shock_resilience = day_raw_score / shock_pre_score
                else:
                    shock_resilience = 0.0
                print("[SHOCK RESILIENCE]")
                print(f"Pre-Shock Score: {shock_pre_score:.3f}")
                print(f"Post-Shock Score: {day_raw_score:.3f}")
                print(f"Resilience Ratio: {shock_resilience:.3f}")
                shock_pending = False
                shock_pre_score = None

            active_penalized_tasks = [
                t for t in active_tasks
                if getattr(t, "freeze_penalty_factor", 0.0) > 0
            ]
            penalty_entropy = compute_penalty_entropy(active_penalized_tasks)
            print("[PENALTY ENTROPY]")
            print(f"Active Penalized Tasks: {len(active_penalized_tasks)}")
            print(f"Entropy Score: {penalty_entropy:.3f}")

            csi_penalties = []
            for task in active_tasks:
                # Exclude metadata-only records from CSI monitoring.
                if getattr(task, "is_metadata", False) or getattr(task, "metadata_only", False):
                    continue
                penalty_value = None
                if hasattr(task, "penalty"):
                    penalty_value = task.penalty
                elif hasattr(task, "freeze_penalty_factor"):
                    raw_penalty = task.freeze_penalty_factor
                    if raw_penalty is not None and raw_penalty < 1.0:
                        penalty_value = raw_penalty
                if penalty_value is None:
                    continue
                try:
                    penalty_value = float(penalty_value)
                except (TypeError, ValueError):
                    continue
                if penalty_value > 0:
                    csi_penalties.append(penalty_value)

            if csi_penalties:
                current_avg_penalty = sum(csi_penalties) / len(csi_penalties)
            else:
                current_avg_penalty = 0.0
            if initial_avg_penalty is None:
                initial_avg_penalty = current_avg_penalty
            days_elapsed = max(1, d + 1)
            csi = max(0.0, (initial_avg_penalty - current_avg_penalty) / days_elapsed)
            print("[CONVERGENCE SPEED]")
            print(f"Initial Avg Penalty: {initial_avg_penalty:.3f}")
            print(f"Current Avg Penalty: {current_avg_penalty:.3f}")
            print(f"CSI: {csi:.3f}")
            self.day_scores.append(day_raw_score)
            self.entropy_values.append(penalty_entropy)
            self.csi_values.append(csi)
            self.penalty_values.append(current_avg_penalty)

            # --- Accumulate ---
            total_score += best_score
            actual_days += 1

            # Reset deferred counters for tasks that were scheduled today.
            for task in selected_today:
                task.reset_deferred_days()

            # --- Remove completed tasks ---
            backlog = [
                t for t in backlog
                if t.name not in [x.name for x in selected_today]
            ]

            # --- Advance time & increase delay ---
            for task in backlog:
                # Increment anti-starvation counter for tasks deferred to future days.
                task.increment_deferred_day()
                task.delay_count += 1
                task.advance_time(24)

        # --- Final average ---
        if actual_days == 0:
            print("\n[RESULT] MULTI-DAY AVERAGE SCORE: 0")
            return 0

        average_score = total_score / actual_days
        print("\n[RESULT] MULTI-DAY AVERAGE SCORE:", round(average_score, 3))

        return average_score
