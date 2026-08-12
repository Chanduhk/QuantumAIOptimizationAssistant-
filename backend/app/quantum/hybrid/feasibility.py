from __future__ import annotations

from typing import Mapping

from backend.app.quantum.domain import ConstraintSense, IsingProblem, QUBOProblem

FEASIBILITY_TOLERANCE = 1e-9


class HybridFeasibilityChecker:
    """Validate candidate assignments against problem variables and constraints."""

    def validate_assignment(self, problem: QUBOProblem | IsingProblem, assignment: Mapping[str, int]) -> bool:
        """Return whether a candidate assignment is domain-valid and constraint-feasible."""

        variable_ids = self.variable_order(problem)
        if set(assignment) != set(variable_ids):
            return False
        for variable_id in variable_ids:
            value = assignment.get(variable_id)
            if isinstance(value, bool) or value not in (0, 1):
                return False
        if isinstance(problem, QUBOProblem):
            return self._qubo_constraints_satisfied(problem, assignment)
        return True

    def variable_order(self, problem: QUBOProblem | IsingProblem) -> tuple[str, ...]:
        """Return deterministic problem variable order."""

        if isinstance(problem, QUBOProblem):
            return tuple(variable.variable_id for variable in problem.variables)
        if isinstance(problem, IsingProblem):
            return tuple(problem.variables)
        raise ValueError("problem must be a QUBOProblem or IsingProblem.")

    @staticmethod
    def _qubo_constraints_satisfied(problem: QUBOProblem, assignment: Mapping[str, int]) -> bool:
        for constraint in problem.constraints:
            lhs = sum(constraint.coefficients[variable_id] * assignment[variable_id] for variable_id in constraint.coefficients)
            if constraint.sense is ConstraintSense.EQ and abs(lhs - constraint.rhs) > FEASIBILITY_TOLERANCE:
                return False
            if constraint.sense is ConstraintSense.LE and lhs > constraint.rhs + FEASIBILITY_TOLERANCE:
                return False
            if constraint.sense is ConstraintSense.GE and lhs < constraint.rhs - FEASIBILITY_TOLERANCE:
                return False
        return True
