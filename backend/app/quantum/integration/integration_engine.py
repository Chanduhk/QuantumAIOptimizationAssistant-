from __future__ import annotations

from typing import Any, Mapping

from backend.app.quantum.baseline import ExactClassicalSolver
from backend.app.quantum.domain import IsingProblem, ObjectiveSense, QUBOProblem, QuantumSolution
from backend.app.quantum.domain.quantum_objective import _validate_identifier
from backend.app.quantum.hybrid import HybridCandidate, HybridFeasibilityChecker, HybridOptimizationConfig, HybridOptimizationEngine
from backend.app.quantum.integration.explanations import AIQuantumExplanationBuilder
from backend.app.quantum.integration.models import (
    AIOptimizationProblem,
    AIQuantumIntegrationConfig,
    AIQuantumIntegrationResult,
    QuantumSuitabilityResult,
)
from backend.app.quantum.integration.problem_adapter import AIQuantumProblemAdapter
from backend.app.quantum.integration.router import AIQuantumRouter
from backend.app.quantum.integration.suitability import QuantumSuitabilityAnalyzer
from backend.app.quantum.optimization import QAOAConfig


class AIQuantumIntegrationEngine:
    """Bridge AI optimization contracts to the existing E.1-E.6 quantum stack."""

    def __init__(
        self,
        *,
        adapter: AIQuantumProblemAdapter | None = None,
        suitability_analyzer: QuantumSuitabilityAnalyzer | None = None,
        router: AIQuantumRouter | None = None,
        hybrid_engine: HybridOptimizationEngine | None = None,
        exact_solver: ExactClassicalSolver | None = None,
        feasibility_checker: HybridFeasibilityChecker | None = None,
        explanation_builder: AIQuantumExplanationBuilder | None = None,
    ) -> None:
        self.adapter = adapter or AIQuantumProblemAdapter()
        self.suitability_analyzer = suitability_analyzer or QuantumSuitabilityAnalyzer()
        self.router = router or AIQuantumRouter()
        self.hybrid_engine = hybrid_engine or HybridOptimizationEngine()
        self.exact_solver = exact_solver or ExactClassicalSolver()
        self.feasibility_checker = feasibility_checker or HybridFeasibilityChecker()
        self.explanation_builder = explanation_builder or AIQuantumExplanationBuilder()

    def optimize(
        self,
        request_id: str,
        problem: AIOptimizationProblem | QUBOProblem | IsingProblem | Mapping[str, Any],
        *,
        config: AIQuantumIntegrationConfig | None = None,
        qaoa_config: QAOAConfig | None = None,
    ) -> AIQuantumIntegrationResult:
        """Adapt, route, and execute a truthful AI + quantum optimization request."""

        request_id = _validate_identifier(request_id, "request_id")
        config = config or AIQuantumIntegrationConfig()
        qaoa_config = qaoa_config or QAOAConfig(shots=config.qaoa_shots, seed=config.qaoa_seed)
        problem_id = self._problem_id_for_error(problem)
        try:
            quantum_problem = self.adapter.adapt(problem)
        except ValueError as exc:
            if self._is_reformulation_case(str(exc), problem):
                suitability = QuantumSuitabilityResult(
                    "REQUIRES_REFORMULATION",
                    (str(exc),),
                    0,
                    0,
                    "adapter",
                )
                return self._empty_result(
                    request_id=request_id,
                    problem_id=problem_id,
                    objective_sense=self._objective_sense_for_error(problem),
                    suitability=suitability,
                    execution_path="requires_reformulation",
                )
            raise

        suitability = self.suitability_analyzer.analyze(quantum_problem, config=config, qaoa_config=qaoa_config)
        execution_path = self.router.route(suitability, config)
        if execution_path == "quantum_hybrid":
            return self._run_quantum_hybrid(request_id, quantum_problem, suitability, qaoa_config)
        if execution_path == "classical_fallback":
            return self._run_classical_fallback(request_id, quantum_problem, suitability)
        return self._empty_result(
            request_id=request_id,
            problem_id=quantum_problem.problem_id,
            objective_sense=quantum_problem.objective.sense.value,
            suitability=suitability,
            execution_path=execution_path,
        )

    def _run_quantum_hybrid(
        self,
        request_id: str,
        problem: QUBOProblem | IsingProblem,
        suitability: QuantumSuitabilityResult,
        qaoa_config: QAOAConfig,
    ) -> AIQuantumIntegrationResult:
        hybrid_result = self.hybrid_engine.optimize(
            problem,
            qaoa_config=qaoa_config,
            config=HybridOptimizationConfig(include_exact_reference=True, include_qaoa_candidate=True),
        )
        classical_candidate = self._candidate_by_type(hybrid_result.candidates, "classical_exact")
        quantum_candidate = self._candidate_by_type(hybrid_result.candidates, "quantum_qaoa")
        selected = hybrid_result.selected_candidate
        explanation = self.explanation_builder.build(
            execution_path="quantum_hybrid",
            suitability=suitability,
            hybrid_result=hybrid_result,
            classical_used=True,
            quantum_used=True,
        )
        return AIQuantumIntegrationResult(
            request_id=request_id,
            problem_id=problem.problem_id,
            objective_sense=problem.objective.sense.value,
            suitability_decision=suitability.decision,
            suitability_reasons=suitability.reasons,
            execution_path="quantum_hybrid",
            quantum_used=True,
            classical_used=True,
            classical_candidate=classical_candidate,
            quantum_candidate=quantum_candidate,
            hybrid_result=hybrid_result,
            selected_candidate=selected,
            selected_solver=selected.solver_name,
            objective_value=selected.objective_value,
            energy=selected.energy,
            feasible=selected.feasible,
            exact_reference_available=True,
            exact_match=hybrid_result.benchmark_report.exact_match,
            energy_gap=hybrid_result.benchmark_report.energy_gap,
            relative_gap=hybrid_result.benchmark_report.relative_gap,
            explanation=explanation,
            execution_metadata={
                "e7_engine": "ai_quantum_integration",
                "e6_used": True,
                "qaoa_executed": quantum_candidate is not None,
                "hardware_execution": False,
                "quantum_advantage_claimed": False,
            },
        )

    def _run_classical_fallback(
        self,
        request_id: str,
        problem: QUBOProblem | IsingProblem,
        suitability: QuantumSuitabilityResult,
    ) -> AIQuantumIntegrationResult:
        try:
            solution = self.exact_solver.solve(problem)
        except ValueError:
            return self._empty_result(
                request_id=request_id,
                problem_id=problem.problem_id,
                objective_sense=problem.objective.sense.value,
                suitability=suitability,
                execution_path="resource_limited" if suitability.decision == "RESOURCE_LIMIT" else "unsupported",
            )
        candidate = self._candidate_from_solution(solution, problem)
        explanation = self.explanation_builder.build(
            execution_path="classical_fallback",
            suitability=suitability,
            hybrid_result=None,
            classical_used=True,
            quantum_used=False,
        )
        return AIQuantumIntegrationResult(
            request_id=request_id,
            problem_id=problem.problem_id,
            objective_sense=problem.objective.sense.value,
            suitability_decision=suitability.decision,
            suitability_reasons=suitability.reasons,
            execution_path="classical_fallback",
            quantum_used=False,
            classical_used=True,
            classical_candidate=candidate,
            quantum_candidate=None,
            hybrid_result=None,
            selected_candidate=candidate,
            selected_solver=candidate.solver_name,
            objective_value=candidate.objective_value,
            energy=candidate.energy,
            feasible=candidate.feasible,
            exact_reference_available=True,
            exact_match=None,
            energy_gap=None,
            relative_gap=None,
            explanation=explanation,
            execution_metadata={
                "e7_engine": "ai_quantum_integration",
                "e6_used": False,
                "qaoa_executed": False,
                "hardware_execution": False,
                "quantum_advantage_claimed": False,
            },
        )

    def _empty_result(
        self,
        *,
        request_id: str,
        problem_id: str,
        objective_sense: str,
        suitability: QuantumSuitabilityResult,
        execution_path: str,
    ) -> AIQuantumIntegrationResult:
        explanation = self.explanation_builder.build(
            execution_path=execution_path,
            suitability=suitability,
            hybrid_result=None,
            classical_used=False,
            quantum_used=False,
        )
        return AIQuantumIntegrationResult(
            request_id=request_id,
            problem_id=problem_id,
            objective_sense=objective_sense,
            suitability_decision=suitability.decision,
            suitability_reasons=suitability.reasons,
            execution_path=execution_path,
            quantum_used=False,
            classical_used=False,
            classical_candidate=None,
            quantum_candidate=None,
            hybrid_result=None,
            selected_candidate=None,
            selected_solver=None,
            objective_value=None,
            energy=None,
            feasible=None,
            exact_reference_available=False,
            exact_match=None,
            energy_gap=None,
            relative_gap=None,
            explanation=explanation,
            execution_metadata={
                "e7_engine": "ai_quantum_integration",
                "e6_used": False,
                "qaoa_executed": False,
                "hardware_execution": False,
                "quantum_advantage_claimed": False,
            },
        )

    def _candidate_from_solution(
        self,
        solution: QuantumSolution,
        problem: QUBOProblem | IsingProblem,
    ) -> HybridCandidate:
        feasible = bool(solution.feasible) and self.feasibility_checker.validate_assignment(problem, solution.assignments)
        return HybridCandidate(
            candidate_id=f"classical_fallback_{problem.problem_id}",
            candidate_type="classical_exact",
            problem_id=problem.problem_id,
            objective_value=solution.objective_value,
            feasible=feasible,
            assignment=solution.assignments,
            energy=solution.energy if solution.energy is not None else solution.objective_value,
            sense=self._comparison_mode(problem),
            solver_name=solution.solver_name,
            metadata={
                "source_solution_id": solution.solution_id,
                "fallback": True,
                "exact": True,
            },
        )

    @staticmethod
    def _candidate_by_type(candidates: tuple[HybridCandidate, ...], candidate_type: str) -> HybridCandidate | None:
        for candidate in candidates:
            if candidate.candidate_type == candidate_type:
                return candidate
        return None

    @staticmethod
    def _comparison_mode(problem: QUBOProblem | IsingProblem) -> str:
        if problem.metadata.get("objective_transformed_for_minimization") is True:
            return "MINIMIZE"
        if problem.metadata.get("source_problem_type") == "QUBO":
            return "MINIMIZE"
        if problem.objective.sense is ObjectiveSense.MAXIMIZE:
            return "MAXIMIZE"
        return "MINIMIZE"

    @staticmethod
    def _is_reformulation_case(message: str, problem: object) -> bool:
        if not isinstance(problem, Mapping):
            return False
        lowered = message.lower()
        return any(term in lowered for term in ("domain", "penalty", "constraints", "unsupported"))

    @staticmethod
    def _problem_id_for_error(problem: object) -> str:
        if isinstance(problem, (QUBOProblem, IsingProblem, AIOptimizationProblem)):
            return problem.problem_id
        if isinstance(problem, Mapping) and isinstance(problem.get("problem_id"), str):
            return _validate_identifier(problem.get("problem_id"), "problem_id")
        return "unadapted_problem"

    @staticmethod
    def _objective_sense_for_error(problem: object) -> str:
        if isinstance(problem, (QUBOProblem, IsingProblem)):
            return problem.objective.sense.value
        if isinstance(problem, AIOptimizationProblem):
            return problem.objective_sense
        if isinstance(problem, Mapping):
            sense = problem.get("objective_sense", "MINIMIZE")
            if sense in {"MINIMIZE", "MAXIMIZE"}:
                return sense
        return "MINIMIZE"
