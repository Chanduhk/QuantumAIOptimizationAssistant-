from __future__ import annotations

import itertools

from backend.app.quantum.domain import IsingProblem
from backend.app.quantum.optimization.exceptions import QAOAOptimizationError
from backend.app.quantum.optimization.qaoa_models import QAOAConfig, QAOAParameterSet


class DeterministicQAOAParameterOptimizer:
    """Small bounded deterministic grid-search optimizer for QAOA parameters."""

    def candidate_parameters(self, config: QAOAConfig) -> tuple[QAOAParameterSet, ...]:
        """Return bounded candidate parameter sets without using randomness."""

        if config.parameters is not None and not config.optimize_parameters:
            return (config.parameters,)
        if not config.optimize_parameters:
            return (QAOAParameterSet(gammas=(0.0,) * config.depth, betas=(0.0,) * config.depth),)
        candidates: list[QAOAParameterSet] = []
        for values in itertools.product(config.angle_grid, repeat=2 * config.depth):
            gammas = tuple(values[: config.depth])
            betas = tuple(values[config.depth :])
            candidates.append(QAOAParameterSet(gammas=gammas, betas=betas))
            if len(candidates) >= config.max_iterations:
                break
        if not candidates:
            raise QAOAOptimizationError("no QAOA parameter candidates were generated.")
        return tuple(candidates)

    @staticmethod
    def comparison_mode(problem: IsingProblem) -> str:
        """Return whether expectation should be minimized or maximized."""

        if problem.metadata.get("source_problem_type") == "QUBO":
            if problem.metadata.get("original_objective_sense") == "MAXIMIZE":
                return "MINIMIZE"
            return "MINIMIZE"
        if problem.objective.sense.value == "MAXIMIZE":
            return "MAXIMIZE"
        return "MINIMIZE"
