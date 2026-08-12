from __future__ import annotations

from backend.app.quantum.integration.models import AIQuantumIntegrationConfig, QuantumSuitabilityResult


class AIQuantumRouter:
    """Choose the E.7 execution path from suitability and fallback policy."""

    def route(self, suitability: QuantumSuitabilityResult, config: AIQuantumIntegrationConfig) -> str:
        """Return a deterministic execution path string."""

        if not isinstance(suitability, QuantumSuitabilityResult):
            raise ValueError("suitability must be a QuantumSuitabilityResult.")
        if not isinstance(config, AIQuantumIntegrationConfig):
            raise ValueError("config must be an AIQuantumIntegrationConfig.")
        if suitability.decision == "SUITABLE":
            return "quantum_hybrid"
        if suitability.decision == "REQUIRES_REFORMULATION":
            return "classical_fallback" if config.allow_classical_fallback else "requires_reformulation"
        if suitability.decision == "RESOURCE_LIMIT":
            return "classical_fallback" if config.allow_classical_fallback else "resource_limited"
        if suitability.decision in {"UNSUITABLE", "UNSUPPORTED"}:
            return "classical_fallback" if config.allow_classical_fallback else "unsupported"
        raise ValueError("unsupported suitability decision.")
