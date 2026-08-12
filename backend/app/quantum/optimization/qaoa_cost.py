from __future__ import annotations

from typing import Mapping

from backend.app.quantum.domain import IsingProblem, QUBOProblem
from backend.app.quantum.formulation import QUBOToIsingConverter


class QAOACostEvaluator:
    """Evaluate Ising cost Hamiltonian expectations using E.2 conventions."""

    def normalize_problem(self, problem: QUBOProblem | IsingProblem) -> tuple[IsingProblem, str]:
        """Return an Ising representation and the original representation name."""

        if isinstance(problem, IsingProblem):
            return problem, "Ising"
        if isinstance(problem, QUBOProblem):
            return QUBOToIsingConverter().convert(problem), "QUBO"
        raise ValueError("problem must be a QUBOProblem or IsingProblem.")

    def bitstring_energy(self, problem: IsingProblem, bitstring: str) -> float:
        """Evaluate H_C for one measured bitstring under s_i = 2x_i - 1."""

        if len(bitstring) != len(problem.variables) or any(bit not in {"0", "1"} for bit in bitstring):
            raise ValueError("bitstring length or values are invalid for the Ising problem.")
        spins = {variable_id: (2 * int(bitstring[index])) - 1 for index, variable_id in enumerate(problem.variables)}
        return self.spin_energy(problem, spins)

    def spin_energy(self, problem: IsingProblem, spins: Mapping[str, int]) -> float:
        """Evaluate H_C = offset + sum h_i s_i + sum J_ij s_i s_j."""

        energy = float(problem.constant_offset)
        for variable_id in problem.variables:
            value = spins.get(variable_id)
            if value not in (-1, 1) or isinstance(value, bool):
                raise ValueError(f"spin for '{variable_id}' must be -1 or +1.")
        for variable_id in sorted(problem.linear_coefficients):
            energy += problem.linear_coefficients[variable_id] * spins[variable_id]
        for left, right in sorted(problem.quadratic_coefficients):
            energy += problem.quadratic_coefficients[(left, right)] * spins[left] * spins[right]
        return energy

    def statevector_expectation(self, problem: IsingProblem, statevector: tuple[complex, ...]) -> float:
        """Compute exact statevector expectation <psi|H_C|psi>."""

        expected_length = 2 ** len(problem.variables)
        if len(statevector) != expected_length:
            raise ValueError("statevector length does not match problem variable count.")
        expectation = 0.0
        for index, amplitude in enumerate(statevector):
            probability = (amplitude.real * amplitude.real) + (amplitude.imag * amplitude.imag)
            if probability:
                expectation += probability * self.bitstring_energy(problem, format(index, f"0{len(problem.variables)}b"))
        return expectation

    def empirical_expectation(self, problem: IsingProblem, counts: Mapping[str, int]) -> float:
        """Compute shot-based expected energy from measured counts."""

        total = sum(counts.values())
        if total <= 0:
            raise ValueError("counts must contain at least one shot.")
        return sum(self.bitstring_energy(problem, bitstring) * count for bitstring, count in counts.items()) / total
