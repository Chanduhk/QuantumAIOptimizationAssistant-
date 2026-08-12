from __future__ import annotations

from typing import Mapping

from backend.app.quantum.domain import IsingProblem, QUBOProblem
from backend.app.quantum.domain.quantum_objective import _validate_identifier, _validate_name


class QUBOToIsingConverter:
    """Convert E.1 canonical QUBO coefficients to Ising coefficients.

    Uses x_i = (1 + s_i) / 2. For QUBO term a_i x_i, h_i += a_i/2
    and offset += a_i/2. For b_ij x_i x_j, J_ij += b_ij/4,
    h_i += b_ij/4, h_j += b_ij/4, and offset += b_ij/4.
    """

    def convert(self, problem: QUBOProblem, *, problem_id: str | None = None, name: str | None = None) -> IsingProblem:
        """Return a mathematically equivalent IsingProblem."""

        if not isinstance(problem, QUBOProblem):
            raise ValueError("problem must be a QUBOProblem.")
        ising_id = _validate_identifier(problem_id or f"{problem.problem_id}_ising", "problem_id")
        ising_name = _validate_name(name or f"{problem.name} Ising", "name")
        variables = tuple(variable.variable_id for variable in problem.variables)
        h = {variable_id: 0.0 for variable_id in variables}
        j: dict[tuple[str, str], float] = {}
        offset = float(problem.constant_offset)

        for variable_id in sorted(problem.linear_coefficients):
            coefficient = problem.linear_coefficients[variable_id]
            h[variable_id] += coefficient / 2.0
            offset += coefficient / 2.0

        for pair in sorted(problem.quadratic_coefficients):
            left, right = pair
            coefficient = problem.quadratic_coefficients[pair]
            h[left] += coefficient / 4.0
            h[right] += coefficient / 4.0
            j[pair] = j.get(pair, 0.0) + coefficient / 4.0
            offset += coefficient / 4.0

        metadata = {
            "source_problem_id": problem.problem_id,
            "source_problem_type": "QUBO",
            "transformation": "x_i=(1+s_i)/2",
            "variable_mapping": tuple((variable.variable_id, variable.variable_id) for variable in problem.variables),
            "original_objective_sense": problem.objective.sense.value,
        }
        return IsingProblem(
            problem_id=ising_id,
            name=ising_name,
            variables=variables,
            linear_coefficients={key: value for key, value in sorted(h.items()) if value != 0.0},
            quadratic_coefficients={key: value for key, value in sorted(j.items()) if value != 0.0},
            constant_offset=offset,
            objective=problem.objective,
            metadata=metadata,
        )

    @staticmethod
    def evaluate_qubo_energy(problem: QUBOProblem, assignment: Mapping[str, int]) -> float:
        """Evaluate a QUBO energy for validation; this is not a solver."""

        if not isinstance(problem, QUBOProblem):
            raise ValueError("problem must be a QUBOProblem.")
        energy = float(problem.constant_offset)
        for variable_id in sorted(problem.linear_coefficients):
            value = QUBOToIsingConverter._binary_value(assignment, variable_id)
            energy += problem.linear_coefficients[variable_id] * value
        for left, right in sorted(problem.quadratic_coefficients):
            energy += (
                problem.quadratic_coefficients[(left, right)]
                * QUBOToIsingConverter._binary_value(assignment, left)
                * QUBOToIsingConverter._binary_value(assignment, right)
            )
        return energy

    @staticmethod
    def evaluate_ising_energy(problem: IsingProblem, spins: Mapping[str, int]) -> float:
        """Evaluate an Ising energy for validation; this is not a solver."""

        if not isinstance(problem, IsingProblem):
            raise ValueError("problem must be an IsingProblem.")
        energy = float(problem.constant_offset)
        for variable_id in sorted(problem.linear_coefficients):
            energy += problem.linear_coefficients[variable_id] * QUBOToIsingConverter._spin_value(spins, variable_id)
        for left, right in sorted(problem.quadratic_coefficients):
            energy += (
                problem.quadratic_coefficients[(left, right)]
                * QUBOToIsingConverter._spin_value(spins, left)
                * QUBOToIsingConverter._spin_value(spins, right)
            )
        return energy

    @staticmethod
    def _binary_value(assignment: Mapping[str, int], variable_id: str) -> int:
        value = assignment.get(variable_id)
        if value not in (0, 1) or isinstance(value, bool):
            raise ValueError(f"assignment for '{variable_id}' must be 0 or 1.")
        return int(value)

    @staticmethod
    def _spin_value(spins: Mapping[str, int], variable_id: str) -> int:
        value = spins.get(variable_id)
        if value not in (-1, 1) or isinstance(value, bool):
            raise ValueError(f"spin assignment for '{variable_id}' must be -1 or +1.")
        return int(value)
