"""AI + quantum optimization integration package for E.7."""

from backend.app.quantum.integration.explanations import AIQuantumExplanationBuilder
from backend.app.quantum.integration.integration_engine import AIQuantumIntegrationEngine
from backend.app.quantum.integration.models import (
    AIOptimizationProblem,
    AIOptimizationVariable,
    AIQuantumIntegrationConfig,
    AIQuantumIntegrationResult,
    QuantumSuitabilityResult,
)
from backend.app.quantum.integration.problem_adapter import AIQuantumProblemAdapter
from backend.app.quantum.integration.router import AIQuantumRouter
from backend.app.quantum.integration.suitability import QuantumSuitabilityAnalyzer

__all__ = [
    "AIOptimizationProblem",
    "AIOptimizationVariable",
    "AIQuantumExplanationBuilder",
    "AIQuantumIntegrationConfig",
    "AIQuantumIntegrationEngine",
    "AIQuantumIntegrationResult",
    "AIQuantumProblemAdapter",
    "AIQuantumRouter",
    "QuantumSuitabilityAnalyzer",
    "QuantumSuitabilityResult",
]
