from __future__ import annotations

from backend.app.quantum.hybrid.hybrid_models import HybridCandidate, HybridComparison, HybridSelection

CANDIDATE_TYPE_PRIORITY = {
    "quantum_qaoa": 0,
    "classical_exact": 1,
    "classical_heuristic": 2,
}


class HybridCandidateComparator:
    """Rank feasible hybrid candidates deterministically under objective sense."""

    def rank(
        self,
        candidates: tuple[HybridCandidate, ...],
        *,
        exact_reference_energy: float,
        sense: str,
        tolerance: float,
    ) -> tuple[HybridCandidate, ...]:
        """Return candidates sorted from best to worst."""

        if not candidates:
            raise ValueError("candidates cannot be empty.")
        if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
            raise ValueError("candidate IDs must be unique.")
        if sense not in {"MINIMIZE", "MAXIMIZE"}:
            raise ValueError("sense must be MINIMIZE or MAXIMIZE.")
        return tuple(
            sorted(
                candidates,
                key=lambda candidate: self._sort_key(candidate, exact_reference_energy, sense, tolerance),
            )
        )

    def comparisons(
        self,
        ranked: tuple[HybridCandidate, ...],
        *,
        exact_reference_energy: float,
        tolerance: float,
    ) -> tuple[HybridComparison, ...]:
        """Build immutable comparison rows against exact reference."""

        comparisons: list[HybridComparison] = []
        for rank, candidate in enumerate(ranked, start=1):
            gap = abs(candidate.objective_value - exact_reference_energy)
            relative_gap = None if exact_reference_energy == 0 else gap / abs(exact_reference_energy)
            comparisons.append(
                HybridComparison(
                    candidate_id=candidate.candidate_id,
                    candidate_type=candidate.candidate_type,
                    objective_value=candidate.objective_value,
                    feasible=candidate.feasible,
                    energy_gap_to_exact=gap,
                    relative_gap=relative_gap,
                    exact_match=gap <= tolerance,
                    rank=rank,
                    rationale=self._rationale(candidate, gap, tolerance),
                )
            )
        return tuple(comparisons)

    @staticmethod
    def selection(candidate: HybridCandidate) -> HybridSelection:
        """Return selected candidate summary."""

        reason = (
            f"Selected {candidate.candidate_type} because it is feasible and best under deterministic objective ranking."
            if candidate.feasible
            else f"Selected {candidate.candidate_type} only because all candidates are infeasible."
        )
        return HybridSelection(
            selected_candidate_id=candidate.candidate_id,
            selected_candidate_type=candidate.candidate_type,
            selected_objective_value=candidate.objective_value,
            reason_selected=reason,
        )

    @staticmethod
    def _sort_key(candidate: HybridCandidate, exact_reference_energy: float, sense: str, tolerance: float) -> tuple:
        feasibility_rank = 0 if candidate.feasible else 1
        objective_rank = candidate.objective_value if sense == "MINIMIZE" else -candidate.objective_value
        gap = abs(candidate.objective_value - exact_reference_energy)
        if gap <= tolerance:
            gap = 0.0
        assignment_key = tuple(candidate.assignment[key] for key in sorted(candidate.assignment))
        return (
            feasibility_rank,
            objective_rank,
            gap,
            CANDIDATE_TYPE_PRIORITY[candidate.candidate_type],
            assignment_key,
            candidate.candidate_id,
        )

    @staticmethod
    def _rationale(candidate: HybridCandidate, gap: float, tolerance: float) -> str:
        if not candidate.feasible:
            return f"{candidate.candidate_type} is infeasible and loses to feasible candidates."
        if gap <= tolerance:
            return f"{candidate.candidate_type} matches the exact reference within tolerance."
        return f"{candidate.candidate_type} differs from the exact reference by {gap:.12g}."
