from __future__ import annotations

from backend.app.quantum.domain import IsingProblem, QUBOProblem
from backend.app.quantum.hybrid.hybrid_models import HybridBenchmarkReport, HybridCandidate


class HybridBenchmarkBuilder:
    """Create lightweight benchmark reports from hybrid candidates."""

    def build(
        self,
        *,
        problem: QUBOProblem | IsingProblem,
        selected: HybridCandidate,
        candidates: tuple[HybridCandidate, ...],
        exact_reference_energy: float,
        qaoa_depth: int | None,
        tolerance: float,
    ) -> HybridBenchmarkReport:
        """Return immutable exact-vs-quantum benchmark metrics."""

        quantum = next((candidate for candidate in candidates if candidate.candidate_type == "quantum_qaoa"), None)
        quantum_energy = None if quantum is None else quantum.objective_value
        energy_gap = None if quantum is None else abs(quantum.objective_value - exact_reference_energy)
        relative_gap = None
        if energy_gap is not None and exact_reference_energy != 0:
            relative_gap = energy_gap / abs(exact_reference_energy)
        exact_match = None if energy_gap is None else energy_gap <= tolerance
        problem_size = len(problem.variables) if isinstance(problem, IsingProblem) else len(problem.variables)
        return HybridBenchmarkReport(
            exact_reference_energy=exact_reference_energy,
            quantum_candidate_energy=quantum_energy,
            energy_gap=energy_gap,
            relative_gap=relative_gap,
            exact_match=exact_match,
            candidate_count=len(candidates),
            selected_candidate_type=selected.candidate_type,
            problem_size=problem_size,
            qaoa_depth=qaoa_depth,
            metadata={
                "selected_candidate_id": selected.candidate_id,
                "candidate_types": tuple(candidate.candidate_type for candidate in candidates),
            },
        )
