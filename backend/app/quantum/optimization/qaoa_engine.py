from __future__ import annotations

from typing import Mapping

from backend.app.quantum.domain import IsingProblem, QUBOProblem, QuantumSolution
from backend.app.quantum.execution import QuantumExecutionConfig, QuantumExecutionEngine, QuantumExecutionRequest
from backend.app.quantum.optimization.exceptions import QAOAExecutionError, QAOAResultError
from backend.app.quantum.optimization.qaoa_circuit import QAOACircuitBuilder
from backend.app.quantum.optimization.qaoa_cost import QAOACostEvaluator
from backend.app.quantum.optimization.qaoa_models import QAOAConfig, QAOAParameterSet, QAOAResult
from backend.app.quantum.optimization.qaoa_optimizer import DeterministicQAOAParameterOptimizer

ENERGY_TOLERANCE = 1e-12


class QAOAEngine:
    """Execute bounded local QAOA through the E.4 execution engine."""

    def __init__(
        self,
        *,
        execution_engine: QuantumExecutionEngine | None = None,
        circuit_builder: QAOACircuitBuilder | None = None,
        cost_evaluator: QAOACostEvaluator | None = None,
        parameter_optimizer: DeterministicQAOAParameterOptimizer | None = None,
    ) -> None:
        self.execution_engine = execution_engine or QuantumExecutionEngine()
        self.circuit_builder = circuit_builder or QAOACircuitBuilder()
        self.cost_evaluator = cost_evaluator or QAOACostEvaluator()
        self.parameter_optimizer = parameter_optimizer or DeterministicQAOAParameterOptimizer()

    def solve(self, problem: QUBOProblem | IsingProblem, config: QAOAConfig | None = None) -> QAOAResult:
        """Run QAOA and return the best measured candidate without exact-solver substitution."""

        config = config or QAOAConfig(parameters=QAOAParameterSet((0.0,), (0.0,)))
        ising_problem, representation = self.cost_evaluator.normalize_problem(problem)
        variable_mapping = {variable_id: index for index, variable_id in enumerate(ising_problem.variables)}
        comparison = self.parameter_optimizer.comparison_mode(ising_problem)
        best_result: QAOAResult | None = None
        for index, parameters in enumerate(self.parameter_optimizer.candidate_parameters(config)):
            circuit = self.circuit_builder.build(ising_problem, parameters, config)
            execution_result = self.execution_engine.execute(
                QuantumExecutionRequest(
                    request_id=f"qaoa_{ising_problem.problem_id}_{index}",
                    circuit=circuit,
                    config=QuantumExecutionConfig(
                        shots=config.shots,
                        seed=config.seed,
                        max_qubits=config.max_qubits,
                        max_shots=config.max_shots,
                    ),
                    variable_mapping=variable_mapping,
                    problem=ising_problem,
                    metadata={"algorithm": "QAOA", "parameter_index": index},
                )
            )
            expectation = self.cost_evaluator.statevector_expectation(ising_problem, execution_result.statevector)
            empirical = self.cost_evaluator.empirical_expectation(ising_problem, execution_result.measurement.counts)
            ranked = self._rank_candidates(
                problem=ising_problem,
                counts=execution_result.measurement.counts,
                comparison=comparison,
                parameters=parameters,
                representation=representation,
                request_id=f"qaoa_{ising_problem.problem_id}_{index}",
            )
            result = QAOAResult(
                problem_id=ising_problem.problem_id,
                representation=representation,
                parameters=parameters,
                expectation_value=expectation,
                empirical_expectation_value=empirical,
                best_solution=ranked[0],
                ranked_candidates=ranked,
                metadata={
                    "algorithm": "QAOA",
                    "depth": parameters.depth,
                    "shots": config.shots,
                    "seed": config.seed,
                    "backend": "local_statevector_simulator",
                    "execution_request_id": execution_result.request_id,
                    "comparison_mode": comparison,
                    "operation_count": len(circuit.operations),
                    "statevector_norm": self._statevector_norm(execution_result.statevector),
                    "parameter_index": index,
                    "optimized_parameters": config.optimize_parameters,
                },
            )
            if best_result is None or self._result_better(result, best_result, comparison):
                best_result = result
        if best_result is None:
            raise QAOAExecutionError("QAOA produced no result.")
        return best_result

    def _rank_candidates(
        self,
        *,
        problem: IsingProblem,
        counts: Mapping[str, int],
        comparison: str,
        parameters: QAOAParameterSet,
        representation: str,
        request_id: str,
    ) -> tuple[QuantumSolution, ...]:
        candidates: list[QuantumSolution] = []
        for bitstring in sorted(counts):
            assignment = {
                variable_id: int(bitstring[index])
                for index, variable_id in enumerate(problem.variables)
            }
            spins = {variable_id: (2 * value) - 1 for variable_id, value in assignment.items()}
            energy = self.cost_evaluator.spin_energy(problem, spins)
            candidates.append(
                QuantumSolution(
                    solution_id=f"qaoa_{request_id}_{bitstring}",
                    problem_id=problem.problem_id,
                    assignments=assignment,
                    objective_value=energy,
                    feasible=True,
                    energy=energy,
                    solver_name="qaoa_local_statevector",
                    execution_mode="local_simulator",
                    metadata={
                        "algorithm": "QAOA",
                        "representation": representation,
                        "bitstring": bitstring,
                        "count": counts[bitstring],
                        "gammas": parameters.gammas,
                        "betas": parameters.betas,
                        "method": "measured_candidate_energy_ranking",
                        "spin_assignments": spins,
                    },
                )
            )
        if not candidates:
            raise QAOAResultError("QAOA measurement produced no candidates.")
        return tuple(sorted(candidates, key=lambda candidate: self._candidate_sort_key(candidate, comparison, problem.variables)))

    @staticmethod
    def _candidate_sort_key(candidate: QuantumSolution, comparison: str, variable_order: tuple[str, ...]) -> tuple:
        assignment_key = tuple(candidate.assignments[variable_id] for variable_id in variable_order)
        if comparison == "MAXIMIZE":
            return (-candidate.objective_value, assignment_key)
        return (candidate.objective_value, assignment_key)

    @staticmethod
    def _result_better(current: QAOAResult, best: QAOAResult, comparison: str) -> bool:
        current_energy = current.best_solution.objective_value
        best_energy = best.best_solution.objective_value
        if comparison == "MAXIMIZE":
            if current_energy > best_energy + ENERGY_TOLERANCE:
                return True
            if current_energy < best_energy - ENERGY_TOLERANCE:
                return False
        else:
            if current_energy < best_energy - ENERGY_TOLERANCE:
                return True
            if current_energy > best_energy + ENERGY_TOLERANCE:
                return False
        return current.parameters.to_dict()["gammas"] + current.parameters.to_dict()["betas"] < (
            best.parameters.to_dict()["gammas"] + best.parameters.to_dict()["betas"]
        )

    @staticmethod
    def _statevector_norm(statevector: tuple[complex, ...]) -> float:
        return sum((amplitude.real * amplitude.real) + (amplitude.imag * amplitude.imag) for amplitude in statevector)
