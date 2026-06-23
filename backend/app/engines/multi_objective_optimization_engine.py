from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Dict, List

from backend.app.domain.multi_objective_model import OptimizationObjective, OptimizationResult
from backend.app.domain.simulation_model import SimulationResult


class MultiObjectiveOptimizationEngine:
    """Evaluate simulated futures and select the best multi-objective outcome."""

    def __init__(self, objectives: List[OptimizationObjective | Dict[str, Any]] | None = None) -> None:
        self.objectives = self._normalize_objectives(objectives) if objectives is not None else self.default_objectives()
        self.optimization_results: List[OptimizationResult] = []

    def default_objectives(self) -> List[OptimizationObjective]:
        """Return the default objective set for future selection."""
        return [
            OptimizationObjective("Productivity", 1.0, "Maximize scenario success probability."),
            OptimizationObjective("Goal Completion", 1.25, "Maximize goal completion likelihood."),
            OptimizationObjective("Milestone Completion", 1.0, "Maximize milestone completion likelihood."),
            OptimizationObjective("Risk Reduction", 1.2, "Prefer lower risk futures."),
            OptimizationObjective("Workload Balance", 0.9, "Prefer sustainable workload."),
            OptimizationObjective("Dependency Stability", 0.9, "Prefer fewer blocked dependencies."),
            OptimizationObjective("Strategic Alignment", 1.0, "Prefer high-confidence strategic outcomes."),
        ]

    def optimize(
        self,
        simulation_results: List[SimulationResult | Dict[str, Any]],
        objectives: List[OptimizationObjective | Dict[str, Any]] | None = None,
    ) -> OptimizationResult:
        """Score and rank simulated futures, returning the selected scenario."""
        simulations = self._normalize_simulations(simulation_results)
        active_objectives = self._active_objectives(objectives)
        ranking = self.rank_scenarios(simulations, active_objectives)
        selected = ranking[0]
        selected_result = selected["simulation"]
        alternatives = ranking[1:]
        tradeoffs = self._tradeoffs(selected_result, alternatives)
        recommendations = self._recommendations(selected_result, alternatives, tradeoffs)
        result = OptimizationResult(
            selected_scenario_id=selected_result.scenario_id,
            selected_scenario_name=self._scenario_name(selected_result),
            overall_score=selected["overall_score"],
            objective_scores=selected["objective_scores"],
            tradeoffs=tradeoffs,
            recommendations=recommendations,
            optimization_summary={
                "selected_future": {
                    "scenario_id": selected_result.scenario_id,
                    "scenario_name": self._scenario_name(selected_result),
                    "overall_score": selected["overall_score"],
                },
                "ranking": [
                    {
                        "rank": index,
                        "scenario_id": item["simulation"].scenario_id,
                        "scenario_name": self._scenario_name(item["simulation"]),
                        "overall_score": item["overall_score"],
                        "objective_scores": item["objective_scores"],
                    }
                    for index, item in enumerate(ranking, start=1)
                ],
                "objective_weights": {
                    objective.objective_name: objective.weight
                    for objective in active_objectives
                },
            },
        )
        self.optimization_results.append(result)
        return result

    def rank_scenarios(
        self,
        simulation_results: List[SimulationResult | Dict[str, Any]],
        objectives: List[OptimizationObjective | Dict[str, Any]] | None = None,
    ) -> List[Dict[str, Any]]:
        """Return scored scenarios from best to worst."""
        simulations = self._normalize_simulations(simulation_results)
        active_objectives = self._active_objectives(objectives)
        weighted_total = sum(objective.weight for objective in active_objectives)
        if weighted_total <= 0:
            raise ValueError("At least one enabled objective must have positive weight.")
        ranked = []
        for simulation in simulations:
            objective_scores = self.score_scenario(simulation)
            overall_score = sum(
                objective_scores[objective.objective_name] * objective.weight
                for objective in active_objectives
            ) / weighted_total
            ranked.append(
                {
                    "simulation": simulation,
                    "overall_score": round(self._bounded(overall_score, 0.0, 100.0), 2),
                    "objective_scores": objective_scores,
                }
            )
        return sorted(
            ranked,
            key=lambda item: (
                -item["overall_score"],
                item["simulation"].risk_score,
                -item["simulation"].success_probability,
                item["simulation"].scenario_id,
            ),
        )

    def score_scenario(self, simulation: SimulationResult | Dict[str, Any]) -> Dict[str, float]:
        """Return bounded objective scores for one simulation result."""
        result = self._normalize_simulations([simulation])[0]
        blocked_count = self._safe_float(result.projected_state.get("blocked_task_count", 0.0), 0.0)
        projected_state = str(result.projected_state.get("projected_goal_state", "at_risk"))
        strategic_bonus = {"on_track": 10.0, "at_risk": 0.0, "likely_delayed": -10.0}.get(projected_state, 0.0)
        return {
            "Productivity": round(result.success_probability * 100.0, 2),
            "Goal Completion": round(result.goal_completion_probability * 100.0, 2),
            "Milestone Completion": round(result.milestone_completion_probability * 100.0, 2),
            "Risk Reduction": round(100.0 - result.risk_score, 2),
            "Workload Balance": round(100.0 - result.workload_score, 2),
            "Dependency Stability": round(self._bounded(100.0 - (blocked_count * 20.0), 0.0, 100.0), 2),
            "Strategic Alignment": round(self._bounded(result.confidence_score + strategic_bonus, 0.0, 100.0), 2),
        }

    def summarize_latest_optimization(self) -> Dict[str, Any] | None:
        """Return compact selected-future summary when optimization has run."""
        if not self.optimization_results:
            return None
        latest = self.optimization_results[-1]
        return {
            "selected_future": {
                "scenario_id": latest.selected_scenario_id,
                "scenario_name": latest.selected_scenario_name,
                "overall_score": latest.overall_score,
            },
            "optimization_summary": {
                "ranking_count": len(latest.optimization_summary.get("ranking", [])),
                "tradeoff_count": len(latest.tradeoffs),
                "recommendation_count": len(latest.recommendations),
            },
        }

    def _tradeoffs(self, selected: SimulationResult, alternatives: List[Dict[str, Any]]) -> List[str]:
        tradeoffs: List[str] = []
        if selected.success_probability >= 0.7 and selected.risk_score >= 35.0:
            tradeoffs.append("Higher productivity vs higher risk")
        if selected.goal_completion_probability >= 0.7 and selected.workload_score >= 25.0:
            tradeoffs.append("Goal acceleration vs workload increase")
        if selected.projected_state.get("blocked_task_count", 0) == 0 and self._projected_days(selected) > 30:
            tradeoffs.append("Dependency safety vs slower execution")
        if selected.confidence_score >= 70.0 and selected.workload_score >= 20.0:
            tradeoffs.append("Strategic gain vs short-term effort")
        if alternatives:
            nearest = alternatives[0]["simulation"]
            if selected.risk_score > nearest.risk_score and selected.success_probability > nearest.success_probability:
                tradeoffs.append("Selected future accepts more risk for greater upside")
        return sorted(dict.fromkeys(tradeoffs)) or ["No major tradeoffs detected"]

    def _recommendations(
        self,
        selected: SimulationResult,
        alternatives: List[Dict[str, Any]],
        tradeoffs: List[str],
    ) -> List[str]:
        recommendations = [
            f"Select {self._scenario_name(selected)} because it has the strongest weighted objective score",
        ]
        if selected.risk_score >= 40.0:
            recommendations.append("Mitigate major risks before execution")
        if selected.workload_score >= 30.0:
            recommendations.append("Reduce workload pressure before committing")
        if selected.projected_state.get("blocked_task_count", 0):
            recommendations.append("Resolve dependency blockers before starting the selected path")
        if alternatives:
            recommendations.append(
                f"{self._scenario_name(alternatives[-1]['simulation'])} ranked lowest due to weaker objective balance"
            )
        if tradeoffs and tradeoffs != ["No major tradeoffs detected"]:
            recommendations.append("Review tradeoffs with the user before locking the plan")
        return sorted(dict.fromkeys(recommendations))

    def _active_objectives(
        self,
        objectives: List[OptimizationObjective | Dict[str, Any]] | None,
    ) -> List[OptimizationObjective]:
        normalized = self._normalize_objectives(objectives) if objectives is not None else list(self.objectives)
        active = [objective for objective in normalized if objective.enabled]
        if not active:
            raise ValueError("At least one objective must be enabled.")
        return active

    def _normalize_objectives(
        self,
        objectives: List[OptimizationObjective | Dict[str, Any]],
    ) -> List[OptimizationObjective]:
        if not isinstance(objectives, list):
            raise ValueError("objectives must be a list.")
        normalized = [
            objective if isinstance(objective, OptimizationObjective) else OptimizationObjective(**objective)
            for objective in objectives
        ]
        supported = set(self.score_scenario(self._neutral_simulation()).keys())
        for objective in normalized:
            if objective.objective_name not in supported:
                raise ValueError(f"Unsupported objective: {objective.objective_name}")
        return normalized

    def _normalize_simulations(
        self,
        simulation_results: List[SimulationResult | Dict[str, Any]],
    ) -> List[SimulationResult]:
        if not isinstance(simulation_results, list):
            raise ValueError("simulation_results must be a list.")
        if not simulation_results:
            raise ValueError("At least one simulation result is required.")
        simulations = [
            simulation if isinstance(simulation, SimulationResult) else SimulationResult(**simulation)
            for simulation in simulation_results
        ]
        seen_ids = set()
        for simulation in simulations:
            if simulation.scenario_id in seen_ids:
                raise ValueError("simulation scenario ids must be unique.")
            seen_ids.add(simulation.scenario_id)
        return simulations

    def _neutral_simulation(self) -> SimulationResult:
        return SimulationResult(
            scenario_id="neutral",
            success_probability=0.5,
            goal_completion_probability=0.5,
            milestone_completion_probability=0.5,
            workload_score=50.0,
            risk_score=50.0,
            confidence_score=50.0,
            projected_state={"projected_goal_state": "at_risk", "blocked_task_count": 0},
            recommendations=[],
        )

    def _scenario_name(self, simulation: SimulationResult) -> str:
        scenario_type = str(simulation.projected_state.get("scenario_type") or simulation.scenario_id)
        return scenario_type.replace("_", " ").title()

    def _projected_days(self, simulation: SimulationResult) -> float:
        return self._safe_float(simulation.projected_state.get("projected_completion_days", 0.0), 0.0)

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        return number

    def _bounded(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))
