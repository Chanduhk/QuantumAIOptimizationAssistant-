"""F9.3 assignment adapter for the repository's bounded local QAOA engine."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from backend.app.domain.assignment_qubo_ising import (
    AssignmentQuboIsing,
    AssignmentQuboIsingBuilder,
    evaluate_ising,
    evaluate_qubo,
)
from backend.app.domain.classical_optimizer import ClassicalOptimizer
from backend.app.domain.prediction_matrix import PredictionMatrix
from backend.app.domain.quantum_suitability import QuantumSuitabilityAnalyzer
from backend.app.quantum.baseline import ExactClassicalSolver
from backend.app.quantum.domain import IsingProblem
from backend.app.quantum.optimization import (
    DeterministicQAOAParameterOptimizer,
    QAOAConfig,
    QAOAEngine,
)

MAX_LOCAL_QUBITS = 8
MAX_PARAMETER_TRIALS = 25
MAX_LOCAL_SHOTS = 10_000
MAX_QAOA_DEPTH = 3
_TOLERANCE = 1e-9


@dataclass(frozen=True)
class AssignmentQAOAResult:
    status: str
    mode: str
    reason: str | None = None
    candidate: dict[str, Any] | None = None
    classical_objective: float | None = None
    exact_qubo_energy: float | None = None
    exact_qubo_objective: float | None = None
    approximation_ratio: float | None = None
    approximation_ratio_status: str = "UNAVAILABLE"
    expectation_energy: float | None = None
    statevector_norm: float | None = None
    measurement_distribution: tuple[dict[str, Any], ...] = ()
    parameters: dict[str, Any] | None = None
    parameter_trials: int = 0
    runtime_backend: str | None = None
    suitability_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "reason": self.reason,
            "candidate": dict(self.candidate) if self.candidate is not None else None,
            "classical_objective": self.classical_objective,
            "exact_qubo_energy": self.exact_qubo_energy,
            "exact_qubo_objective": self.exact_qubo_objective,
            "approximation_ratio": self.approximation_ratio,
            "approximation_ratio_status": self.approximation_ratio_status,
            "expectation_energy": self.expectation_energy,
            "statevector_norm": self.statevector_norm,
            "measurement_distribution": [dict(entry) for entry in self.measurement_distribution],
            "parameters": dict(self.parameters) if self.parameters is not None else None,
            "parameter_trials": self.parameter_trials,
            "runtime_backend": self.runtime_backend,
            "suitability_status": self.suitability_status,
        }


class AssignmentQAOASolver:
    """Run QAOA only for a validated F9.3 formulation and matching matrix."""

    def __init__(
        self,
        *,
        allow_test_mode: bool = False,
        qaoa_engine: QAOAEngine | None = None,
    ) -> None:
        self.allow_test_mode = allow_test_mode
        self.qaoa_engine = qaoa_engine or QAOAEngine()

    def solve(
        self,
        formulation: AssignmentQuboIsing | None,
        matrix: PredictionMatrix | None,
        config: QAOAConfig | None = None,
    ) -> AssignmentQAOAResult:
        mode = getattr(formulation, "mode", "PRODUCTION")
        if formulation is None or matrix is None:
            return AssignmentQAOAResult(
                status="NOT_READY",
                mode="PRODUCTION",
                reason="validated production QUBO/Ising formulation and prediction matrix are unavailable",
            )
        if not isinstance(formulation, AssignmentQuboIsing) or not isinstance(matrix, PredictionMatrix):
            return self._invalid(mode, "expected F9.3 AssignmentQuboIsing and F9.2 PredictionMatrix inputs")
        if matrix.mode in {"TEST/SYNTHETIC", "DEVELOPMENT/DEMO"} and not self.allow_test_mode:
            return AssignmentQAOAResult(
                status="NOT_READY",
                mode=matrix.mode,
                reason=f"{matrix.mode} execution requires explicit non-production opt-in",
            )
        if matrix.mode not in {"PRODUCTION", "TEST/SYNTHETIC", "DEVELOPMENT/DEMO"}:
            return self._invalid(matrix.mode, "unsupported matrix mode")
        if formulation.mode != matrix.mode:
            return self._invalid(matrix.mode, "formulation and matrix provenance modes differ")

        config = config or QAOAConfig()
        if not isinstance(config, QAOAConfig):
            return self._invalid(matrix.mode, "config must be a validated QAOAConfig")
        if config.depth > MAX_QAOA_DEPTH:
            return AssignmentQAOAResult(
                status="NOT_SUPPORTED",
                mode=matrix.mode,
                reason=f"QAOA depth {config.depth} exceeds local limit {MAX_QAOA_DEPTH}",
            )
        if config.max_iterations > MAX_PARAMETER_TRIALS:
            return AssignmentQAOAResult(
                status="NOT_SUPPORTED",
                mode=matrix.mode,
                reason=f"parameter iterations {config.max_iterations} exceed local limit {MAX_PARAMETER_TRIALS}",
            )
        if config.shots > MAX_LOCAL_SHOTS:
            return AssignmentQAOAResult(
                status="NOT_SUPPORTED",
                mode=matrix.mode,
                reason=f"shot count {config.shots} exceeds local limit {MAX_LOCAL_SHOTS}",
            )
        variable_count = len(formulation.ising.variables)
        if variable_count > MAX_LOCAL_QUBITS or variable_count > config.max_qubits:
            return AssignmentQAOAResult(
                status="TOO_LARGE",
                mode=matrix.mode,
                reason=(
                    f"problem has {variable_count} variables; configured limit is "
                    f"{min(config.max_qubits, MAX_LOCAL_QUBITS)} local qubits"
                ),
            )

        try:
            validated = AssignmentQuboIsingBuilder(
                allow_test_matrices=self.allow_test_mode,
            ).build(matrix)
            if validated.qubo.to_dict() != formulation.qubo.to_dict() or validated.ising.to_dict() != formulation.ising.to_dict():
                return self._invalid(matrix.mode, "QUBO/Ising formulation does not match the validated F9.2 matrix")
            if tuple(validated.variable_mapping) != tuple(formulation.variable_mapping):
                return self._invalid(matrix.mode, "task/hour variable mapping is invalid")

            classical = ClassicalOptimizer(allow_test_matrices=self.allow_test_mode).optimize(matrix)
            suitability = QuantumSuitabilityAnalyzer().assess(
                matrix,
                classical,
                formulation,
                config=config,
                allow_test_mode=self.allow_test_mode,
            )
            test_algorithm_only = (
                self.allow_test_mode
                and matrix.mode in {"TEST/SYNTHETIC", "DEVELOPMENT/DEMO"}
                and suitability.status == "NOT_SUITABLE"
                and suitability.reasons == ("assignment nontriviality has not been demonstrated",)
            )
            if suitability.status != "SUITABLE" and not test_algorithm_only:
                return AssignmentQAOAResult(
                    status=suitability.status,
                    mode=matrix.mode,
                    reason="; ".join(suitability.reasons),
                    suitability_status=suitability.status,
                )
            exact = ExactClassicalSolver(max_variables=MAX_LOCAL_QUBITS).solve(formulation.qubo)
            exact_assignment = exact.assignments
            exact_objective, exact_feasible, _ = self._decode_and_evaluate(
                formulation, matrix, exact_assignment
            )
            if not exact_feasible or not math.isclose(
                exact_objective, classical.total_objective, rel_tol=0.0, abs_tol=_TOLERANCE
            ):
                return self._invalid(matrix.mode, "exact QUBO optimum does not match the validated classical objective")

            # Existing engine uses bit b -> s=2b-1. F9.3 defines x=(1-z)/2,
            # so z=1-2b=-s. Flip only the linear fields to preserve the exact
            # source Ising energy while retaining the simulator's established
            # circuit/evaluator convention. This is a basis convention adapter,
            # not a new optimization formulation.
            engine_ising = _to_qaoa_bit_convention(formulation.ising)
            qaoa = self.qaoa_engine.solve(engine_ising, config)
            raw_assignment = dict(qaoa.best_solution.assignments)
            objective, feasible, violations = self._decode_and_evaluate(formulation, matrix, raw_assignment)
            qubo_energy = evaluate_qubo(formulation.qubo, raw_assignment)
            source_spins = {variable: 1 - (2 * value) for variable, value in raw_assignment.items()}
            ising_energy = evaluate_ising(formulation.ising, source_spins)
            if not math.isclose(qubo_energy, ising_energy, rel_tol=0.0, abs_tol=_TOLERANCE):
                return self._invalid(matrix.mode, "measured candidate QUBO and source Ising energies disagree")
            if not math.isclose(qubo_energy, qaoa.best_solution.objective_value, rel_tol=0.0, abs_tol=_TOLERANCE):
                return self._invalid(matrix.mode, "simulator candidate energy does not match the F9.3 QUBO energy")

            bitstring = "".join(str(raw_assignment[variable]) for variable in formulation.ising.variables)
            decoded = [
                {"task_id": task, "candidate_hour": hour}
                for variable, task, hour in formulation.variable_mapping
                if raw_assignment[variable] == 1
            ]
            ratio, ratio_status = _approximation_ratio(objective, classical.total_objective, feasible)
            distribution = tuple(
                {
                    "bitstring": solution.metadata["bitstring"],
                    "count": solution.metadata["count"],
                    "probability": solution.metadata["count"] / config.shots,
                    "energy": solution.energy,
                }
                for solution in qaoa.ranked_candidates
            )
            trials = len(DeterministicQAOAParameterOptimizer().candidate_parameters(config))
            return AssignmentQAOAResult(
                status="CANDIDATE",
                mode=matrix.mode,
                candidate={
                    "bitstring": bitstring,
                    "assignments": decoded,
                    "objective_value": objective,
                    "qubo_energy": qubo_energy,
                    "ising_energy": ising_energy,
                    "feasible": feasible,
                    "constraint_violations": list(violations),
                    "repaired": False,
                    "solver_name": "qaoa_local_statevector",
                },
                classical_objective=classical.total_objective,
                exact_qubo_energy=exact.objective_value,
                exact_qubo_objective=exact_objective,
                approximation_ratio=ratio,
                approximation_ratio_status=ratio_status,
                expectation_energy=qaoa.expectation_value,
                statevector_norm=float(qaoa.metadata["statevector_norm"]),
                measurement_distribution=distribution,
                parameters={
                    **qaoa.parameters.to_dict(),
                    "depth": qaoa.parameters.depth,
                    "shots": config.shots,
                    "seed": config.seed,
                    "optimize_parameters": config.optimize_parameters,
                    "iterations_requested": config.max_iterations,
                },
                parameter_trials=trials,
                runtime_backend="local_statevector_simulator",
                suitability_status=("TEST_ALGORITHM_ONLY" if test_algorithm_only else suitability.status),
            )
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            return self._invalid(matrix.mode, f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _decode_and_evaluate(
        formulation: AssignmentQuboIsing,
        matrix: PredictionMatrix,
        assignment: dict[str, int],
    ) -> tuple[float, bool, tuple[str, ...]]:
        expected = {variable for variable, _, _ in formulation.variable_mapping}
        if set(assignment) != expected:
            raise ValueError("candidate assignment does not match the F9.3 variable mapping")
        selected = [
            (task, hour)
            for variable, task, hour in formulation.variable_mapping
            if assignment[variable] == 1
        ]
        violations: list[str] = []
        for task in matrix.task_ids:
            count = sum(candidate_task == task for candidate_task, _ in selected)
            if count != 1:
                violations.append(f"task {task!r} assigned {count} times (expected exactly once)")
        for hour in matrix.candidate_hours:
            count = sum(candidate_hour == hour for _, candidate_hour in selected)
            if count > 1:
                violations.append(f"hour {hour} assigned {count} tasks (capacity is one)")
        objective = math.fsum(matrix.score(task, hour) for task, hour in selected)
        return objective, not violations, tuple(violations)

    @staticmethod
    def _invalid(mode: str, reason: str) -> AssignmentQAOAResult:
        return AssignmentQAOAResult(status="INVALID_INPUT", mode=mode, reason=reason)


def _to_qaoa_bit_convention(problem: IsingProblem) -> IsingProblem:
    if not isinstance(problem, IsingProblem):
        raise ValueError("F9.3 QAOA input must be an IsingProblem")
    return IsingProblem(
        problem_id=f"{problem.problem_id}_qaoa_basis",
        name=f"{problem.name} QAOA bit convention",
        variables=problem.variables,
        linear_coefficients={key: -value for key, value in problem.linear_coefficients.items()},
        quadratic_coefficients=dict(problem.quadratic_coefficients),
        constant_offset=problem.constant_offset,
        objective=problem.objective,
        metadata={
            **dict(problem.metadata),
            "source_problem_id": problem.problem_id,
            "basis_adapter": "z=1-2x; existing QAOA engine evaluates s=2x-1=-z",
            "source_ising_preserved": True,
        },
    )


def _approximation_ratio(candidate: float, optimum: float, feasible: bool) -> tuple[float | None, str]:
    if not feasible:
        return None, "INFEASIBLE_CANDIDATE"
    if candidate < 0:
        return None, "NEGATIVE_OBJECTIVE"
    if optimum == 0:
        return None, "ZERO_CLASSICAL_OPTIMUM"
    if optimum < 0:
        return None, "NEGATIVE_CLASSICAL_OPTIMUM"
    return candidate / optimum, "DEFINED"
