"""QUBO/Ising formulation for the validated F9.2 task-hour assignment."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from backend.app.domain.classical_optimizer import ClassicalOptimizer
from backend.app.domain.prediction_matrix import PredictionMatrix
from backend.app.quantum.domain import (
    ConstraintSense,
    IsingProblem,
    ObjectiveSense,
    QUBOProblem,
    QuantumConstraint,
    QuantumObjective,
    QuantumVariable,
)
from backend.app.quantum.formulation import QUBOToIsingConverter


@dataclass(frozen=True)
class AssignmentQuboIsing:
    """Matched QUBO/Ising models plus their assignment variable mapping."""

    qubo: QUBOProblem
    ising: IsingProblem
    variable_mapping: tuple[tuple[str, int | str, int], ...]
    penalty: float
    objective_score_bound: float
    classical_objective: float
    mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "mode": self.mode,
            "qubo": self.qubo.to_dict(),
            "ising": self.ising.to_dict(),
            "variable_mapping": [
                {"variable_id": var_id, "task_id": task_id, "candidate_hour": hour}
                for var_id, task_id, hour in self.variable_mapping
            ],
            "penalty": self.penalty,
            "objective_score_bound": self.objective_score_bound,
            "classical_objective": self.classical_objective,
            "quantum_execution": "NOT_IMPLEMENTED",
        }


class AssignmentQuboIsingBuilder:
    """Build a penalty-encoded assignment model, without executing a solver."""

    def __init__(self, *, allow_test_matrices: bool = False) -> None:
        self.allow_test_matrices = allow_test_matrices

    def build(self, matrix: PredictionMatrix) -> AssignmentQuboIsing:
        if not isinstance(matrix, PredictionMatrix):
            raise ValueError("a validated PredictionMatrix is required")
        candidate = ClassicalOptimizer(allow_test_matrices=self.allow_test_matrices).optimize(matrix)
        # Include type in the key because integer 1 and string "1" are
        # distinct accepted task IDs but have the same string form.
        tasks = tuple(sorted(matrix.task_ids, key=lambda task: (type(task).__name__, str(task))))
        hours = tuple(sorted(matrix.candidate_hours))
        variable_ids = {
            (task, hour): f"x_{task_index}_{hour_index}"
            for task_index, task in enumerate(tasks)
            for hour_index, hour in enumerate(hours)
        }
        variables = tuple(
            QuantumVariable(
                variable_id=variable_ids[(task, hour)],
                name=f"assign_task_{task_index}_hour_{hour_index}",
                index=task_index * len(hours) + hour_index,
                metadata={"task_id": task, "candidate_hour": hour},
            )
            for task_index, task in enumerate(tasks)
            for hour_index, hour in enumerate(hours)
        )

        scores = {(task, hour): matrix.score(task, hour) for task in tasks for hour in hours}
        score_bound = math.fsum(scores.values())
        # Any infeasible binary assignment has >=1 integer constraint violation.
        # Its total score is <= score_bound; this strict bound makes its energy
        # positive while every feasible assignment has energy <= 0.
        penalty = score_bound + 1.0
        if not math.isfinite(penalty):
            raise ValueError("derived penalty is not finite")

        linear: dict[str, float] = {}
        quadratic: dict[tuple[str, str], float] = {}
        for task in tasks:
            for hour in hours:
                variable_id = variable_ids[(task, hour)]
                # -score converts maximization to minimization; -M is the
                # linear part of M*(sum_h x[t,h] - 1)^2.
                linear[variable_id] = -scores[(task, hour)] - penalty
            for index, hour_left in enumerate(hours):
                for hour_right in hours[index + 1 :]:
                    pair = tuple(sorted((variable_ids[(task, hour_left)], variable_ids[(task, hour_right)])))
                    quadratic[pair] = 2.0 * penalty
        for hour in hours:
            for task_index, task_left in enumerate(tasks):
                for task_right in tasks[task_index + 1 :]:
                    pair = tuple(sorted((variable_ids[(task_left, hour)], variable_ids[(task_right, hour)])))
                    quadratic[pair] = penalty

        constraints = tuple(
            QuantumConstraint(
                constraint_id=f"task_once_{index}",
                name=f"task_{index}_assigned_exactly_once",
                sense=ConstraintSense.EQ,
                rhs=1.0,
                coefficients={variable_ids[(task, hour)]: 1.0 for hour in hours},
                metadata={"task_id": task, "hard": True},
            )
            for index, task in enumerate(tasks)
        ) + tuple(
            QuantumConstraint(
                constraint_id=f"hour_capacity_{index}",
                name=f"hour_{hour}_at_most_one_task",
                sense=ConstraintSense.LE,
                rhs=1.0,
                coefficients={variable_ids[(task, hour)]: 1.0 for task in tasks},
                metadata={"candidate_hour": hour, "hard": True},
            )
            for index, hour in enumerate(hours)
        )
        provenance = {
            "source": "F9.2 PredictionMatrix",
            "mode": matrix.mode,
            "task_ids": tuple(tasks),
            "candidate_hours": tuple(hours),
            "variable_mapping": tuple(
                (variable_ids[(task, hour)], task, hour)
                for task in tasks
                for hour in hours
            ),
            "model_version": matrix.model_version,
            "feature_schema_version": matrix.feature_schema_version,
            "target_schema_version": matrix.target_schema_version,
            "nontriviality": matrix.nontriviality,
            "assignment_contrast": matrix.assignment_contrast,
            "classical_solver": candidate.solver,
            "classical_objective_validated": candidate.total_objective,
            "penalty_derivation": "1 + sum of all nonnegative validated cell scores",
            "qubo_convention": "constant + linear*x + quadratic*x*x; minimized",
            "spin_mapping": "x=(1-z)/2",
        }
        qubo = QUBOProblem(
            problem_id="task_hour_assignment_f93",
            name="F9.2 task-hour assignment QUBO",
            variables=variables,
            linear_coefficients=linear,
            quadratic_coefficients=quadratic,
            constant_offset=len(tasks) * penalty,
            objective=QuantumObjective(
                objective_id="maximize_f92_prediction_score",
                name="F9.2 total task-hour prediction score",
                sense=ObjectiveSense.MAXIMIZE,
                metadata={"original_expression": "maximize sum P[t,h] * x[t,h]", "energy_direction": "MINIMIZE"},
            ),
            constraints=constraints,
            metadata={
                **provenance,
                "objective_transformed_for_minimization": True,
                "constraint_metadata": (
                    "each task exactly once",
                    "each candidate hour at most once",
                ),
                "penalty": penalty,
                "objective_score_bound": score_bound,
            },
        )
        ising = _qubo_to_minus_spin_ising(qubo)
        return AssignmentQuboIsing(
            qubo=qubo,
            ising=ising,
            variable_mapping=tuple((variable_ids[pair], pair[0], pair[1]) for pair in variable_ids),
            penalty=penalty,
            objective_score_bound=score_bound,
            classical_objective=candidate.total_objective,
            mode=matrix.mode,
        )


def _qubo_to_minus_spin_ising(problem: QUBOProblem) -> IsingProblem:
    """Convert with the requested convention x=(1-z)/2 (z in {-1,+1})."""
    fields = {variable.variable_id: 0.0 for variable in problem.variables}
    couplings: dict[tuple[str, str], float] = {}
    offset = problem.constant_offset
    for variable_id, coefficient in problem.linear_coefficients.items():
        fields[variable_id] -= coefficient / 2.0
        offset += coefficient / 2.0
    for (left, right), coefficient in problem.quadratic_coefficients.items():
        fields[left] -= coefficient / 4.0
        fields[right] -= coefficient / 4.0
        couplings[(left, right)] = coefficient / 4.0
        offset += coefficient / 4.0
    return IsingProblem(
        problem_id="task_hour_assignment_f93_ising",
        name="F9.2 task-hour assignment Ising",
        variables=tuple(variable.variable_id for variable in problem.variables),
        linear_coefficients={key: value for key, value in fields.items() if value != 0.0},
        quadratic_coefficients={key: value for key, value in couplings.items() if value != 0.0},
        constant_offset=offset,
        objective=problem.objective,
        metadata={
            "source_problem_id": problem.problem_id,
            "source_problem_type": "QUBO",
            "transformation": "x=(1-z)/2",
            "task_hour_variable_mapping": problem.metadata["variable_mapping"],
            "provenance": problem.metadata["mode"],
        },
    )


def evaluate_qubo(problem: QUBOProblem, assignment: dict[str, int]) -> float:
    return QUBOToIsingConverter.evaluate_qubo_energy(problem, assignment)


def evaluate_ising(problem: IsingProblem, spins: dict[str, int]) -> float:
    return QUBOToIsingConverter.evaluate_ising_energy(problem, spins)
