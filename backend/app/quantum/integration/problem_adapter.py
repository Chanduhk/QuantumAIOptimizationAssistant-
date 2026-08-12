from __future__ import annotations

from typing import Any, Mapping

from backend.app.quantum.domain import IsingProblem, QUBOProblem, QuantumConstraint, QuantumObjective, QuantumVariable
from backend.app.quantum.formulation import QUBOFormulator
from backend.app.quantum.integration.models import AIOptimizationProblem, AIOptimizationVariable


class AIQuantumProblemAdapter:
    """Adapt supported AI optimization contracts into E.1/E.2 quantum problems."""

    def __init__(self, formulator: QUBOFormulator | None = None) -> None:
        self.formulator = formulator or QUBOFormulator()

    def adapt(self, problem: AIOptimizationProblem | QUBOProblem | IsingProblem | Mapping[str, Any]) -> QUBOProblem | IsingProblem:
        """Return a QUBOProblem or IsingProblem without mutating the caller input."""

        if isinstance(problem, (QUBOProblem, IsingProblem)):
            return problem
        ai_problem = problem if isinstance(problem, AIOptimizationProblem) else self.from_mapping(problem)
        variables = tuple(
            QuantumVariable(
                variable.variable_id,
                variable.name,
                variable.index,
                metadata={"source_domain": variable.domain, **dict(variable.metadata)},
            )
            for variable in ai_problem.variables
        )
        constraints = tuple(self._constraint_from_mapping(constraint) for constraint in ai_problem.constraints)
        return self.formulator.formulate(
            problem_id=ai_problem.problem_id,
            name=ai_problem.name,
            variables=variables,
            linear_coefficients=ai_problem.linear_coefficients,
            quadratic_coefficients=ai_problem.quadratic_coefficients,
            constant_offset=ai_problem.constant_offset,
            objective=QuantumObjective(
                "objective_" + ai_problem.problem_id,
                f"{ai_problem.name} Objective",
                ai_problem.objective_sense,
                metadata={"source": "ai_quantum_integration"},
            ),
            constraints=constraints,
            penalty=ai_problem.penalty,
            metadata={
                "source": "ai_quantum_integration",
                "source_problem_id": ai_problem.problem_id,
                **dict(ai_problem.metadata),
            },
        )

    def from_mapping(self, data: Mapping[str, Any]) -> AIOptimizationProblem:
        """Create an AIOptimizationProblem from a mapping using strict validation."""

        if not isinstance(data, Mapping):
            raise ValueError("AI optimization problem must be a mapping or supported quantum problem.")
        quadratic_entries = data.get("quadratic_coefficients", {})
        quadratic = self._quadratic_from_data(quadratic_entries)
        return AIOptimizationProblem(
            problem_id=data.get("problem_id"),
            name=data.get("name"),
            variables=tuple(self._variable_from_mapping(item) for item in data.get("variables", ())),
            linear_coefficients=data.get("linear_coefficients", {}),
            quadratic_coefficients=quadratic,
            constant_offset=data.get("constant_offset", 0.0),
            objective_sense=data.get("objective_sense", "MINIMIZE"),
            constraints=tuple(data.get("constraints", ())),
            penalty=data.get("penalty"),
            metadata=data.get("metadata", {}),
        )

    @staticmethod
    def _variable_from_mapping(data: Mapping[str, Any]) -> AIOptimizationVariable:
        if not isinstance(data, Mapping):
            raise ValueError("variables must contain mappings.")
        return AIOptimizationVariable(
            variable_id=data.get("variable_id"),
            name=data.get("name"),
            index=data.get("index"),
            domain=data.get("domain", "binary"),
            metadata=data.get("metadata", {}),
        )

    @staticmethod
    def _constraint_from_mapping(data: Mapping[str, Any]) -> QuantumConstraint:
        if not isinstance(data, Mapping):
            raise ValueError("constraints must contain mappings.")
        return QuantumConstraint(
            constraint_id=data.get("constraint_id"),
            name=data.get("name"),
            sense=data.get("sense"),
            rhs=data.get("rhs"),
            coefficients=data.get("coefficients", {}),
            metadata=data.get("metadata", {}),
        )

    @staticmethod
    def _quadratic_from_data(data: object) -> Mapping[tuple[str, str], float]:
        if isinstance(data, Mapping):
            return data  # type: ignore[return-value]
        if not isinstance(data, (list, tuple)):
            raise ValueError("quadratic_coefficients must be a mapping or sequence.")
        quadratic: dict[tuple[str, str], float] = {}
        for entry in data:
            if not isinstance(entry, Mapping):
                raise ValueError("quadratic coefficient entries must be mappings.")
            variables = entry.get("variables")
            if not isinstance(variables, (list, tuple)) or len(variables) != 2:
                raise ValueError("quadratic coefficient variables must contain two IDs.")
            quadratic[(variables[0], variables[1])] = entry.get("coefficient")
        return quadratic
