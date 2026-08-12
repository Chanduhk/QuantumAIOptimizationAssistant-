from __future__ import annotations

from typing import Mapping

from backend.app.quantum.baseline import ExactClassicalSolver
from backend.app.quantum.domain import IsingProblem, QUBOProblem, QuantumSolution
from backend.app.quantum.execution.exceptions import QuantumDecodingError
from backend.app.quantum.execution.models import QuantumMeasurementResult


class QuantumResultDecoder:
    """Decode measured bitstrings into validated QuantumSolution candidates."""

    def __init__(self, solver: ExactClassicalSolver | None = None) -> None:
        self.solver = solver or ExactClassicalSolver()

    def decode(
        self,
        *,
        request_id: str,
        measurement: QuantumMeasurementResult,
        variable_mapping: Mapping[str, int],
        problem: QUBOProblem | IsingProblem | None,
    ) -> QuantumSolution | None:
        """Decode the most likely bitstring; return None when no problem exists."""

        if problem is None:
            return None
        if not isinstance(measurement, QuantumMeasurementResult):
            raise QuantumDecodingError("measurement must be a QuantumMeasurementResult.")
        if not isinstance(variable_mapping, Mapping) or not variable_mapping:
            raise QuantumDecodingError("variable_mapping is required when decoding a problem result.")
        bitstring = self._most_likely_bitstring(measurement.counts)
        assignment = self._assignment_from_bitstring(bitstring, variable_mapping)
        if isinstance(problem, QUBOProblem):
            energy = self.solver.evaluate_qubo_energy(problem, assignment)
            representation = "QUBO"
        elif isinstance(problem, IsingProblem):
            spins = {variable_id: (2 * value) - 1 for variable_id, value in assignment.items()}
            energy = self.solver.evaluate_ising_energy(problem, spins)
            representation = "Ising"
        else:
            raise QuantumDecodingError("problem must be a QUBOProblem, IsingProblem, or None.")
        return QuantumSolution(
            solution_id=f"decoded_{request_id}",
            problem_id=problem.problem_id,
            assignments=assignment,
            objective_value=energy,
            feasible=True,
            energy=energy,
            solver_name="local_statevector_simulator",
            execution_mode="local_simulator",
            metadata={
                "decoded_from_request_id": request_id,
                "representation": representation,
                "bitstring": bitstring,
                "method": "measurement_decoding",
            },
        )

    @staticmethod
    def _most_likely_bitstring(counts: Mapping[str, int]) -> str:
        if not counts:
            raise QuantumDecodingError("counts cannot be empty.")
        return sorted(counts, key=lambda bitstring: (-counts[bitstring], bitstring))[0]

    @staticmethod
    def _assignment_from_bitstring(bitstring: str, variable_mapping: Mapping[str, int]) -> dict[str, int]:
        assignment: dict[str, int] = {}
        for variable_id in sorted(variable_mapping):
            qubit = variable_mapping[variable_id]
            if qubit >= len(bitstring):
                raise QuantumDecodingError(f"variable '{variable_id}' maps outside bitstring width.")
            assignment[variable_id] = int(bitstring[qubit])
        return assignment
