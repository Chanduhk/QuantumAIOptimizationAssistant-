from __future__ import annotations

from backend.app.quantum.domain import IsingProblem
from backend.app.quantum.execution import QuantumCircuit, QuantumOperation
from backend.app.quantum.optimization.exceptions import QAOAConfigurationError
from backend.app.quantum.optimization.qaoa_models import QAOAConfig, QAOAParameterSet


class QAOACircuitBuilder:
    """Build p-layer QAOA circuits for the E.2 Ising convention."""

    def build(self, problem: IsingProblem, parameters: QAOAParameterSet, config: QAOAConfig) -> QuantumCircuit:
        """Return a QAOA circuit using H initialization, cost phases, and RX mixers."""

        if not isinstance(problem, IsingProblem):
            raise QAOAConfigurationError("problem must be an IsingProblem.")
        if len(problem.variables) > config.max_qubits:
            raise QAOAConfigurationError(
                f"problem qubits {len(problem.variables)} exceeds max_qubits {config.max_qubits}."
            )
        operations: list[QuantumOperation] = []
        for qubit in range(len(problem.variables)):
            operations.append(QuantumOperation("H", (qubit,), metadata={"stage": "initialization"}))
        for layer in range(parameters.depth):
            gamma = parameters.gammas[layer]
            beta = parameters.betas[layer]
            for variable_index, variable_id in enumerate(problem.variables):
                coefficient = problem.linear_coefficients.get(variable_id, 0.0)
                if coefficient != 0.0:
                    operations.append(
                        QuantumOperation(
                            "RZ",
                            (variable_index,),
                            metadata={
                                "angle": 2.0 * gamma * coefficient,
                                "stage": "cost",
                                "layer": layer,
                                "variable_id": variable_id,
                                "coefficient": coefficient,
                            },
                        )
                    )
            for left, right in sorted(problem.quadratic_coefficients):
                left_index = problem.variables.index(left)
                right_index = problem.variables.index(right)
                coefficient = problem.quadratic_coefficients[(left, right)]
                operations.append(
                    QuantumOperation(
                        "RZZ",
                        (left_index, right_index),
                        metadata={
                            "angle": 2.0 * gamma * coefficient,
                            "stage": "cost",
                            "layer": layer,
                            "variables": (left, right),
                            "coefficient": coefficient,
                        },
                    )
                )
            for qubit, variable_id in enumerate(problem.variables):
                operations.append(
                    QuantumOperation(
                        "RX",
                        (qubit,),
                        metadata={
                            "angle": 2.0 * beta,
                            "stage": "mixer",
                            "layer": layer,
                            "variable_id": variable_id,
                        },
                    )
                )
        if len(operations) > config.max_operations:
            raise QAOAConfigurationError(
                f"operation count {len(operations)} exceeds max_operations {config.max_operations}."
            )
        return QuantumCircuit(
            circuit_id=f"qaoa_{problem.problem_id}",
            qubit_count=len(problem.variables),
            operations=tuple(operations),
            metadata={
                "algorithm": "QAOA",
                "depth": parameters.depth,
                "problem_id": problem.problem_id,
                "cost_offset_preserved_for_energy": problem.constant_offset,
            },
        )
