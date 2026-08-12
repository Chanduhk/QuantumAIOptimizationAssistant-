from __future__ import annotations

import itertools
from typing import Mapping

from backend.app.quantum.domain import IsingProblem, ObjectiveSense, QUBOProblem, QuantumSolution
from backend.app.quantum.domain.quantum_objective import _validate_non_negative_int

DEFAULT_MAX_VARIABLES = 20
DEFAULT_MAX_STATES = 1_048_576
ENERGY_TOLERANCE = 1e-12


class ExactClassicalSolver:
    """Deterministic exhaustive classical reference solver.

    The solver enumerates every state lazily and returns the exact best state
    under the problem's comparison semantics. Time complexity is O(2^N times
    evaluation cost); working memory is O(N), excluding input model storage.
    """

    def __init__(self, *, max_variables: int = DEFAULT_MAX_VARIABLES, max_states: int = DEFAULT_MAX_STATES) -> None:
        self.max_variables = self._positive_int(max_variables, "max_variables")
        self.max_states = self._positive_int(max_states, "max_states")

    def solve(self, problem: QUBOProblem | IsingProblem) -> QuantumSolution:
        """Solve a supported E.1 QUBOProblem or IsingProblem exactly."""

        if isinstance(problem, QUBOProblem):
            return self.solve_qubo(problem)
        if isinstance(problem, IsingProblem):
            return self.solve_ising(problem)
        raise ValueError("problem must be a QUBOProblem or IsingProblem.")

    def solve_qubo(self, problem: QUBOProblem) -> QuantumSolution:
        """Enumerate every binary assignment and return the exact QUBO optimum."""

        if not isinstance(problem, QUBOProblem):
            raise ValueError("problem must be a QUBOProblem.")
        variable_ids = tuple(variable.variable_id for variable in problem.variables)
        self._validate_size(len(variable_ids))
        comparison = self._comparison_mode(problem)
        best_assignment: dict[str, int] | None = None
        best_energy: float | None = None
        evaluated_states = 0

        for values in itertools.product((0, 1), repeat=len(variable_ids)):
            assignment = dict(zip(variable_ids, values))
            energy = self.evaluate_qubo_energy(problem, assignment)
            evaluated_states += 1
            if self._is_better(energy, assignment, best_energy, best_assignment, comparison, variable_ids):
                best_energy = energy
                best_assignment = assignment

        if best_assignment is None or best_energy is None:
            raise ValueError("no assignments were evaluated.")
        return self._solution(
            problem_id=problem.problem_id,
            assignments=best_assignment,
            objective_value=best_energy,
            representation="QUBO",
            objective_sense=problem.objective.sense.value,
            comparison_mode=comparison,
            variable_count=len(variable_ids),
            evaluated_states=evaluated_states,
        )

    def solve_ising(self, problem: IsingProblem) -> QuantumSolution:
        """Enumerate every spin state and return the exact Ising optimum."""

        if not isinstance(problem, IsingProblem):
            raise ValueError("problem must be an IsingProblem.")
        variable_ids = tuple(problem.variables)
        self._validate_size(len(variable_ids))
        comparison = self._comparison_mode(problem)
        best_binary_assignment: dict[str, int] | None = None
        best_spin_assignment: dict[str, int] | None = None
        best_energy: float | None = None
        evaluated_states = 0

        for values in itertools.product((0, 1), repeat=len(variable_ids)):
            binary_assignment = dict(zip(variable_ids, values))
            spin_assignment = {variable_id: (2 * value) - 1 for variable_id, value in binary_assignment.items()}
            energy = self.evaluate_ising_energy(problem, spin_assignment)
            evaluated_states += 1
            if self._is_better(energy, binary_assignment, best_energy, best_binary_assignment, comparison, variable_ids):
                best_energy = energy
                best_binary_assignment = binary_assignment
                best_spin_assignment = spin_assignment

        if best_binary_assignment is None or best_spin_assignment is None or best_energy is None:
            raise ValueError("no spin states were evaluated.")
        solution = self._solution(
            problem_id=problem.problem_id,
            assignments=best_binary_assignment,
            objective_value=best_energy,
            representation="Ising",
            objective_sense=problem.objective.sense.value,
            comparison_mode=comparison,
            variable_count=len(variable_ids),
            evaluated_states=evaluated_states,
            extra_metadata={"spin_assignments": best_spin_assignment},
        )
        return solution

    def evaluate_qubo_energy(self, problem: QUBOProblem, assignment: Mapping[str, int]) -> float:
        """Evaluate QUBO energy for a complete binary assignment."""

        if not isinstance(problem, QUBOProblem):
            raise ValueError("problem must be a QUBOProblem.")
        if not isinstance(assignment, Mapping):
            raise ValueError("assignment must be a mapping.")
        energy = float(problem.constant_offset)
        for variable in problem.variables:
            self._binary_value(assignment, variable.variable_id)
        for variable_id in sorted(problem.linear_coefficients):
            energy += problem.linear_coefficients[variable_id] * self._binary_value(assignment, variable_id)
        for left, right in sorted(problem.quadratic_coefficients):
            energy += (
                problem.quadratic_coefficients[(left, right)]
                * self._binary_value(assignment, left)
                * self._binary_value(assignment, right)
            )
        return energy

    def evaluate_ising_energy(self, problem: IsingProblem, spins: Mapping[str, int]) -> float:
        """Evaluate Ising energy for a complete spin assignment."""

        if not isinstance(problem, IsingProblem):
            raise ValueError("problem must be an IsingProblem.")
        if not isinstance(spins, Mapping):
            raise ValueError("spins must be a mapping.")
        energy = float(problem.constant_offset)
        for variable_id in problem.variables:
            self._spin_value(spins, variable_id)
        for variable_id in sorted(problem.linear_coefficients):
            energy += problem.linear_coefficients[variable_id] * self._spin_value(spins, variable_id)
        for left, right in sorted(problem.quadratic_coefficients):
            energy += problem.quadratic_coefficients[(left, right)] * self._spin_value(spins, left) * self._spin_value(
                spins,
                right,
            )
        return energy

    def _validate_size(self, variable_count: int) -> None:
        if variable_count > self.max_variables:
            raise ValueError(
                f"exact enumeration refused: variable count {variable_count} exceeds limit {self.max_variables}."
            )
        state_count = 2 ** variable_count
        if state_count > self.max_states:
            raise ValueError(f"exact enumeration refused: state count {state_count} exceeds limit {self.max_states}.")

    @staticmethod
    def _comparison_mode(problem: QUBOProblem | IsingProblem) -> str:
        metadata = problem.metadata
        if metadata.get("objective_transformed_for_minimization") is True:
            return "MINIMIZE"
        if metadata.get("source_problem_type") == "QUBO":
            return "MINIMIZE"
        if problem.objective.sense is ObjectiveSense.MAXIMIZE:
            return "MAXIMIZE"
        return "MINIMIZE"

    @staticmethod
    def _is_better(
        energy: float,
        assignment: Mapping[str, int],
        best_energy: float | None,
        best_assignment: Mapping[str, int] | None,
        comparison: str,
        variable_order: tuple[str, ...],
    ) -> bool:
        if best_energy is None or best_assignment is None:
            return True
        if comparison == "MINIMIZE":
            if energy < best_energy - ENERGY_TOLERANCE:
                return True
            if energy > best_energy + ENERGY_TOLERANCE:
                return False
        else:
            if energy > best_energy + ENERGY_TOLERANCE:
                return True
            if energy < best_energy - ENERGY_TOLERANCE:
                return False
        return tuple(assignment[key] for key in variable_order) < tuple(best_assignment[key] for key in variable_order)

    @staticmethod
    def _binary_value(assignment: Mapping[str, int], variable_id: str) -> int:
        if variable_id not in assignment:
            raise ValueError(f"assignment is missing variable '{variable_id}'.")
        value = assignment[variable_id]
        if isinstance(value, bool) or value not in (0, 1):
            raise ValueError(f"assignment for '{variable_id}' must be 0 or 1.")
        return int(value)

    @staticmethod
    def _spin_value(spins: Mapping[str, int], variable_id: str) -> int:
        if variable_id not in spins:
            raise ValueError(f"spin assignment is missing variable '{variable_id}'.")
        value = spins[variable_id]
        if isinstance(value, bool) or value not in (-1, 1):
            raise ValueError(f"spin assignment for '{variable_id}' must be -1 or +1.")
        return int(value)

    @staticmethod
    def _solution(
        *,
        problem_id: str,
        assignments: Mapping[str, int],
        objective_value: float,
        representation: str,
        objective_sense: str,
        comparison_mode: str,
        variable_count: int,
        evaluated_states: int,
        extra_metadata: Mapping[str, object] | None = None,
    ) -> QuantumSolution:
        metadata: dict[str, object] = {
            "solver_name": "exact_classical",
            "method": "exhaustive_enumeration",
            "exact": True,
            "representation": representation,
            "objective_sense": objective_sense,
            "comparison_mode": comparison_mode,
            "variable_count": variable_count,
            "evaluated_states": evaluated_states,
            "tie_break_policy": "lexicographically_smallest_assignment_by_problem_variable_order",
        }
        if extra_metadata:
            metadata.update(dict(extra_metadata))
        return QuantumSolution(
            solution_id=f"exact_classical_{problem_id}",
            problem_id=problem_id,
            assignments=assignments,
            objective_value=objective_value,
            feasible=True,
            energy=objective_value,
            solver_name="exact_classical",
            execution_mode="exact_classical",
            metadata=metadata,
        )

    @staticmethod
    def _positive_int(value: object, field_name: str) -> int:
        parsed = _validate_non_negative_int(value, field_name)
        if parsed <= 0:
            raise ValueError(f"{field_name} must be positive.")
        return parsed
