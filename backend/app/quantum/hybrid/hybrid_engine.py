from __future__ import annotations

from typing import Iterable

from backend.app.quantum.baseline import ExactClassicalSolver
from backend.app.quantum.domain import IsingProblem, ObjectiveSense, QUBOProblem, QuantumSolution
from backend.app.quantum.hybrid.candidate_comparator import HybridCandidateComparator
from backend.app.quantum.hybrid.feasibility import HybridFeasibilityChecker
from backend.app.quantum.hybrid.hybrid_benchmark import HybridBenchmarkBuilder
from backend.app.quantum.hybrid.hybrid_models import (
    HybridCandidate,
    HybridOptimizationConfig,
    HybridOptimizationResult,
)
from backend.app.quantum.optimization import QAOAConfig, QAOAEngine, QAOAResult


class HybridOptimizationEngine:
    """Compare exact classical and QAOA candidates without replacing quantum answers."""

    def __init__(
        self,
        *,
        exact_solver: ExactClassicalSolver | None = None,
        qaoa_engine: QAOAEngine | None = None,
        feasibility_checker: HybridFeasibilityChecker | None = None,
        comparator: HybridCandidateComparator | None = None,
        benchmark_builder: HybridBenchmarkBuilder | None = None,
    ) -> None:
        self.exact_solver = exact_solver or ExactClassicalSolver()
        self.qaoa_engine = qaoa_engine or QAOAEngine()
        self.feasibility_checker = feasibility_checker or HybridFeasibilityChecker()
        self.comparator = comparator or HybridCandidateComparator()
        self.benchmark_builder = benchmark_builder or HybridBenchmarkBuilder()

    def optimize(
        self,
        problem: QUBOProblem | IsingProblem,
        *,
        qaoa_config: QAOAConfig | None = None,
        config: HybridOptimizationConfig | None = None,
        additional_candidates: Iterable[HybridCandidate] = (),
    ) -> HybridOptimizationResult:
        """Run E.3/E.5 candidates and return deterministic hybrid selection."""

        if not isinstance(problem, (QUBOProblem, IsingProblem)):
            raise ValueError("problem must be a QUBOProblem or IsingProblem.")
        config = config or HybridOptimizationConfig()
        sense = self._comparison_mode(problem)
        candidates: list[HybridCandidate] = []
        exact_solution = self.exact_solver.solve(problem)
        exact_candidate = self._candidate_from_solution(
            solution=exact_solution,
            problem=problem,
            candidate_id=f"classical_exact_{problem.problem_id}",
            candidate_type="classical_exact",
            sense=sense,
        )
        if config.include_exact_reference:
            candidates.append(exact_candidate)
        qaoa_result: QAOAResult | None = None
        if config.include_qaoa_candidate:
            qaoa_result = self.qaoa_engine.solve(problem, qaoa_config)
            candidates.append(
                self._candidate_from_solution(
                    solution=qaoa_result.best_solution,
                    problem=problem,
                    candidate_id=f"quantum_qaoa_{problem.problem_id}",
                    candidate_type="quantum_qaoa",
                    sense=sense,
                    qaoa_result=qaoa_result,
                )
            )
        for candidate in additional_candidates:
            if not isinstance(candidate, HybridCandidate):
                raise ValueError("additional_candidates must contain HybridCandidate instances.")
            candidates.append(
                HybridCandidate(
                    candidate_id=candidate.candidate_id,
                    candidate_type=candidate.candidate_type,
                    problem_id=problem.problem_id,
                    objective_value=candidate.objective_value,
                    feasible=candidate.feasible
                    and self.feasibility_checker.validate_assignment(problem, candidate.assignment),
                    assignment=candidate.assignment,
                    energy=candidate.energy,
                    sense=sense,
                    solver_name=candidate.solver_name,
                    metadata={**dict(candidate.metadata), "revalidated_by_hybrid_engine": True},
                )
            )
        if not candidates:
            raise ValueError("at least one candidate is required.")
        if len(candidates) > config.max_candidates:
            raise ValueError(f"candidate count {len(candidates)} exceeds max_candidates {config.max_candidates}.")
        ranked = self.comparator.rank(
            tuple(candidates),
            exact_reference_energy=exact_candidate.objective_value,
            sense=sense,
            tolerance=config.exact_match_tolerance,
        )
        comparisons = self.comparator.comparisons(
            ranked,
            exact_reference_energy=exact_candidate.objective_value,
            tolerance=config.exact_match_tolerance,
        )
        selected = ranked[0]
        selection = self.comparator.selection(selected)
        benchmark = self.benchmark_builder.build(
            problem=problem,
            selected=selected,
            candidates=tuple(candidates),
            exact_reference_energy=exact_candidate.objective_value,
            qaoa_depth=None if qaoa_result is None else qaoa_result.parameters.depth,
            tolerance=config.exact_match_tolerance,
        )
        return HybridOptimizationResult(
            problem_id=problem.problem_id,
            objective_sense=sense,
            selected_candidate=selected,
            candidates=tuple(candidates),
            comparisons=comparisons,
            selection=selection,
            benchmark_report=benchmark,
            feasibility_summary={candidate.candidate_id: candidate.feasible for candidate in candidates},
            metadata={
                "engine": "hybrid_classical_quantum",
                "candidate_count": len(candidates),
                "exact_reference_candidate_id": exact_candidate.candidate_id,
                "qaoa_candidate_id": None if qaoa_result is None else f"quantum_qaoa_{problem.problem_id}",
                "non_cheating_policy": "exact reference compared but not used to overwrite quantum candidate",
            },
        )

    def _candidate_from_solution(
        self,
        *,
        solution: QuantumSolution,
        problem: QUBOProblem | IsingProblem,
        candidate_id: str,
        candidate_type: str,
        sense: str,
        qaoa_result: QAOAResult | None = None,
    ) -> HybridCandidate:
        if not isinstance(solution, QuantumSolution):
            raise ValueError("solution must be a QuantumSolution.")
        feasible = bool(solution.feasible) and self.feasibility_checker.validate_assignment(problem, solution.assignments)
        metadata = {
            "source_solution_id": solution.solution_id,
            "source_problem_id": solution.problem_id,
            "source_solver_name": solution.solver_name,
            "validated_against_problem_id": problem.problem_id,
        }
        if qaoa_result is not None:
            metadata.update(
                {
                    "qaoa_depth": qaoa_result.parameters.depth,
                    "qaoa_expectation_value": qaoa_result.expectation_value,
                    "qaoa_empirical_expectation_value": qaoa_result.empirical_expectation_value,
                }
            )
        return HybridCandidate(
            candidate_id=candidate_id,
            candidate_type=candidate_type,
            problem_id=problem.problem_id,
            objective_value=solution.objective_value,
            feasible=feasible,
            assignment=solution.assignments,
            energy=solution.energy if solution.energy is not None else solution.objective_value,
            sense=sense,
            solver_name=solution.solver_name,
            metadata=metadata,
        )

    @staticmethod
    def _comparison_mode(problem: QUBOProblem | IsingProblem) -> str:
        if problem.metadata.get("objective_transformed_for_minimization") is True:
            return "MINIMIZE"
        if problem.metadata.get("source_problem_type") == "QUBO":
            return "MINIMIZE"
        if problem.objective.sense is ObjectiveSense.MAXIMIZE:
            return "MAXIMIZE"
        return "MINIMIZE"
