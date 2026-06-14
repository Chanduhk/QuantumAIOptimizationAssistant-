"""Strategic Compression Layer

Soft-freeze compression that de-prioritizes lower-value tasks via penalty factors
instead of hard exclusion.

Functions:
    - compute_overload_index: Calculate task load vs capacity ratio
    - compute_strategic_weight: Calculate task importance/urgency score
    - compute_effective_weight: Strategic weight adjusted by soft-freeze penalty
    - apply_strategic_compression: Apply soft freeze penalties during overload
    - update_penalty_recovery: Recover penalties daily toward 1.0
    - ensure_feasible_task_set: Guarantee minimum active candidate feasibility
"""
import math

MIN_ACTIVE_TASKS = 2
MIN_ACTIVE_DURATION = 1.0  # hours
RECOVERY_BASE_MIN = 0.10
RECOVERY_BASE_MAX = 0.30


def compute_penalty_entropy(tasks):
    """
    Compute normalized entropy of non-zero task penalties in [0, 1].

    Steps:
      1) Collect penalty values from tasks
      2) Ignore penalty == 0
      3) Normalize penalties to probabilities
      4) Compute Shannon entropy using natural log
      5) Normalize by log(N)
    """
    penalties = [max(0.0, float(t.freeze_penalty_factor)) for t in tasks if getattr(t, "freeze_penalty_factor", 0.0) > 0]
    if not penalties:
        return 0.0

    total_penalty = sum(penalties)
    if total_penalty <= 0:
        return 0.0

    probabilities = [p / total_penalty for p in penalties]
    entropy = -sum(p * math.log(p) for p in probabilities if p > 0)
    n = len(probabilities)
    if n <= 1:
        return 0.0

    max_entropy = math.log(n)
    if max_entropy <= 0:
        return 0.0

    normalized = entropy / max_entropy
    return max(0.0, min(1.0, normalized))


def compute_overload_index(tasks, capacity_per_day, planning_horizon):
    """
    Compute overload index based on total task hours.

    Overload_Index = Total_Task_Hours / (Capacity_Per_Day * Planning_Horizon)
    """
    total_hours = sum(t.duration for t in tasks)
    total_capacity = capacity_per_day * planning_horizon
    if total_capacity <= 0:
        return 0.0
    return total_hours / total_capacity


def compute_strategic_weight(task):
    """
    Compute strategic importance weight for a task.

    Weight = (0.7 * effective_priority)
           + (0.2 * (effective_priority / duration))
           - (0.1 * duration)
    """
    if task.duration <= 0:
        return 0.0

    effective_priority = task.effective_priority()
    weight = (
        0.7 * effective_priority
        + 0.2 * (effective_priority / task.duration)
        - 0.1 * task.duration
    )
    return round(weight, 3)


def compute_effective_weight(task):
    """
    Compute selection weight with soft-freeze penalty applied.

    effective_weight = strategic_weight * freeze_penalty_factor
    """
    return round(compute_strategic_weight(task) * task.freeze_penalty_factor, 3)


def _duration_profile(protected_tasks):
    """Return duration-category coverage flags for protected tasks."""
    contains_short = any(task.duration <= 2.0 for task, _ in protected_tasks)
    contains_long = any(task.duration >= 2.0 for task, _ in protected_tasks)
    return contains_short, contains_long


def enforce_structural_diversity(protected_tasks, weighted_tasks, hard_limit):
    """
    Enforce structural duration diversity in protected-task selection.

    Diversity constraint:
      - At least one short task (duration <= 2.0h)
      - At least one long task  (duration >= 2.0h)
    """
    if not protected_tasks:
        return protected_tasks, False

    contains_short, contains_long = _duration_profile(protected_tasks)
    if contains_short and contains_long:
        return protected_tasks, False

    protected_names = {task.name for task, _ in protected_tasks}
    non_protected = [(task, weight) for task, weight in weighted_tasks if task.name not in protected_names]

    missing_short = not contains_short
    missing_long = not contains_long

    swap_in = None
    if missing_short and missing_long:
        # Prefer a single bridge task that satisfies both categories.
        swap_in = next((tw for tw in non_protected if tw[0].duration == 2.0), None)
        if swap_in is None:
            short_candidate = next((tw for tw in non_protected if tw[0].duration <= 2.0), None)
            long_candidate = next((tw for tw in non_protected if tw[0].duration >= 2.0), None)
            if short_candidate and long_candidate:
                swap_in = short_candidate if short_candidate[1] >= long_candidate[1] else long_candidate
            else:
                swap_in = short_candidate or long_candidate
    elif missing_short:
        swap_in = next((tw for tw in non_protected if tw[0].duration <= 2.0), None)
    elif missing_long:
        swap_in = next((tw for tw in non_protected if tw[0].duration >= 2.0), None)

    if swap_in is None:
        return protected_tasks, False

    # Replace the lowest strategic-weight protected task (replace-any policy).
    swap_out = min(protected_tasks, key=lambda x: x[1])
    proposed = [
        (task, weight) for task, weight in protected_tasks if task.name != swap_out[0].name
    ]
    proposed.append(swap_in)
    proposed.sort(key=lambda x: x[1], reverse=True)

    proposed_total = sum(task.duration for task, _ in proposed)
    if proposed_total > hard_limit:
        # Revert if replacement violates capacity.
        return protected_tasks, False

    return proposed, True


def compute_adaptive_recovery(
    overload_index,
    freeze_penalty_factor,
    recovery_base=None
):
    """
    Compute overload-aware damped recovery increment using critical damping.

    recovery_base = 0.20 + 0.10 * (1 - global_overload_index)
    recovery_base = clamp(recovery_base, 0.10, 0.30)

    adaptive_recovery = recovery_base
                        * (1 / global_overload_index)
                        * (1 - freeze_penalty_factor)
    adaptive_recovery = min(adaptive_recovery, 0.30)
    """
    safe_overload = max(overload_index, 1e-6)
    safe_penalty = min(1.0, max(0.4, freeze_penalty_factor))

    if recovery_base is None:
        recovery_base = 0.20 + 0.10 * (1.0 - safe_overload)
    recovery_base = min(RECOVERY_BASE_MAX, max(RECOVERY_BASE_MIN, recovery_base))

    adaptive_recovery = recovery_base * (1.0 / safe_overload) * (1.0 - safe_penalty)
    adaptive_recovery = min(adaptive_recovery, 0.30)
    return max(0.0, adaptive_recovery)


def update_penalty_recovery(
    tasks,
    overload_index,
    daily_capacity=None,
    recovery_base=None,
    remaining_days=None
):
    """
    Recover soft-freeze penalties using global-overload adaptive recovery.

    No task is permanently excluded because penalties are monotonically
    recovered and capped at 1.0.
    """
    penalized_tasks = [t for t in tasks if t.freeze_penalty_factor < 1.0]
    # Terminal damping: keep recovery active with a tighter final-day cap.
    if remaining_days == 0:
        terminal_recovery_cap = 0.12
    else:
        terminal_recovery_cap = 0.30

    allowed_tasks = penalized_tasks

    # Final-day recovery override: avoid concentration bias on long tasks.
    if remaining_days == 0 and penalized_tasks:
        final_day_candidates = sorted(
            penalized_tasks,
            key=lambda t: t.freeze_penalty_factor,
            reverse=True
        )
        final_day_selected = []
        for task in final_day_candidates:
            if task.freeze_penalty_factor > 0.85:
                continue
            if task.duration > 2.5:
                continue
            final_day_selected.append(task)
            if len(final_day_selected) >= 3:
                break
        allowed_tasks = final_day_selected
    # Backlog throttling: diversify reintegration when global overload is low.
    elif overload_index < 0.8 and penalized_tasks:
        # Adaptive backlog relief: allow up to 2 recovery tasks under low overload.
        allowed_recovery_tasks = 1
        if overload_index < 0.8:
            allowed_recovery_tasks = 2
            print("[ADAPTIVE BACKLOG RELIEF]")
            print(f"Global Overload Index: {overload_index:.3f}")
            print(f"Allowed Recovery Tasks: {allowed_recovery_tasks}")
        allowed_recovery_tasks = min(2, max(1, allowed_recovery_tasks))

        sorted_penalized = sorted(
            penalized_tasks,
            key=lambda t: (-t.priority, t.duration)
        )
        effective_daily_capacity = daily_capacity
        if effective_daily_capacity is None:
            effective_daily_capacity = sum(t.duration for t in sorted_penalized)
        duration_cap = 0.5 * effective_daily_capacity
        cumulative_duration = 0.0
        diversified_tasks = []
        for task in sorted_penalized:
            if len(diversified_tasks) >= allowed_recovery_tasks:
                break
            if cumulative_duration + task.duration > duration_cap:
                break
            diversified_tasks.append(task)
            cumulative_duration += task.duration
        allowed_tasks = diversified_tasks
        print("[BACKLOG DIVERSIFIED]")
        print(f"Global Overload Index: {overload_index:.3f}")
        print(f"Allowed Tasks: {len(diversified_tasks)}")
        print(f"Total Recovery Duration: {cumulative_duration:.3f}")
        print(f"Duration Cap: {duration_cap:.3f}")

    updated_count = 0
    for task in allowed_tasks:
        previous_penalty = task.freeze_penalty_factor
        effective_recovery_base = recovery_base
        if effective_recovery_base is None:
            effective_recovery_base = 0.20 + 0.10 * (1.0 - max(overload_index, 1e-6))
        effective_recovery_base = min(
            RECOVERY_BASE_MAX,
            max(RECOVERY_BASE_MIN, effective_recovery_base)
        )
        adaptive_recovery = compute_adaptive_recovery(
            overload_index,
            previous_penalty,
            recovery_base=effective_recovery_base
        )
        adaptive_recovery = min(adaptive_recovery, terminal_recovery_cap)
        # Keep penalty non-negative and strictly non-increasing during recovery.
        new_penalty = max(0.0, previous_penalty - adaptive_recovery)
        task.freeze_penalty_factor = min(previous_penalty, new_penalty)
        updated_count += 1
        print("[ADAPTIVE RECOVERY - CRITICAL]")
        print(f"Task: {task.name}")
        print(f"Global Overload Index: {overload_index:.3f}")
        print(f"Recovery Base: {effective_recovery_base:.3f}")
        print(f"Previous Penalty: {previous_penalty:.3f}")
        print(f"Recovery Applied: {adaptive_recovery:.3f}")
        print(f"New Penalty: {task.freeze_penalty_factor:.3f}")
    return updated_count


def ensure_feasible_task_set(
    tasks,
    capacity_per_day,
    min_active_tasks=MIN_ACTIVE_TASKS,
    min_active_duration=MIN_ACTIVE_DURATION
):
    """
    Enforce feasibility constraints for candidate generation.

    Why this guard exists:
    Deferral/compression interactions can make the active candidate set empty.

    Theoretical reasoning:
    Scheduling requires a non-empty feasible set. This guard enforces:
      1) active task count >= minimum
      2) total active duration >= minimum
      3) total active duration > 0
    by reactivating highest effective-weight deferred tasks first.
    """
    active_tasks = [t for t in tasks if not t.deferred]
    active_duration = sum(t.duration for t in active_tasks)
    reactivated_count = 0

    if (
        len(active_tasks) >= min_active_tasks
        and active_duration >= min_active_duration
        and active_duration > 0
    ):
        return active_tasks, reactivated_count

    deferred_candidates = [t for t in tasks if t.deferred]
    deferred_candidates.sort(key=compute_effective_weight, reverse=True)

    for task in deferred_candidates:
        if (
            len(active_tasks) >= min_active_tasks
            and active_duration >= min_active_duration
            and active_duration > 0
        ):
            break
        if task.duration <= 0:
            continue
        if active_duration + task.duration > capacity_per_day:
            continue
        task.deferred = False
        task.deferral_start_time = None
        active_tasks.append(task)
        active_duration += task.duration
        reactivated_count += 1

    if active_duration == 0:
        for task in deferred_candidates:
            if not task.deferred:
                continue
            if task.duration <= 0:
                continue
            if task.duration > capacity_per_day:
                continue
            task.deferred = False
            task.deferral_start_time = None
            active_tasks.append(task)
            active_duration += task.duration
            reactivated_count += 1
            break

    if reactivated_count > 0:
        print("[FEASIBILITY GUARD ACTIVATED]")
        print(f"Unfroze {reactivated_count} task(s) to prevent deadlock.")

    return active_tasks, reactivated_count


def apply_strategic_compression(
    tasks,
    capacity_per_day=8,
    planning_horizon=5,
    compression_threshold=1.2,
    soft_freeze_penalty=0.4,
    anti_starvation_days=5
):
    """
    Apply soft-freeze compression during overload.

    Compression threshold is hard-isolated via compression_threshold and
    is not overridden by learning modules.
    """
    overload_index = compute_overload_index(tasks, capacity_per_day, planning_horizon)

    print("\n[COMPRESSION CHECK]")
    print("Overload Index: {:.2f}".format(overload_index))
    print("Compression Threshold: {:.2f} [HARD-ISOLATED]".format(compression_threshold))

    if overload_index <= compression_threshold:
        print("[COMPRESSION] Not activated (overload <= threshold)")
        return False

    print("\n" + "=" * 70)
    print("[COMPRESSION MODE ACTIVATED]")
    print("=" * 70)
    print("Overload Index: {:.2f} (threshold: {:.2f})".format(overload_index, compression_threshold))
    print(f"Total Task Hours: {sum(t.duration for t in tasks):.1f}h")
    print(f"Available Capacity: {capacity_per_day * planning_horizon:.1f}h")
    print()

    if not tasks:
        print("[WARNING] No tasks to compress!")
        return False

    weighted_tasks = [(t, compute_effective_weight(t)) for t in tasks]
    weighted_tasks.sort(key=lambda x: x[1], reverse=True)

    protected_tasks = []
    protected_names = set()
    total_protected_hours = 0.0

    protection_target = 0.80 * capacity_per_day
    hard_limit = 0.90 * capacity_per_day

    # Anti-starvation pass: protect high deferral-age tasks first.
    starved_tasks = [(t, w) for (t, w) in weighted_tasks if t.days_deferred >= anti_starvation_days]
    for task, weight in starved_tasks:
        if total_protected_hours + task.duration > hard_limit:
            continue
        protected_tasks.append((task, weight))
        protected_names.add(task.name)
        total_protected_hours += task.duration
        if total_protected_hours >= protection_target:
            break

    # Fill remaining protection budget by highest effective weight.
    for task, weight in weighted_tasks:
        if task.name in protected_names:
            continue
        if total_protected_hours + task.duration > hard_limit:
            continue
        protected_tasks.append((task, weight))
        protected_names.add(task.name)
        total_protected_hours += task.duration
        if total_protected_hours >= protection_target:
            break

    if not protected_tasks and weighted_tasks:
        first_task, first_weight = weighted_tasks[0]
        if first_task.duration <= hard_limit:
            protected_tasks.append((first_task, first_weight))
            protected_names.add(first_task.name)
            total_protected_hours = first_task.duration

    assert total_protected_hours <= hard_limit, (
        "ERROR: Protected hours ({:.2f}h) exceed hard limit ({:.2f}h)!".format(
            total_protected_hours, hard_limit
        )
    )

    # Structural diversity pass: keep protected set duration-balanced.
    protected_tasks, diversity_adjusted = enforce_structural_diversity(
        protected_tasks=protected_tasks,
        weighted_tasks=weighted_tasks,
        hard_limit=hard_limit
    )
    if diversity_adjusted:
        total_protected_hours = sum(task.duration for task, _ in protected_tasks)
        contains_short, contains_long = _duration_profile(protected_tasks)
        print("[STRUCTURAL DIVERSITY ENFORCED]")
        print(f"Protected Count: {len(protected_tasks)}")
        print(f"Total Duration: {total_protected_hours:.3f}")
        print(f"Contains Short Task: {contains_short}")
        print(f"Contains Long Task: {contains_long}")

    # Refresh protected set after diversity adjustment.
    protected_names = {task.name for task, _ in protected_tasks}

    print("[PROTECTING] Capacity-Based Selection (Soft Freeze Enabled)")
    print("Daily Capacity: {}h".format(capacity_per_day))
    print("Protection Target (80%): {:.2f}h".format(protection_target))
    print("Hard Limit (90%): {:.2f}h".format(hard_limit))
    print("Protected Hours: {:.2f}h".format(total_protected_hours))
    print()

    print("Protected Tasks ({} total):".format(len(protected_tasks)))
    for i, (task, weight) in enumerate(protected_tasks, 1):
        task.freeze_penalty_factor = 1.0
        print("   {}. {} [PROTECTED]".format(i, task.name))
        print(
            "      Priority: {}, Effective Priority: {:.2f}, Duration: {}h, Effective Weight: {:.3f}".format(
                task.priority, task.effective_priority(), task.duration, weight
            )
        )

    print()
    print("[SOFT FREEZE] Applying penalty to non-protected tasks:")
    penalized_count = 0
    for task, _ in weighted_tasks:
        if task.name in protected_names:
            continue
        task.freeze_penalty_factor = soft_freeze_penalty
        penalized_count += 1
        print("[SOFT FREEZE APPLIED]")
        print(f"Task: {task.name} penalty set to {soft_freeze_penalty:.1f}")

    print()
    print("[SUMMARY] COMPRESSION STATUS:")
    penalized_hours = sum(t.duration for t, _ in weighted_tasks if t.name not in protected_names)
    print(f"   Protected Hours: {total_protected_hours:.1f}h")
    print(f"   Penalized Hours: {penalized_hours:.1f}h")
    print(f"   Penalized Tasks: {penalized_count}")
    print("=" * 70 + "\n")

    return True


def update_freeze_status(tasks, overload_index=1.0, daily_capacity=None, remaining_days=None):
    """
    Compatibility wrapper.

    Hard-freeze countdown logic is removed; this now performs penalty recovery.
    """
    return update_penalty_recovery(
        tasks,
        overload_index=overload_index,
        daily_capacity=daily_capacity,
        remaining_days=remaining_days
    )


def filter_active_tasks(tasks):
    """Filter tasks to include only currently non-deferred tasks."""
    return [t for t in tasks if not t.deferred]


def get_compression_status(tasks):
    """Get current soft-freeze status summary."""
    active_tasks = [t for t in tasks if not t.deferred]
    penalized_tasks = [t for t in tasks if t.freeze_penalty_factor < 1.0]
    return {
        "total_tasks": len(tasks),
        "active_tasks": len(active_tasks),
        "penalized_tasks": len(penalized_tasks),
        "active_hours": sum(t.duration for t in active_tasks),
        "penalized_hours": sum(t.duration for t in penalized_tasks),
        "compression_active": len(penalized_tasks) > 0,
    }


def print_compression_status(tasks):
    """Print human-readable soft-freeze compression status."""
    status = get_compression_status(tasks)
    if status["penalized_tasks"] == 0:
        print("[OK] No soft freeze penalties active")
    else:
        print("\n[INFO] COMPRESSION STATUS:")
        print(f"   Active Tasks: {status['active_tasks']}/{status['total_tasks']}")
        print(f"   Active Hours: {status['active_hours']:.1f}h")
        print(f"   Penalized Tasks: {status['penalized_tasks']}")
        print(f"   Penalized Hours: {status['penalized_hours']:.1f}h")
