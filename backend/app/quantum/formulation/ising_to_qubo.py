from __future__ import annotations

from backend.app.quantum.domain import IsingProblem, QUBOProblem, QuantumVariable
from backend.app.quantum.domain.quantum_objective import _validate_identifier, _validate_name


class IsingToQUBOConverter:
    """Convert E.1 Ising coefficients to canonical QUBO coefficients.

    Uses s_i = 2x_i - 1. For h_i s_i, linear_i += 2h_i and
    offset -= h_i. For J_ij s_i s_j, quadratic_ij += 4J_ij,
    linear_i -= 2J_ij, linear_j -= 2J_ij, and offset += J_ij.
    """

    def convert(self, problem: IsingProblem, *, problem_id: str | None = None, name: str | None = None) -> QUBOProblem:
        """Return a mathematically equivalent QUBOProblem."""

        if not isinstance(problem, IsingProblem):
            raise ValueError("problem must be an IsingProblem.")
        qubo_id = _validate_identifier(problem_id or f"{problem.problem_id}_qubo", "problem_id")
        qubo_name = _validate_name(name or f"{problem.name} QUBO", "name")
        variables = tuple(
            QuantumVariable(variable_id=variable_id, name=f"Binary {variable_id}", index=index)
            for index, variable_id in enumerate(problem.variables)
        )
        linear = {variable.variable_id: 0.0 for variable in variables}
        quadratic: dict[tuple[str, str], float] = {}
        offset = float(problem.constant_offset)

        for variable_id in sorted(problem.linear_coefficients):
            coefficient = problem.linear_coefficients[variable_id]
            linear[variable_id] += 2.0 * coefficient
            offset -= coefficient

        for pair in sorted(problem.quadratic_coefficients):
            left, right = pair
            coefficient = problem.quadratic_coefficients[pair]
            quadratic[pair] = quadratic.get(pair, 0.0) + 4.0 * coefficient
            linear[left] -= 2.0 * coefficient
            linear[right] -= 2.0 * coefficient
            offset += coefficient

        metadata = {
            "source_problem_id": problem.problem_id,
            "source_problem_type": "Ising",
            "transformation": "s_i=2x_i-1",
            "variable_mapping": tuple((variable_id, variable_id) for variable_id in problem.variables),
            "original_objective_sense": problem.objective.sense.value,
        }
        return QUBOProblem(
            problem_id=qubo_id,
            name=qubo_name,
            variables=variables,
            linear_coefficients={key: value for key, value in sorted(linear.items()) if value != 0.0},
            quadratic_coefficients={key: value for key, value in sorted(quadratic.items()) if value != 0.0},
            constant_offset=offset,
            objective=problem.objective,
            metadata=metadata,
        )
