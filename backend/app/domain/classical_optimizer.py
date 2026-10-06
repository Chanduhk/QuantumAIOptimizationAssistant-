"""Deterministic maximum-weight task/hour assignment over validated matrices."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from itertools import permutations
from time import perf_counter
from typing import Any

from backend.app.domain.prediction_matrix import (
    PredictionMatrix,
    validate_prediction_matrix,
    validate_development_demo_matrix,
    validate_synthetic_test_matrix,
)


@dataclass(frozen=True)
class ClassicalAssignment:
    task_id: int | str
    assigned_hour: int
    prediction_score: float


@dataclass(frozen=True)
class ClassicalCandidate:
    assignments: tuple[ClassicalAssignment, ...]
    total_objective: float
    feasibility: bool
    solver: str
    runtime_seconds: float
    input_provenance: dict[str, Any]
    mode: str
    constraint_violations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "CANDIDATE",
            "assignments": [asdict(item) for item in self.assignments],
            "total_objective": self.total_objective,
            "feasibility": self.feasibility,
            "solver": self.solver,
            "runtime_seconds": self.runtime_seconds,
            "input_provenance": dict(self.input_provenance),
            "mode": self.mode,
            "constraint_violations": list(self.constraint_violations),
        }


class ClassicalOptimizer:
    """Maximum-score one-task/one-hour assignment solver.

    Test matrices are accepted only when the caller explicitly constructs the
    optimizer with ``allow_test_matrices=True``. Production mode requires the
    validated real-model provenance and a proven task/hour interaction.
    """

    def __init__(self, *, allow_test_matrices: bool = False) -> None:
        self.allow_test_matrices = allow_test_matrices

    def optimize(self, matrix: PredictionMatrix) -> ClassicalCandidate:
        matrix = self._validate(matrix)
        tasks = tuple(sorted(matrix.task_ids, key=str))
        hours = tuple(sorted(matrix.candidate_hours))
        scores = [[matrix.score(task, hour) for hour in hours] for task in tasks]

        started = perf_counter()
        assignment = _maximum_weight_assignment(scores)
        elapsed = perf_counter() - started
        results = tuple(
            ClassicalAssignment(task, hours[column], scores[row][column])
            for row, (task, column) in enumerate(zip(tasks, assignment))
        )
        objective = math.fsum(item.prediction_score for item in results)
        violations = _constraint_violations(results, tasks, hours)
        if violations:
            raise ValueError(f"classical solver produced an infeasible assignment: {', '.join(violations)}")

        if matrix.mode == "TEST/SYNTHETIC":
            provenance = {
                "label": "TEST/SYNTHETIC",
                "model_version": None,
                "feature_schema_version": None,
                "target_schema_version": None,
                "nontriviality_claim": "TEST_ONLY_NOT_PRODUCTION_EVIDENCE",
            }
        elif matrix.mode == "DEVELOPMENT/DEMO":
            provenance = {
                "label": "DEVELOPMENT/DEMO",
                "model_version": matrix.model_version,
                "feature_schema_version": matrix.feature_schema_version,
                "target_schema_version": matrix.target_schema_version,
                "nontriviality_claim": "DEMO_EVIDENCE_ONLY_NOT_REAL_USER_EVIDENCE",
            }
        else:
            provenance = {
                "label": "PRODUCTION_MODEL_PREDICTIONS",
                "model_version": matrix.model_version,
                "feature_schema_version": matrix.feature_schema_version,
                "target_schema_version": matrix.target_schema_version,
                "nontriviality_claim": "PROVEN_FOR_THIS_VALIDATED_MATRIX",
            }
        return ClassicalCandidate(
            assignments=results,
            total_objective=objective,
            feasibility=True,
            solver="deterministic_hungarian_assignment",
            runtime_seconds=elapsed,
            input_provenance=provenance,
            mode=matrix.mode,
            constraint_violations=(),
        )

    def reference_optimize(self, matrix: PredictionMatrix, *, max_tasks: int = 4) -> ClassicalCandidate:
        """Independent exhaustive reference for small test/verification cases."""
        matrix = self._validate(matrix)
        if len(matrix.task_ids) > max_tasks:
            raise ValueError(f"reference solver is limited to {max_tasks} tasks")
        tasks = tuple(sorted(matrix.task_ids, key=str))
        hours = tuple(sorted(matrix.candidate_hours))
        started = perf_counter()
        best_assignment: tuple[int, ...] | None = None
        best_score = -math.inf
        for selected_hours in permutations(hours, len(tasks)):
            score = math.fsum(matrix.score(task, hour) for task, hour in zip(tasks, selected_hours))
            if score > best_score or (score == best_score and (best_assignment is None or selected_hours < best_assignment)):
                best_score = score
                best_assignment = selected_hours
        assert best_assignment is not None
        elapsed = perf_counter() - started
        results = tuple(
            ClassicalAssignment(task, hour, matrix.score(task, hour))
            for task, hour in zip(tasks, best_assignment)
        )
        violations = _constraint_violations(results, tasks, hours)
        return ClassicalCandidate(
            assignments=results,
            total_objective=best_score,
            feasibility=not violations,
            solver="exhaustive_reference",
            runtime_seconds=elapsed,
            input_provenance={"label": matrix.mode, "reference_only": True},
            mode=matrix.mode,
            constraint_violations=violations,
        )

    def _validate(self, matrix: PredictionMatrix) -> PredictionMatrix:
        if not isinstance(matrix, PredictionMatrix):
            raise TypeError("ClassicalOptimizer accepts only a validated PredictionMatrix")
        if matrix.mode == "TEST/SYNTHETIC":
            if not self.allow_test_matrices:
                raise ValueError("TEST/SYNTHETIC matrices require explicit test-mode optimizer construction")
            validated = validate_synthetic_test_matrix(matrix.cells, matrix.task_ids, matrix.candidate_hours)
        elif matrix.mode == "DEVELOPMENT/DEMO":
            if not self.allow_test_matrices:
                raise ValueError("DEVELOPMENT/DEMO matrices require explicit non-production optimizer opt-in")
            validated = validate_development_demo_matrix(matrix.cells, matrix.task_ids, matrix.candidate_hours)
            if validated.nontriviality != "PASS":
                raise ValueError("development/demo matrix has NOT_PROVEN non-triviality")
        elif matrix.mode == "PRODUCTION":
            validated = validate_prediction_matrix(matrix.cells, matrix.task_ids, matrix.candidate_hours)
            if not validated.optimizer_eligible:
                raise ValueError("production prediction matrix has NOT_PROVEN non-triviality and is not optimizer eligible")
        else:
            raise ValueError("matrix mode must be PRODUCTION, DEVELOPMENT/DEMO, or TEST/SYNTHETIC")
        if (
            matrix.nontriviality != validated.nontriviality
            or matrix.assignment_contrast != validated.assignment_contrast
            or matrix.model_version != validated.model_version
            or matrix.feature_schema_version != validated.feature_schema_version
            or matrix.target_schema_version != validated.target_schema_version
            or tuple(matrix.task_ids) != tuple(validated.task_ids)
            or tuple(matrix.candidate_hours) != tuple(validated.candidate_hours)
        ):
            raise ValueError("PredictionMatrix derived fields do not match its validated cells")
        return validated


def _maximum_weight_assignment(scores: list[list[float]]) -> tuple[int, ...]:
    """Rectangular Hungarian algorithm; rows <= columns, deterministic ties."""
    row_count = len(scores)
    if row_count == 0:
        raise ValueError("assignment matrix must contain at least one task")
    column_count = len(scores[0])
    if column_count < row_count or any(len(row) != column_count for row in scores):
        raise ValueError("assignment matrix dimensions are inconsistent or infeasible")
    if any(not math.isfinite(value) for row in scores for value in row):
        raise ValueError("assignment scores must all be finite")

    # Standard 1-indexed shortest augmenting path formulation for min-cost
    # assignment. Negating score converts this maximum-weight problem.
    u = [0.0] * (row_count + 1)
    v = [0.0] * (column_count + 1)
    p = [0] * (column_count + 1)
    way = [0] * (column_count + 1)
    for i in range(1, row_count + 1):
        p[0] = i
        j0 = 0
        minv = [math.inf] * (column_count + 1)
        used = [False] * (column_count + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = math.inf
            j1 = 0
            for j in range(1, column_count + 1):
                if used[j]:
                    continue
                cur = -scores[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            if not math.isfinite(delta):
                raise ValueError("no feasible assignment exists")
            for j in range(column_count + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    assigned = [-1] * row_count
    for j in range(1, column_count + 1):
        if p[j] != 0:
            assigned[p[j] - 1] = j - 1
    if any(column < 0 for column in assigned):
        raise ValueError("solver failed to assign every task")
    return tuple(assigned)


def _constraint_violations(
    assignments: tuple[ClassicalAssignment, ...],
    task_ids: tuple[int | str, ...],
    candidate_hours: tuple[int, ...],
) -> tuple[str, ...]:
    violations: list[str] = []
    assigned_tasks = [item.task_id for item in assignments]
    assigned_hours = [item.assigned_hour for item in assignments]
    if len(assignments) != len(task_ids) or set(assigned_tasks) != set(task_ids):
        violations.append("each eligible task must be assigned exactly once")
    if len(set(assigned_hours)) != len(assigned_hours):
        violations.append("each candidate hour may receive at most one task")
    if any(hour not in candidate_hours for hour in assigned_hours):
        violations.append("assigned hour must belong to the candidate domain")
    return tuple(violations)
