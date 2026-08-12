from __future__ import annotations

from backend.app.quantum.domain import IsingProblem, QUBOProblem
from backend.app.quantum.integration.models import AIQuantumIntegrationConfig, QuantumSuitabilityResult
from backend.app.quantum.optimization import QAOAConfig


class QuantumSuitabilityAnalyzer:
    """Determine whether a supported problem should enter the quantum path."""

    def analyze(
        self,
        problem: QUBOProblem | IsingProblem,
        *,
        config: AIQuantumIntegrationConfig | None = None,
        qaoa_config: QAOAConfig | None = None,
    ) -> QuantumSuitabilityResult:
        """Return deterministic suitability with explicit routing reasons."""

        config = config or AIQuantumIntegrationConfig()
        qaoa_config = qaoa_config or QAOAConfig(shots=config.qaoa_shots, seed=config.qaoa_seed)
        if not isinstance(problem, (QUBOProblem, IsingProblem)):
            return QuantumSuitabilityResult("UNSUPPORTED", ("Problem is not QUBO or Ising.",), 0, 0, "problem_type")
        variable_count = self._variable_count(problem)
        estimated_states = 2 ** variable_count
        reasons: list[str] = []
        if not config.allow_quantum:
            return QuantumSuitabilityResult(
                "UNSUITABLE",
                ("Quantum routing disabled by configuration.",),
                variable_count,
                estimated_states,
                "allow_quantum",
            )
        if variable_count <= 0:
            return QuantumSuitabilityResult(
                "UNSUPPORTED",
                ("Problem has no variables.",),
                variable_count,
                estimated_states,
                "variable_count",
            )
        if variable_count > config.max_variables_for_quantum:
            return QuantumSuitabilityResult(
                "RESOURCE_LIMIT",
                (f"Variable count {variable_count} exceeds E.7 quantum limit {config.max_variables_for_quantum}.",),
                variable_count,
                estimated_states,
                "max_variables_for_quantum",
            )
        if variable_count > qaoa_config.max_qubits:
            return QuantumSuitabilityResult(
                "RESOURCE_LIMIT",
                (f"Variable count {variable_count} exceeds QAOA max_qubits {qaoa_config.max_qubits}.",),
                variable_count,
                estimated_states,
                "qaoa_max_qubits",
            )
        if estimated_states > config.max_states_for_suitability:
            return QuantumSuitabilityResult(
                "RESOURCE_LIMIT",
                (f"Estimated state count {estimated_states} exceeds E.7 suitability limit.",),
                variable_count,
                estimated_states,
                "max_states_for_suitability",
            )
        reasons.append("Problem is binary and represented as QUBO or Ising.")
        reasons.append("Problem fits current local QAOA qubit and state limits.")
        if isinstance(problem, QUBOProblem) and problem.constraints:
            reasons.append("QUBO constraints are already encoded through the E.2 formulator metadata.")
        return QuantumSuitabilityResult(
            "SUITABLE",
            tuple(reasons),
            variable_count,
            estimated_states,
            metadata={
                "qaoa_max_qubits": qaoa_config.max_qubits,
                "qaoa_max_shots": qaoa_config.max_shots,
                "qaoa_shots": qaoa_config.shots,
            },
        )

    @staticmethod
    def _variable_count(problem: QUBOProblem | IsingProblem) -> int:
        if isinstance(problem, QUBOProblem):
            return len(problem.variables)
        return len(problem.variables)
