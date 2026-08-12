from __future__ import annotations

from dataclasses import dataclass

from backend.app.quantum.baseline import ExactClassicalSolver
from backend.app.quantum.domain import IsingProblem, QUBOProblem
from backend.app.quantum.optimization.qaoa_models import QAOAResult


@dataclass(frozen=True)
class QAOABenchmarkReport:
    """Comparison report between QAOA measured candidate and E.3 exact reference."""

    exact_reference_energy: float
    absolute_energy_gap: float
    relative_energy_gap: float | None
    exact_optimum_found: bool
    approximation_ratio: float | None


class QAOABenchmarkComparator:
    """Compare QAOA output with E.3 exact classical ground truth."""

    def __init__(self, solver: ExactClassicalSolver | None = None) -> None:
        self.solver = solver or ExactClassicalSolver()

    def compare(self, problem: QUBOProblem | IsingProblem, result: QAOAResult) -> QAOABenchmarkReport:
        """Return a pure comparison report; it does not influence QAOA solving."""

        exact = self.solver.solve(problem)
        candidate_energy = result.best_solution.objective_value
        absolute_gap = abs(candidate_energy - exact.objective_value)
        relative_gap = None if exact.objective_value == 0 else absolute_gap / abs(exact.objective_value)
        approximation_ratio = None if exact.objective_value == 0 else candidate_energy / exact.objective_value
        return QAOABenchmarkReport(
            exact_reference_energy=exact.objective_value,
            absolute_energy_gap=absolute_gap,
            relative_energy_gap=relative_gap,
            exact_optimum_found=absolute_gap <= 1e-9,
            approximation_ratio=approximation_ratio,
        )
