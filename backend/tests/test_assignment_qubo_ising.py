from __future__ import annotations

from itertools import product

import pytest

from backend.app.domain.assignment_qubo_ising import (
    AssignmentQuboIsingBuilder,
    evaluate_ising,
    evaluate_qubo,
)
from backend.app.domain.classical_optimizer import ClassicalOptimizer
from backend.app.domain.prediction_matrix import create_synthetic_test_matrix


def _matrix(task_ids, hours):
    scores = []
    for ti, task in enumerate(task_ids):
        for hi, hour in enumerate(hours):
            # Deterministic test-only values; not production predictions.
            scores.append((task, hour, float(5 + ((ti + 2) * (hi + 3) * 7) % 89)))
    return create_synthetic_test_matrix(task_ids, hours, scores)


@pytest.mark.parametrize(
    ("tasks", "hours"),
    [(["a"], [9]), (["a", "b"], [9, 10]), (["a", "b", "c"], [8, 9, 10]), (["a", "b"], [7, 8, 9])],
)
def test_exhaustive_qubo_and_ising_equivalence_to_classical(tasks, hours) -> None:
    matrix = _matrix(tasks, hours)
    formulation = AssignmentQuboIsingBuilder(allow_test_matrices=True).build(matrix)
    variable_ids = tuple(variable.variable_id for variable in formulation.qubo.variables)
    feasible_energies = []
    all_qubo_energies = []
    for bits in product((0, 1), repeat=len(variable_ids)):
        assignment = dict(zip(variable_ids, bits))
        spins = {variable_id: 1 - 2 * bit for variable_id, bit in assignment.items()}
        energy = evaluate_qubo(formulation.qubo, assignment)
        ising_energy = evaluate_ising(formulation.ising, spins)
        assert ising_energy == pytest.approx(energy, abs=1e-9)
        selected = {
            (task, hour)
            for variable_id, task, hour in formulation.variable_mapping
            if assignment[variable_id] == 1
        }
        task_counts = [sum((task, hour) in selected for hour in hours) for task in tasks]
        hour_counts = [sum((task, hour) in selected for task in tasks) for hour in hours]
        is_feasible = all(count == 1 for count in task_counts) and all(count <= 1 for count in hour_counts)
        objective = sum(matrix.score(task, hour) for task, hour in selected)
        assert energy == pytest.approx(-objective + _constraint_penalty(formulation, selected, tasks, hours))
        if is_feasible:
            feasible_energies.append((energy, objective))
        all_qubo_energies.append(energy)

    best_energy = min(all_qubo_energies)
    minimizing = [energy for energy in all_qubo_energies if energy == pytest.approx(best_energy)]
    assert len(minimizing) >= 1
    assert best_energy == pytest.approx(min(energy for energy, _ in feasible_energies))
    classical = ClassicalOptimizer(allow_test_matrices=True).optimize(matrix)
    assert formulation.classical_objective == pytest.approx(classical.total_objective)
    assert -best_energy == pytest.approx(classical.total_objective)
    assert formulation.qubo.constant_offset == pytest.approx(len(tasks) * formulation.penalty)
    assert formulation.penalty == pytest.approx(formulation.objective_score_bound + 1.0)


def _constraint_penalty(formulation, selected, tasks, hours):
    penalty_count = sum((sum((task, hour) in selected for hour in hours) - 1) ** 2 for task in tasks)
    penalty_count += sum(
        sum((task, hour) in selected for task in tasks)
        * (sum((task, hour) in selected for task in tasks) - 1)
        // 2
        for hour in hours
    )
    return formulation.penalty * penalty_count


def test_variable_mapping_is_deterministic_and_includes_constraint_metadata() -> None:
    matrix = _matrix(["b", "a"], [10, 9])
    builder = AssignmentQuboIsingBuilder(allow_test_matrices=True)
    first = builder.build(matrix)
    second = builder.build(matrix)
    assert first.variable_mapping == second.variable_mapping
    assert len(first.qubo.constraints) == 4
    assert first.mode == "TEST/SYNTHETIC"
    assert first.qubo.metadata["mode"] == "TEST/SYNTHETIC"
    assert first.ising.metadata["transformation"] == "x=(1-z)/2"

    mixed = _matrix(["1", 1], [9, 10])
    shuffled = create_synthetic_test_matrix(
        [1, "1"], [10, 9],
        [(task, hour, mixed.score(task, hour)) for task in (1, "1") for hour in (10, 9)],
    )
    assert builder.build(mixed).variable_mapping == builder.build(shuffled).variable_mapping


def test_synthetic_matrix_requires_explicit_test_mode_and_never_passes_production_gate() -> None:
    matrix = _matrix(["a"], [9])
    with pytest.raises(ValueError, match="explicit test-mode"):
        AssignmentQuboIsingBuilder().build(matrix)


def test_invalid_incomplete_or_nonfinite_matrix_is_rejected() -> None:
    from dataclasses import replace
    from backend.app.domain.prediction_matrix import create_synthetic_test_matrix

    matrix = _matrix(["a"], [9, 10])
    with pytest.raises(ValueError, match="incomplete"):
        AssignmentQuboIsingBuilder(allow_test_matrices=True).build(replace(matrix, cells=matrix.cells[:-1]))
    for value in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite"):
            create_synthetic_test_matrix(["a"], [9], [("a", 9, value)])
