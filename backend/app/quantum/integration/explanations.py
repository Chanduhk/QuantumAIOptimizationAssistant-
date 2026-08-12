from __future__ import annotations

from backend.app.quantum.hybrid import HybridOptimizationResult
from backend.app.quantum.integration.models import QuantumSuitabilityResult


class AIQuantumExplanationBuilder:
    """Build truthful deterministic E.7 routing explanations."""

    def build(
        self,
        *,
        execution_path: str,
        suitability: QuantumSuitabilityResult,
        hybrid_result: HybridOptimizationResult | None,
        classical_used: bool,
        quantum_used: bool,
    ) -> str:
        """Return a concise explanation of routing and result provenance."""

        if execution_path == "quantum_hybrid" and hybrid_result is not None:
            selected = hybrid_result.selection.selected_candidate_type
            return (
                f"Quantum path executed because suitability was {suitability.decision}; "
                f"E.6 selected {selected} after exact-vs-QAOA comparison."
            )
        if classical_used and not quantum_used:
            return (
                f"Classical fallback used because suitability was {suitability.decision}: "
                f"{'; '.join(suitability.reasons)}"
            )
        return f"No optimization candidate selected because suitability was {suitability.decision}: {'; '.join(suitability.reasons)}"
