from __future__ import annotations

import math
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List


class ExecutiveCognitiveBrain:
    """High-level deterministic coordinator for existing intelligence engines.

    The executive brain performs no standalone AI work. It validates and coordinates
    existing engines into one executive planning response.
    """

    OUTPUT_KEYS = {
        "executive_context",
        "executive_objectives",
        "candidate_plans",
        "recommended_plan",
        "future_analysis",
        "tradeoff_analysis",
        "risk_summary",
        "executive_summary",
        "explanations",
        "reflection",
    }

    def __init__(
        self,
        *,
        context_engine: Any | None = None,
        context_awareness_engine: Any | None = None,
        behavior_learning_engine: Any | None = None,
        adaptive_life_operating_system: Any | None = None,
        meta_cognitive_engine: Any | None = None,
        goal_intelligence_engine: Any | None = None,
        dependency_intelligence_engine: Any | None = None,
        personal_knowledge_engine: Any | None = None,
        behavior_engine: Any | None = None,
        prediction_engine: Any | None = None,
        decision_engine: Any | None = None,
        planning_engine: Any | None = None,
        scheduling_engine: Any | None = None,
        optimization_engine: Any | None = None,
        strategic_planning_engine: Any | None = None,
        future_simulation_engine: Any | None = None,
        multi_objective_optimization_engine: Any | None = None,
        decision_intelligence_engine: Any | None = None,
        conversational_intelligence_engine: Any | None = None,
    ) -> None:
        self.context_engine = context_engine
        self.context_awareness_engine = context_awareness_engine
        self.behavior_learning_engine = behavior_learning_engine
        self.adaptive_life_operating_system = adaptive_life_operating_system
        self.meta_cognitive_engine = meta_cognitive_engine
        self.goal_intelligence_engine = goal_intelligence_engine
        self.dependency_intelligence_engine = dependency_intelligence_engine
        self.personal_knowledge_engine = personal_knowledge_engine
        self.behavior_engine = behavior_engine
        self.prediction_engine = prediction_engine
        self.decision_engine = decision_engine
        self.planning_engine = planning_engine
        self.scheduling_engine = scheduling_engine
        self.optimization_engine = optimization_engine
        self.strategic_planning_engine = strategic_planning_engine
        self.future_simulation_engine = future_simulation_engine
        self.multi_objective_optimization_engine = multi_objective_optimization_engine
        self.decision_intelligence_engine = decision_intelligence_engine
        self.conversational_intelligence_engine = conversational_intelligence_engine
        self.latest_result: Dict[str, Any] | None = None

    @classmethod
    def from_orchestrator(cls, orchestrator: Any) -> "ExecutiveCognitiveBrain":
        """Create a coordinator wired to an existing AIOrchestrator instance."""
        return cls(
            context_engine=getattr(orchestrator, "context_engine", None),
            context_awareness_engine=getattr(orchestrator, "context_awareness_engine", None),
            behavior_learning_engine=getattr(orchestrator, "behavior_learning_engine", None),
            adaptive_life_operating_system=getattr(orchestrator, "adaptive_life_operating_system", None),
            meta_cognitive_engine=getattr(orchestrator, "meta_cognitive_engine", None),
            goal_intelligence_engine=getattr(orchestrator, "goal_intelligence_engine", None),
            dependency_intelligence_engine=getattr(orchestrator, "dependency_intelligence_engine", None),
            personal_knowledge_engine=getattr(orchestrator, "personal_knowledge_engine", None),
            behavior_engine=getattr(orchestrator, "behavior_engine", None),
            prediction_engine=getattr(orchestrator, "prediction_engine", None),
            decision_engine=getattr(orchestrator, "decision_engine", None),
            planning_engine=getattr(orchestrator, "planning_engine", None),
            scheduling_engine=getattr(orchestrator, "scheduling_engine", None),
            optimization_engine=getattr(orchestrator, "optimization_engine", None),
            strategic_planning_engine=getattr(orchestrator, "strategic_planning_engine", None),
            future_simulation_engine=getattr(orchestrator, "future_simulation_engine", None),
            multi_objective_optimization_engine=getattr(orchestrator, "multi_objective_optimization_engine", None),
            decision_intelligence_engine=getattr(orchestrator, "decision_intelligence_engine", None),
            conversational_intelligence_engine=getattr(orchestrator, "conversational_intelligence_engine", None),
        )

    def execute_planning_request(
        self,
        tasks: List[Dict[str, Any]],
        *,
        user_id: int | None = None,
        behavior_patterns: Dict[str, Any] | None = None,
        goals: List[Dict[str, Any]] | None = None,
        query: str | None = None,
    ) -> Dict[str, Any]:
        """Execute the executive coordination pipeline and return one result object."""
        task_list = self._task_list(tasks)
        behavior_patterns = self._dict({} if behavior_patterns is None else behavior_patterns, "behavior_patterns")
        goals = self._dict_list([] if goals is None else goals, "goals")

        executive_context = self._collect_context(
            task_list,
            user_id=user_id,
            behavior_patterns=behavior_patterns,
            query=query,
        )
        executive_objectives = self._understand_objectives(task_list, goals)
        decision_state = self._evaluate_current_situation(task_list, behavior_patterns)
        candidate_plans = self._build_candidate_plans(decision_state["recommended_task_order"], behavior_patterns)
        future_analysis = self._strategic_evaluation(
            decision_state["recommended_task_order"],
            behavior_patterns,
            candidate_plans,
        )
        recommended_plan = self._executive_decision(
            candidate_plans,
            future_analysis,
            executive_context,
            executive_objectives,
        )
        tradeoff_analysis = self._tradeoff_analysis(recommended_plan)
        risk_summary = self._risk_summary(executive_context, future_analysis, recommended_plan)
        explanations = self._explain_everything(
            recommended_plan,
            tradeoff_analysis,
            risk_summary,
            future_analysis,
        )
        reflection = self._reflect(executive_context, recommended_plan)
        executive_summary = self._executive_summary(recommended_plan, risk_summary, future_analysis)

        result = {
            "executive_context": executive_context,
            "executive_objectives": executive_objectives,
            "candidate_plans": candidate_plans,
            "recommended_plan": recommended_plan,
            "future_analysis": future_analysis,
            "tradeoff_analysis": tradeoff_analysis,
            "risk_summary": risk_summary,
            "executive_summary": executive_summary,
            "explanations": explanations,
            "reflection": reflection,
        }
        self._validate_executive_result(result)
        self.latest_result = result
        return result

    def summarize_executive_brain(self) -> Dict[str, Any] | None:
        """Return compact orchestrator-ready summary only after execution."""
        if self.latest_result is None:
            return None
        recommended = self.latest_result["recommended_plan"]
        risk_summary = self.latest_result["risk_summary"]
        return {
            "recommended_option_id": recommended.get("option_id"),
            "recommended_title": recommended.get("title"),
            "overall_score": recommended.get("overall_score", 0.0),
            "risk_level": risk_summary.get("risk_level", "unknown"),
            "candidate_plan_count": len(self.latest_result["candidate_plans"].get("plans", [])),
            "future_count": len(self.latest_result["future_analysis"].get("ranked_futures", [])),
        }

    def _collect_context(
        self,
        tasks: List[Dict[str, Any]],
        *,
        user_id: int | None,
        behavior_patterns: Dict[str, Any],
        query: str | None,
    ) -> Dict[str, Any]:
        context = {"current_tasks": tasks, "behavior_patterns": behavior_patterns}
        build_context = getattr(self.context_engine, "build_context", None)
        if callable(build_context) and user_id is not None:
            context = build_context(
                user_id=user_id,
                behavior_patterns=behavior_patterns,
                current_tasks=tasks,
                query=query,
            )
            self._require_dict(context, "context_engine output")
        learning_summary = self._optional_summary(self.behavior_learning_engine, "summarize_behavior_learning", "behavior_learning")
        adaptive_summary = self._optional_summary(self.adaptive_life_operating_system, "summarize_adaptive_life", "adaptive_life")
        meta_summary = self._optional_summary(self.meta_cognitive_engine, "summarize_meta_cognition", "meta_cognitive")
        context_snapshot = None
        generate_snapshot = getattr(self.context_awareness_engine, "generate_snapshot", None)
        if callable(generate_snapshot):
            context_snapshot = self._serializable(
                generate_snapshot(
                    current_context=context,
                    workload=self._workload(tasks),
                    goals=[],
                    behavior_learning_summary=(learning_summary or {}).get("behavior_learning_summary", {}),
                    adaptive_life_summary=adaptive_summary or {},
                    meta_cognitive_summary=meta_summary or {},
                )
            )
            self._require_dict(context_snapshot, "context snapshot")
        return {
            "context": context,
            "context_snapshot": context_snapshot,
            "behavior_learning": learning_summary,
            "adaptive_life": adaptive_summary,
            "meta_cognitive": meta_summary,
        }

    def _understand_objectives(self, tasks: List[Dict[str, Any]], goals: List[Dict[str, Any]]) -> Dict[str, Any]:
        goal_state = self._call_optional(self.goal_intelligence_engine, "prioritize_goals", [], "goal state")
        dependency_state = self._call_optional(
            self.dependency_intelligence_engine,
            "analyze_dependencies",
            [tasks],
            "dependency state",
        )
        knowledge_state = self._optional_summary(self.personal_knowledge_engine, "summarize_personal_knowledge", "personal_knowledge")
        return {
            "goals": goals,
            "goal_state": goal_state,
            "dependency_state": dependency_state,
            "knowledge_state": knowledge_state,
        }

    def _evaluate_current_situation(self, tasks: List[Dict[str, Any]], behavior_patterns: Dict[str, Any]) -> Dict[str, Any]:
        if not behavior_patterns and callable(getattr(self.behavior_engine, "get_user_patterns", None)):
            behavior_patterns = self.behavior_engine.get_user_patterns()
            self._require_dict(behavior_patterns, "behavior patterns")
        predicted_tasks = tasks
        predict_batch = getattr(self.prediction_engine, "predict_batch", None)
        if callable(predict_batch):
            predicted_tasks = predict_batch(self.behavior_engine, tasks, behavior_patterns)
            self._require_task_list(predicted_tasks, "predicted_tasks")
        recommended_order = predicted_tasks
        prioritize = getattr(self.decision_engine, "prioritize_tasks", None)
        if callable(prioritize):
            recommended_order = prioritize(tasks, predicted_tasks, behavior_patterns)
            self._require_task_list(recommended_order, "recommended_task_order")
        return {
            "behavior_patterns": behavior_patterns,
            "predicted_tasks": predicted_tasks,
            "recommended_task_order": recommended_order,
        }

    def _build_candidate_plans(self, tasks: List[Dict[str, Any]], behavior_patterns: Dict[str, Any]) -> Dict[str, Any]:
        plans: List[Dict[str, Any]] = []
        generate_daily_plan = getattr(self.planning_engine, "generate_daily_plan", None)
        if callable(generate_daily_plan):
            daily_plan = generate_daily_plan(tasks, behavior_patterns)
            self._require_dict(daily_plan, "daily plan")
            plans.append({"plan_type": "daily_plan", "plan": daily_plan})
        generate_schedule = getattr(self.scheduling_engine, "generate_schedule", None)
        if not callable(generate_schedule):
            generate_schedule = getattr(self.scheduling_engine, "optimize_schedule", None)
        if callable(generate_schedule):
            schedule = generate_schedule(tasks, behavior_patterns)
            self._require_schedule(schedule, "schedule")
            plans.append({"plan_type": "schedule", "plan": schedule})
        optimize_schedule = getattr(self.optimization_engine, "optimize_schedule", None)
        if callable(optimize_schedule):
            optimized = optimize_schedule(tasks, behavior_patterns)
            self._require_dict(optimized, "optimization output")
            plans.append({"plan_type": "optimized_schedule", "plan": optimized})
        if not plans:
            plans.append({"plan_type": "task_order", "plan": {"tasks": tasks}})
        return {"plans": plans}

    def _strategic_evaluation(
        self,
        tasks: List[Dict[str, Any]],
        behavior_patterns: Dict[str, Any],
        candidate_plans: Dict[str, Any],
    ) -> Dict[str, Any]:
        strategic_plan = self._call_optional(
            self.strategic_planning_engine,
            "recommend_next_week",
            [tasks, behavior_patterns],
            "strategic plan",
        )
        simulation_result = self._call_optional(
            self.future_simulation_engine,
            "simulate_baseline",
            [tasks, behavior_patterns],
            "simulation result",
        )
        futures = []
        if simulation_result is not None:
            futures.append(simulation_result)
        ranked_futures = futures
        optimize = getattr(self.multi_objective_optimization_engine, "optimize", None)
        if callable(optimize) and futures:
            ranked = optimize(futures)
            ranked_futures = [self._serializable(ranked)]
            self._require_dict(ranked_futures[0], "multi-objective optimization")
        return {
            "strategic_plan": strategic_plan,
            "simulation": simulation_result,
            "ranked_futures": ranked_futures,
            "candidate_plan_count": len(candidate_plans.get("plans", [])),
        }

    def _executive_decision(
        self,
        candidate_plans: Dict[str, Any],
        future_analysis: Dict[str, Any],
        executive_context: Dict[str, Any],
        executive_objectives: Dict[str, Any],
    ) -> Dict[str, Any]:
        options = self._decision_options(candidate_plans)
        analyze = getattr(self.decision_intelligence_engine, "analyze_decisions", None)
        if callable(analyze):
            analysis = analyze(
                options,
                goals=executive_objectives.get("goals", []),
                dependencies=executive_objectives.get("dependency_state") or {},
                context=executive_context.get("context_snapshot") or {},
                simulations=[future_analysis["simulation"]] if isinstance(future_analysis.get("simulation"), dict) else [],
                optimization_results=self._first_future(future_analysis),
                risks=[],
                momentum=(executive_context.get("context_snapshot") or {}),
                learning_insights=((executive_context.get("behavior_learning") or {}).get("behavior_insights", [])),
            )
            analysis_dict = self._serializable(analysis)
            self._require_dict(analysis_dict, "decision analysis")
            recommendations = analysis_dict.get("recommendations", [])
            if not isinstance(recommendations, list) or not recommendations:
                raise ValueError("decision analysis must include recommendations.")
            best = recommendations[0]
            self._require_dict(best, "decision recommendation")
            return {
                "option_id": best.get("option_id"),
                "title": best.get("title"),
                "reasoning": best.get("reasoning"),
                "overall_score": self._evaluation_score(analysis_dict, best.get("option_id")),
                "decision_analysis": analysis_dict,
            }
        first = options[0]
        return {
            "option_id": first["option_id"],
            "title": first["title"],
            "reasoning": "Selected first validated candidate plan.",
            "overall_score": 50.0,
            "decision_analysis": None,
        }

    def _tradeoff_analysis(self, recommended_plan: Dict[str, Any]) -> Dict[str, Any]:
        analysis = recommended_plan.get("decision_analysis") or {}
        tradeoffs = analysis.get("tradeoffs", []) if isinstance(analysis, dict) else []
        if not isinstance(tradeoffs, list):
            raise ValueError("decision tradeoffs must be a list.")
        return {"tradeoffs": tradeoffs, "tradeoff_count": len(tradeoffs)}

    def _risk_summary(
        self,
        executive_context: Dict[str, Any],
        future_analysis: Dict[str, Any],
        recommended_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        analysis = recommended_plan.get("decision_analysis")
        evaluations = analysis.get("evaluations", []) if isinstance(analysis, dict) else []
        if evaluations and isinstance(evaluations[0], dict):
            risk_score = self._safe_float(evaluations[0].get("risk_score"), 0.0)
        else:
            risk_score = 0.0
        simulation = future_analysis.get("simulation")
        if isinstance(simulation, dict):
            risk_score = max(risk_score, self._safe_float(simulation.get("risk_score"), 0.0))
        snapshot = executive_context.get("context_snapshot")
        if isinstance(snapshot, dict):
            risk_state = snapshot.get("risk_state")
        else:
            risk_state = None
        return {
            "risk_score": round(risk_score, 2),
            "risk_level": risk_state or self._risk_level(risk_score),
        }

    def _explain_everything(
        self,
        recommended_plan: Dict[str, Any],
        tradeoff_analysis: Dict[str, Any],
        risk_summary: Dict[str, Any],
        future_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        conversational = self.conversational_intelligence_engine
        explanations = {
            "executive_summary": f"Recommended {recommended_plan.get('title')} with score {recommended_plan.get('overall_score')}.",
            "decision_explanation": recommended_plan.get("reasoning"),
            "tradeoff_explanation": f"{tradeoff_analysis.get('tradeoff_count', 0)} tradeoffs were identified.",
            "risk_explanation": f"Risk level is {risk_summary.get('risk_level')}.",
            "strategic_explanation": "Strategic futures were evaluated when simulation and optimization engines were available.",
        }
        explain_risk = getattr(conversational, "explain_risk", None)
        if callable(explain_risk):
            risk = self._serializable(explain_risk(risk_summary))
            self._require_dict(risk, "risk explanation")
            explanations["risk_explanation"] = risk
        explain_optimization = getattr(conversational, "explain_optimization", None)
        if callable(explain_optimization) and future_analysis.get("ranked_futures"):
            optimization = self._serializable(explain_optimization({"selected_future": recommended_plan, "tradeoffs": tradeoff_analysis.get("tradeoffs", [])}))
            self._require_dict(optimization, "optimization explanation")
            explanations["tradeoff_explanation"] = optimization
        self._require_dict(explanations, "explanations")
        return explanations

    def _reflect(self, executive_context: Dict[str, Any], recommended_plan: Dict[str, Any]) -> Dict[str, Any]:
        meta = self._optional_summary(self.meta_cognitive_engine, "summarize_meta_cognition", "reflection meta")
        adaptive = self._optional_summary(self.adaptive_life_operating_system, "summarize_adaptive_life", "reflection adaptive")
        learning = self._optional_summary(self.behavior_learning_engine, "summarize_behavior_learning", "reflection learning")
        return {
            "meta_cognitive": meta,
            "adaptive_life": adaptive,
            "behavior_learning": learning,
            "recommended_option_id": recommended_plan.get("option_id"),
            "context_available": bool(executive_context.get("context")),
        }

    def _executive_summary(
        self,
        recommended_plan: Dict[str, Any],
        risk_summary: Dict[str, Any],
        future_analysis: Dict[str, Any],
    ) -> str:
        summary = (
            f"Executive recommendation: {recommended_plan.get('title')} "
            f"(score {recommended_plan.get('overall_score')}, risk {risk_summary.get('risk_level')})."
        )
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("executive summary must be a non-empty string.")
        return summary

    def _decision_options(self, candidate_plans: Dict[str, Any]) -> List[Dict[str, Any]]:
        plans = candidate_plans.get("plans")
        if not isinstance(plans, list) or not plans:
            raise ValueError("candidate_plans must include a non-empty plans list.")
        options = []
        for index, plan in enumerate(plans, start=1):
            self._require_dict(plan, "candidate plan")
            plan_type = str(plan.get("plan_type", f"plan-{index}"))
            options.append(
                {
                    "option_id": f"candidate-{index}",
                    "title": plan_type.replace("_", " ").title(),
                    "description": plan_type,
                    "expected_benefit": 70.0 if "optimized" in plan_type else 60.0,
                    "estimated_cost": 20.0,
                    "estimated_effort": 30.0,
                    "metadata": {"plan_type": plan_type},
                }
            )
        return options

    def _optional_summary(self, engine: Any, method_name: str, field_name: str) -> Dict[str, Any] | None:
        method = getattr(engine, method_name, None)
        if not callable(method):
            return None
        value = method()
        if value is None:
            return None
        value = self._serializable(value)
        self._require_dict(value, field_name)
        return value

    def _call_optional(self, engine: Any, method_name: str, args: List[Any], field_name: str) -> Any:
        method = getattr(engine, method_name, None)
        if not callable(method):
            return None
        value = self._serializable(method(*args))
        if not isinstance(value, (dict, list)):
            raise ValueError(f"{field_name} must be a dictionary or list.")
        self._validate_numeric_payload(value, field_name)
        return value

    def _first_future(self, future_analysis: Dict[str, Any]) -> Dict[str, Any]:
        futures = future_analysis.get("ranked_futures", [])
        return futures[0] if isinstance(futures, list) and futures and isinstance(futures[0], dict) else {}

    def _evaluation_score(self, analysis: Dict[str, Any], option_id: Any) -> float:
        evaluations = analysis.get("evaluations", [])
        if isinstance(evaluations, list):
            for evaluation in evaluations:
                if isinstance(evaluation, dict) and evaluation.get("option_id") == option_id:
                    return self._safe_float(evaluation.get("overall_score"), 0.0)
        return 0.0

    def _workload(self, tasks: List[Dict[str, Any]]) -> Dict[str, float]:
        return {
            "available_capacity": 8.0,
            "projected_workload": round(sum(self._safe_float(task.get("estimated_duration", task.get("duration")), 1.0) for task in tasks), 2),
        }

    def _validate_executive_result(self, result: Dict[str, Any]) -> None:
        if set(result) != self.OUTPUT_KEYS:
            raise ValueError("executive brain result has invalid output keys.")
        for key in self.OUTPUT_KEYS - {"executive_summary"}:
            if not isinstance(result[key], dict):
                raise ValueError(f"{key} must be a dictionary.")
        if not isinstance(result["executive_summary"], str) or not result["executive_summary"].strip():
            raise ValueError("executive_summary must be a non-empty string.")
        self._validate_numeric_payload(result, "executive brain result")

    def _require_schedule(self, value: Any, field_name: str) -> None:
        if not isinstance(value, (dict, list)):
            raise ValueError(f"{field_name} must be a dictionary or list.")
        self._validate_numeric_payload(value, field_name)

    def _require_task_list(self, value: Any, field_name: str) -> None:
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise ValueError(f"{field_name} must be a list of dictionaries.")
        self._validate_numeric_payload(value, field_name)

    def _task_list(self, tasks: Any) -> List[Dict[str, Any]]:
        if not isinstance(tasks, list):
            raise ValueError("tasks must be a list of dictionaries.")
        if any(not isinstance(task, dict) for task in tasks):
            raise ValueError("tasks must be a list of dictionaries.")
        return [dict(task) for task in tasks]

    def _dict_list(self, value: Any, field_name: str) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list of dictionaries.")
        if any(not isinstance(item, dict) for item in value):
            raise ValueError(f"{field_name} entries must be dictionaries.")
        return [dict(item) for item in value]

    def _dict(self, value: Any, field_name: str) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        return dict(value)

    def _require_dict(self, value: Any, field_name: str) -> None:
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} must be a dictionary.")
        self._validate_numeric_payload(value, field_name)

    def _serializable(self, value: Any) -> Any:
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, list):
            return [self._serializable(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serializable(item) for key, item in value.items()}
        return value

    def _validate_numeric_payload(self, payload: Any, field_name: str) -> None:
        if isinstance(payload, dict):
            for value in payload.values():
                self._validate_numeric_payload(value, field_name)
            return
        if isinstance(payload, list):
            for value in payload:
                self._validate_numeric_payload(value, field_name)
            return
        if isinstance(payload, bool) or payload is None or isinstance(payload, str):
            return
        if isinstance(payload, (int, float)) and not math.isfinite(float(payload)):
            raise ValueError(f"{field_name} contains non-finite numeric value.")

    def _safe_float(self, value: Any, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(number):
            return default
        return number

    def _risk_level(self, risk_score: float) -> str:
        if risk_score >= 75.0:
            return "critical"
        if risk_score >= 50.0:
            return "high"
        if risk_score >= 25.0:
            return "medium"
        return "low"
