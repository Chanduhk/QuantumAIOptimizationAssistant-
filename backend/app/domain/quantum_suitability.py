"""Evidence-gated suitability decision for the current F9.2/F9.3 problem."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from backend.app.domain.assignment_qubo_ising import AssignmentQuboIsing, AssignmentQuboIsingBuilder
from backend.app.domain.classical_optimizer import ClassicalCandidate, ClassicalOptimizer
from backend.app.domain.prediction_matrix import (
    PredictionMatrix,
    validate_prediction_matrix,
    validate_synthetic_test_matrix,
    validate_development_demo_matrix,
)
from backend.app.quantum.optimization import QAOAConfig

MAX_LOCAL_QUBITS = 8
MAX_PARAMETER_TRIALS = 25
MAX_LOCAL_SHOTS = 10_000
MAX_QAOA_DEPTH = 3


@dataclass(frozen=True)
class QuantumSuitabilityResult:
    status: str
    mode: str
    reasons: tuple[str, ...]
    task_count: int | None = None
    hour_count: int | None = None
    variable_count: int | None = None
    constraint_count: int | None = None
    qaoa_config: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "reasons": list(self.reasons),
            "task_count": self.task_count,
            "candidate_hour_count": self.hour_count,
            "variable_count": self.variable_count,
            "constraint_count": self.constraint_count,
            "qaoa_config": dict(self.qaoa_config) if self.qaoa_config is not None else None,
            "physical_hardware": False,
            "quantum_advantage_claimed": False,
        }


class QuantumSuitabilityAnalyzer:
    """Validate only already-established matrix, objective, formulation, and limits."""

    def assess(
        self,
        matrix: PredictionMatrix | None,
        classical_candidate: ClassicalCandidate | dict[str, Any] | None,
        formulation: AssignmentQuboIsing | None,
        *,
        config: QAOAConfig | None = None,
        allow_test_mode: bool = False,
    ) -> QuantumSuitabilityResult:
        if matrix is None:
            return QuantumSuitabilityResult(
                "NOT_READY", "PRODUCTION", ("complete eligible prediction matrix is unavailable",)
            )
        mode = getattr(matrix, "mode", "UNKNOWN")
        task_count = len(getattr(matrix, "task_ids", ()))
        hour_count = len(getattr(matrix, "candidate_hours", ()))
        if not isinstance(matrix, PredictionMatrix):
            return self._result("NOT_READY", mode, "prediction matrix has an unsupported type")
        if mode in {"TEST/SYNTHETIC", "DEVELOPMENT/DEMO"} and not allow_test_mode:
            return self._result("NOT_READY", mode, f"{mode} evidence requires explicit non-production opt-in")
        if mode not in {"PRODUCTION", "TEST/SYNTHETIC", "DEVELOPMENT/DEMO"}:
            return self._result("NOT_READY", mode, "prediction matrix mode is invalid")
        if not task_count or not hour_count:
            return self._result("NOT_SUPPORTED", mode, "task/hour dimensions must be non-empty")
        if task_count > hour_count:
            return self._result("NOT_SUPPORTED", mode, "task count exceeds available candidate-hour count")
        try:
            validated = (
                validate_synthetic_test_matrix(matrix.cells, matrix.task_ids, matrix.candidate_hours)
                if mode == "TEST/SYNTHETIC"
                else validate_development_demo_matrix(matrix.cells, matrix.task_ids, matrix.candidate_hours)
                if mode == "DEVELOPMENT/DEMO"
                else validate_prediction_matrix(matrix.cells, matrix.task_ids, matrix.candidate_hours)
            )
        except (TypeError, ValueError) as exc:
            return self._result("NOT_READY", mode, f"matrix/provenance validation failed: {exc}", task_count, hour_count)
        if (
            matrix.nontriviality != validated.nontriviality
            or matrix.assignment_contrast != validated.assignment_contrast
            or matrix.task_ids != validated.task_ids
            or matrix.candidate_hours != validated.candidate_hours
            or matrix.model_version != validated.model_version
            or matrix.feature_schema_version != validated.feature_schema_version
            or matrix.target_schema_version != validated.target_schema_version
        ):
            return self._result("NOT_READY", mode, "matrix derived fields do not match validated cells", task_count, hour_count)
        if mode == "PRODUCTION" and not all(
            (validated.model_version, validated.feature_schema_version, validated.target_schema_version)
        ):
            return self._result("NOT_READY", mode, "compatible model and schema provenance is incomplete", task_count, hour_count)
        if validated.nontriviality != "PASS":
            return self._result("NOT_SUITABLE", mode, "assignment nontriviality has not been demonstrated", task_count, hour_count)

        try:
            solver = ClassicalOptimizer(allow_test_matrices=allow_test_mode)
            validated_classical = solver.optimize(validated)
        except (TypeError, ValueError) as exc:
            return self._result("NOT_READY", mode, f"classical objective validation failed: {exc}", task_count, hour_count)
        if not _candidate_matches(classical_candidate, validated_classical):
            return self._result("NOT_READY", mode, "supplied classical candidate is absent, infeasible, or mismatched", task_count, hour_count)

        try:
            expected_formulation = AssignmentQuboIsingBuilder(allow_test_matrices=allow_test_mode).build(validated)
        except (TypeError, ValueError) as exc:
            return self._result("NOT_READY", mode, f"validated F9.3 formulation could not be built: {exc}", task_count, hour_count)
        if not isinstance(formulation, AssignmentQuboIsing):
            return self._result("NOT_READY", mode, "validated F9.3 QUBO/Ising formulation is unavailable", task_count, hour_count)
        if (
            formulation.mode != mode
            or formulation.qubo.to_dict() != expected_formulation.qubo.to_dict()
            or formulation.ising.to_dict() != expected_formulation.ising.to_dict()
            or formulation.variable_mapping != expected_formulation.variable_mapping
        ):
            return self._result("NOT_READY", mode, "F9.3 QUBO/Ising formulation does not match the validated matrix", task_count, hour_count)

        qaoa_config = config or QAOAConfig()
        if not isinstance(qaoa_config, QAOAConfig):
            return self._result("NOT_SUPPORTED", mode, "QAOA configuration is invalid", task_count, hour_count)
        variable_count = len(formulation.ising.variables)
        constraints = len(formulation.qubo.constraints)
        if variable_count > min(MAX_LOCAL_QUBITS, qaoa_config.max_qubits):
            return self._result("NOT_SUPPORTED", mode, "QAOA variable count exceeds local simulator limit", task_count, hour_count, variable_count, constraints)
        if qaoa_config.depth > MAX_QAOA_DEPTH:
            return self._result("NOT_SUPPORTED", mode, "QAOA depth exceeds local configuration limit", task_count, hour_count, variable_count, constraints)
        if qaoa_config.max_iterations > MAX_PARAMETER_TRIALS:
            return self._result("NOT_SUPPORTED", mode, "QAOA parameter iterations exceed local configuration limit", task_count, hour_count, variable_count, constraints)
        if qaoa_config.shots > MAX_LOCAL_SHOTS:
            return self._result("NOT_SUPPORTED", mode, "QAOA shot count exceeds local configuration limit", task_count, hour_count, variable_count, constraints)

        return QuantumSuitabilityResult(
            status="SUITABLE",
            mode=mode,
            reasons=(
                "complete matrix and prediction provenance validated",
                "F9.2 classical objective and feasible candidate validated",
                "assignment nontriviality passed",
                "F9.3 QUBO/Ising formulation matches the matrix",
                "QAOA dimensions and configuration are within local limits",
                ("TEST/SYNTHETIC mode is algorithm evidence only" if mode == "TEST/SYNTHETIC" else
                 "DEVELOPMENT/DEMO model and lifecycle evidence only; not real-user or production evidence" if mode == "DEVELOPMENT/DEMO" else
                 "production provenance passed"),
            ),
            task_count=task_count,
            hour_count=hour_count,
            variable_count=variable_count,
            constraint_count=constraints,
            qaoa_config={
                "depth": qaoa_config.depth,
                "max_iterations": qaoa_config.max_iterations,
                "shots": qaoa_config.shots,
                "seed": qaoa_config.seed,
                "max_qubits": min(MAX_LOCAL_QUBITS, qaoa_config.max_qubits),
            },
        )

    @staticmethod
    def _result(status, mode, reason, task_count=None, hour_count=None, variable_count=None, constraint_count=None):
        return QuantumSuitabilityResult(
            status=status,
            mode=mode,
            reasons=(reason,),
            task_count=task_count,
            hour_count=hour_count,
            variable_count=variable_count,
            constraint_count=constraint_count,
        )


def _candidate_matches(candidate: ClassicalCandidate | dict[str, Any] | None, expected: ClassicalCandidate) -> bool:
    if isinstance(candidate, ClassicalCandidate):
        data = candidate.to_dict()
    elif isinstance(candidate, dict):
        data = candidate
    else:
        return False
    try:
        if data.get("status") not in {None, "CANDIDATE"} or data.get("feasibility") is not True:
            return False
        objective = float(data["total_objective"])
        if not math.isfinite(objective) or not math.isclose(objective, expected.total_objective, rel_tol=0.0, abs_tol=1e-9):
            return False
        if data.get("constraint_violations", []) not in ([], ()):
            return False
        actual = data.get("assignments")
        if not isinstance(actual, (list, tuple)):
            return False
        normalized = sorted(
            [(
                item.task_id if hasattr(item, "task_id") else item.get("task_id"),
                item.assigned_hour if hasattr(item, "assigned_hour") else item.get("assigned_hour"),
            ) for item in actual],
            key=lambda pair: (type(pair[0]).__name__, str(pair[0]), pair[1]),
        )
        expected_pairs = sorted(
            ((item.task_id, item.assigned_hour) for item in expected.assignments),
            key=lambda pair: (type(pair[0]).__name__, str(pair[0]), pair[1]),
        )
        return normalized == expected_pairs
    except (KeyError, TypeError, ValueError, AttributeError):
        return False
