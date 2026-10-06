"""Compare classical and QAOA candidates against the same F9.2 objective."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from backend.app.domain.assignment_qubo_ising import AssignmentQuboIsing, evaluate_ising, evaluate_qubo
from backend.app.domain.prediction_matrix import (
    PredictionMatrix,
    validate_development_demo_matrix,
    validate_prediction_matrix,
    validate_synthetic_test_matrix,
)


@dataclass(frozen=True)
class HybridComparisonResult:
    status: str
    mode: str
    objective_relation: str
    classical: dict[str, Any] | None
    quantum: dict[str, Any] | None
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "objective_relation": self.objective_relation,
            "classical": dict(self.classical) if self.classical is not None else None,
            "quantum": dict(self.quantum) if self.quantum is not None else None,
            "reasons": list(self.reasons),
            "objective_source": "F9.2 PredictionMatrix; maximize sum P[t,h]",
            "quantum_preferred_automatically": False,
        }


class HybridComparator:
    """Re-evaluate raw candidates without repairing them or choosing a winner."""

    def compare(
        self,
        matrix: PredictionMatrix | None,
        classical_candidate: Any,
        quantum_candidate: Any,
        *,
        formulation: AssignmentQuboIsing | None = None,
        allow_test_mode: bool = False,
    ) -> HybridComparisonResult:
        mode = getattr(matrix, "mode", "PRODUCTION")
        if matrix is None:
            return self._not_ready(mode, "validated prediction matrix is unavailable")
        if not isinstance(matrix, PredictionMatrix):
            return self._invalid(mode, "unsupported prediction matrix type")
        if mode in {"TEST/SYNTHETIC", "DEVELOPMENT/DEMO"} and not allow_test_mode:
            return self._not_ready(mode, f"{mode} comparison requires explicit non-production opt-in")
        if classical_candidate is None or quantum_candidate is None:
            return self._not_ready(mode, "both classical and quantum candidates are required for comparison")
        if not isinstance(classical_candidate, dict) and callable(getattr(classical_candidate, "to_dict", None)):
            classical_candidate = classical_candidate.to_dict()
        if not isinstance(quantum_candidate, dict) and callable(getattr(quantum_candidate, "to_dict", None)):
            quantum_candidate = quantum_candidate.to_dict()
        if not isinstance(classical_candidate, dict) or not isinstance(quantum_candidate, dict):
            return self._invalid(mode, "candidate records must be structured mappings")
        try:
            validated = (
                validate_synthetic_test_matrix(matrix.cells, matrix.task_ids, matrix.candidate_hours)
                if mode == "TEST/SYNTHETIC"
                else validate_development_demo_matrix(matrix.cells, matrix.task_ids, matrix.candidate_hours)
                if mode == "DEVELOPMENT/DEMO"
                else validate_prediction_matrix(matrix.cells, matrix.task_ids, matrix.candidate_hours)
            )
            if (validated.nontriviality, validated.assignment_contrast) != (matrix.nontriviality, matrix.assignment_contrast):
                raise ValueError("matrix derived fields do not match validation")
            if formulation is not None and formulation.mode != mode:
                raise ValueError("formulation provenance does not match matrix mode")
            classical = self._evaluate_candidate("classical", classical_candidate, matrix, formulation)
            quantum = self._evaluate_candidate("quantum", quantum_candidate, matrix, formulation)
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
            return self._invalid(mode, f"candidate or matrix validation failed: {exc}")

        if classical["feasibility"] != "FEASIBLE" or quantum["feasibility"] != "FEASIBLE":
            return HybridComparisonResult(
                "INFEASIBLE_CANDIDATE", mode, "NOT_COMPARABLE", classical, quantum,
                ("raw candidate constraint violations are reported; no repair or fallback was applied",),
            )
        left, right = classical["objective_value"], quantum["objective_value"]
        relation = "EQUAL" if math.isclose(left, right, rel_tol=0.0, abs_tol=1e-9) else (
            "CLASSICAL_HIGHER" if left > right else "QUANTUM_HIGHER"
        )
        return HybridComparisonResult(
            "COMPARED", mode, relation, classical, quantum,
            ("both candidates were independently evaluated using the same F9.2 objective", "comparison supplies evidence; it does not select the executive recommendation"),
        )

    @staticmethod
    def _evaluate_candidate(identity: str, data: dict[str, Any], matrix: PredictionMatrix, formulation: AssignmentQuboIsing | None) -> dict[str, Any]:
        if data.get("mode", matrix.mode) != matrix.mode:
            raise ValueError(f"{identity} candidate provenance mode mismatch")
        if identity == "classical":
            if data.get("status") not in {None, "CANDIDATE"}:
                raise ValueError("classical candidate is not a candidate")
            entries = data.get("assignments")
            hour_key = "assigned_hour"
            claimed_objective = data.get("total_objective")
            claimed_feasible = data.get("feasibility")
            violations_claimed = data.get("constraint_violations", [])
            solver = data.get("solver")
            runtime = data.get("runtime_seconds")
            provenance = data.get("input_provenance")
        else:
            if data.get("status") != "CANDIDATE":
                raise ValueError(f"quantum candidate status is {data.get('status')!r}")
            inner = data.get("candidate")
            if not isinstance(inner, dict) or inner.get("repaired") is not False:
                raise ValueError("quantum candidate is missing or marked repaired")
            entries = inner.get("assignments")
            hour_key = "candidate_hour"
            claimed_objective = inner.get("objective_value")
            claimed_feasible = inner.get("feasible")
            violations_claimed = inner.get("constraint_violations", [])
            solver = inner.get("solver_name")
            runtime = data.get("runtime_seconds")  # only report an actual measured value
            provenance = {"mode": data.get("mode"), "runtime_backend": data.get("runtime_backend"), "parameters": data.get("parameters")}
        if not isinstance(entries, (list, tuple)) or not entries:
            raise ValueError(f"{identity} assignments are missing")
        pairs: list[tuple[Any, int]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"{identity} assignment entries must be mappings")
            task_id, hour = entry.get("task_id"), entry.get(hour_key)
            if isinstance(hour, bool) or not isinstance(hour, int):
                raise ValueError(f"{identity} candidate hour is invalid")
            pairs.append((task_id, hour))
        selected_tasks = [task for task, _ in pairs]
        selected_hours = [hour for _, hour in pairs]
        violations: list[str] = []
        if len(set(pairs)) != len(pairs):
            violations.append("candidate contains duplicate task/hour assignment entries")
        if len(pairs) != len(matrix.task_ids) or set(selected_tasks) != set(matrix.task_ids):
            violations.append("each task must be assigned exactly once")
        if len(set(selected_hours)) != len(selected_hours):
            violations.append("each candidate hour may receive at most one task")
        if any(hour not in matrix.candidate_hours for hour in selected_hours):
            violations.append("assigned hour is outside the candidate domain")
        if any(task not in matrix.task_ids for task in selected_tasks):
            violations.append("assignment contains an unknown task")
        objective = math.fsum(matrix.score(task, hour) for task, hour in pairs if task in matrix.task_ids and hour in matrix.candidate_hours)
        if isinstance(claimed_objective, bool) or not isinstance(claimed_objective, (int, float)) or not math.isfinite(float(claimed_objective)):
            raise ValueError(f"{identity} claimed objective is invalid")
        if not math.isclose(float(claimed_objective), objective, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(f"{identity} claimed objective does not match F9.2 reevaluation")
        feasible = not violations
        if (
            claimed_feasible is not feasible
            or not isinstance(violations_claimed, (list, tuple))
            or any(not isinstance(item, str) for item in violations_claimed)
            or (feasible and violations_claimed)
            or (not feasible and not violations_claimed)
        ):
            raise ValueError(f"{identity} claimed feasibility/violations do not match independent validation")
        qubo_energy = ising_energy = None
        if formulation is not None:
            selected = set(pairs)
            bits = {variable: int((task, hour) in selected) for variable, task, hour in formulation.variable_mapping}
            qubo_energy = evaluate_qubo(formulation.qubo, bits)
            spins = {variable: 1 - 2 * bit for variable, bit in bits.items()}
            ising_energy = evaluate_ising(formulation.ising, spins)
            if not math.isclose(qubo_energy, ising_energy, rel_tol=0.0, abs_tol=1e-8):
                raise ValueError("F9.3 QUBO and Ising energies disagree")
        if identity == "quantum" and isinstance(inner, dict):
            for key, computed in (("qubo_energy", qubo_energy), ("ising_energy", ising_energy)):
                supplied = inner.get(key)
                if supplied is not None and computed is not None and not math.isclose(float(supplied), computed, rel_tol=0.0, abs_tol=1e-8):
                    raise ValueError(f"quantum {key} does not match F9.3 formulation")
        if runtime is not None and (isinstance(runtime, bool) or not isinstance(runtime, (int, float)) or not math.isfinite(float(runtime)) or runtime < 0):
            raise ValueError(f"{identity} measured runtime is invalid")
        return {
            "identity": identity,
            "objective_value": objective,
            "feasibility": "FEASIBLE" if feasible else "INFEASIBLE",
            "constraint_violations": violations,
            "solver_reported_constraint_violations": list(violations_claimed),
            "qubo_energy": qubo_energy if qubo_energy is not None else (inner.get("qubo_energy") if identity == "quantum" else None),
            "ising_energy": ising_energy if ising_energy is not None else (inner.get("ising_energy") if identity == "quantum" else None),
            "runtime_seconds": float(runtime) if runtime is not None else None,
            "solver": solver,
            "provenance": provenance,
        }

    @staticmethod
    def _not_ready(mode: str, reason: str) -> HybridComparisonResult:
        return HybridComparisonResult("NOT_READY", mode, "NOT_COMPARABLE", None, None, (reason,))

    @staticmethod
    def _invalid(mode: str, reason: str) -> HybridComparisonResult:
        return HybridComparisonResult("INVALID_INPUT", mode, "NOT_COMPARABLE", None, None, (reason,))
