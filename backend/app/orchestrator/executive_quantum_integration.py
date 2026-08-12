from __future__ import annotations

from typing import Any, Dict

from backend.app.domain.executive_reasoning_model import Evidence
from backend.app.orchestrator.executive_quantum_evidence import ExecutiveQuantumEvidence, evidence_from_e7
from backend.app.quantum.integration import AIQuantumIntegrationResult


class ExecutiveQuantumIntegration:
    """Adapt E.7 AI+Quantum results into executive evidence and summaries."""

    def adapt(self, result: AIQuantumIntegrationResult | ExecutiveQuantumEvidence) -> ExecutiveQuantumEvidence:
        """Return validated executive quantum evidence without mutating E.7 output."""

        if isinstance(result, ExecutiveQuantumEvidence):
            return result
        return evidence_from_e7(result)

    def to_reasoning_evidence(self, evidence: ExecutiveQuantumEvidence) -> Evidence:
        """Convert quantum evidence into the ExecutiveReasoningEngine evidence contract."""

        if not isinstance(evidence, ExecutiveQuantumEvidence):
            raise ValueError("evidence must be ExecutiveQuantumEvidence.")
        confidence = self._confidence(evidence)
        score = self._score(evidence)
        risk_level = self._risk_level(evidence)
        recommendation = self._recommendation(evidence)
        return Evidence(
            source="AIQuantumIntegration",
            confidence=confidence,
            recommendation=recommendation,
            risk_level=risk_level,
            priority=3,
            score=score,
            explanation=self._explanation(evidence),
            metadata={
                "problem_id": evidence.problem_id,
                "quantum_used": evidence.quantum_used,
                "classical_used": evidence.classical_used,
                "exact_match": evidence.exact_match,
                "energy_gap": evidence.energy_gap,
                "relative_gap": evidence.relative_gap,
                "selected_candidate_type": evidence.selected_candidate_type,
                "qaoa_executed": evidence.metadata.get("qaoa_executed", False),
                "hardware_execution": evidence.metadata.get("hardware_execution", False),
                "quantum_advantage_claimed": False,
            },
        )

    def outputs(self, evidence: ExecutiveQuantumEvidence) -> Dict[str, Any]:
        """Return additive Executive Brain quantum-aware outputs."""

        reasoning_evidence = self.to_reasoning_evidence(evidence)
        summary = {
            "problem_id": evidence.problem_id,
            "suitability_decision": evidence.suitability_decision,
            "execution_path": evidence.execution_path,
            "quantum_used": evidence.quantum_used,
            "classical_used": evidence.classical_used,
            "selected_solver": evidence.selected_solver,
            "selected_candidate_type": evidence.selected_candidate_type,
            "exact_match": evidence.exact_match,
            "energy_gap": evidence.energy_gap,
            "relative_gap": evidence.relative_gap,
            "feasible": evidence.feasible,
        }
        risk = {
            "risk_level": self._risk_level(evidence),
            "warnings": list(evidence.warnings),
            "resource_limited": evidence.suitability_decision == "RESOURCE_LIMIT",
            "requires_reformulation": evidence.suitability_decision == "REQUIRES_REFORMULATION",
        }
        return {
            "executive_quantum_summary": summary,
            "executive_quantum_evidence": evidence.to_dict(),
            "executive_quantum_risk": risk,
            "executive_quantum_tradeoffs": {
                "tradeoffs": self.tradeoffs(evidence),
                "gap": evidence.energy_gap,
                "relative_gap": evidence.relative_gap,
            },
            "executive_quantum_reasoning": {
                "source": reasoning_evidence.source,
                "recommendation": reasoning_evidence.recommendation,
                "confidence": reasoning_evidence.confidence,
                "score": reasoning_evidence.score,
            },
            "executive_quantum_recommendation": {
                "recommendation": reasoning_evidence.recommendation,
                "reason": reasoning_evidence.explanation,
            },
            "executive_quantum_confidence": {"confidence": reasoning_evidence.confidence},
            "executive_quantum_gap": {
                "energy_gap": evidence.energy_gap,
                "relative_gap": evidence.relative_gap,
                "exact_match": evidence.exact_match,
            },
        }

    def tradeoffs(self, evidence: ExecutiveQuantumEvidence) -> list[str]:
        """Return deterministic executive tradeoffs implied by quantum evidence."""

        tradeoffs = []
        if evidence.quantum_used:
            tradeoffs.append("Quantum candidate evidence was available for executive comparison.")
        if evidence.classical_used:
            tradeoffs.append("Classical reference evidence remains part of the executive decision.")
        if evidence.exact_match is False:
            tradeoffs.append("Quantum result did not match exact reference, increasing verification risk.")
        if evidence.execution_path == "classical_fallback":
            tradeoffs.append("Classical fallback avoided quantum execution risk.")
        if evidence.suitability_decision == "RESOURCE_LIMIT":
            tradeoffs.append("Quantum resource limits constrain this recommendation.")
        if evidence.suitability_decision == "REQUIRES_REFORMULATION":
            tradeoffs.append("Problem reformulation is required before quantum execution.")
        return sorted(dict.fromkeys(tradeoffs)) or ["No material quantum tradeoff detected."]

    def _recommendation(self, evidence: ExecutiveQuantumEvidence) -> str:
        if evidence.suitability_decision == "REQUIRES_REFORMULATION":
            return "Reformulate optimization problem before quantum execution"
        if evidence.execution_path == "classical_fallback":
            return "Use classical fallback and treat quantum as unavailable evidence"
        if evidence.quantum_used and evidence.exact_match is True:
            return "Treat quantum candidate as corroborating optimization evidence"
        if evidence.quantum_used and evidence.exact_match is False:
            return "Prefer verified hybrid selection over raw quantum candidate"
        return "Review quantum suitability before relying on optimization evidence"

    def _explanation(self, evidence: ExecutiveQuantumEvidence) -> str:
        return (
            f"E.7 reported {evidence.suitability_decision} via {evidence.execution_path}; "
            f"selected solver is {evidence.selected_solver or 'none'} with gap {evidence.energy_gap}."
        )

    def _confidence(self, evidence: ExecutiveQuantumEvidence) -> float:
        confidence = 55.0
        if evidence.quantum_used:
            confidence += 10.0
        if evidence.classical_used and evidence.exact_reference_available:
            confidence += 15.0
        if evidence.exact_match is True:
            confidence += 12.0
        if evidence.exact_match is False:
            confidence -= 18.0
        if evidence.suitability_decision == "RESOURCE_LIMIT":
            confidence -= 20.0
        if evidence.suitability_decision == "REQUIRES_REFORMULATION":
            confidence -= 25.0
        if evidence.feasible is False:
            confidence -= 35.0
        return round(max(0.0, min(100.0, confidence)), 2)

    def _score(self, evidence: ExecutiveQuantumEvidence) -> float:
        score = self._confidence(evidence)
        if evidence.energy_gap is not None:
            score -= min(30.0, evidence.energy_gap * 10.0)
        if evidence.relative_gap is not None:
            score -= min(20.0, evidence.relative_gap * 20.0)
        return round(max(0.0, min(100.0, score)), 2)

    def _risk_level(self, evidence: ExecutiveQuantumEvidence) -> str:
        if evidence.feasible is False or evidence.suitability_decision == "REQUIRES_REFORMULATION":
            return "high"
        if evidence.suitability_decision == "RESOURCE_LIMIT":
            return "medium"
        if evidence.quantum_used and evidence.exact_match is False:
            return "medium"
        return "low"
