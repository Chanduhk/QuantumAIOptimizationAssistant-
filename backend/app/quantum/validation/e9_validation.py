from __future__ import annotations

import itertools
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from backend.app.orchestrator.executive_cognitive_brain import ExecutiveCognitiveBrain
from backend.app.quantum.baseline import ExactClassicalSolver
from backend.app.quantum.domain import IsingProblem, ObjectiveSense, QUBOProblem
from backend.app.quantum.formulation import IsingToQUBOConverter, QUBOToIsingConverter
from backend.app.quantum.hybrid import HybridOptimizationEngine
from backend.app.quantum.integration import AIQuantumIntegrationConfig, AIQuantumIntegrationEngine
from backend.app.quantum.optimization import QAOAConfig
from backend.app.quantum.optimization.qaoa_circuit import QAOACircuitBuilder
from backend.app.quantum.optimization.qaoa_cost import QAOACostEvaluator
from backend.app.quantum.optimization.qaoa_engine import QAOAEngine

ENERGY_TOLERANCE = 1e-9
DEFAULT_BENCHMARK_MAX_VARIABLES = 8


@dataclass(frozen=True)
class E9BenchmarkCase:
    """Immutable E.9 validation case using an existing quantum problem."""

    case_id: str
    problem: QUBOProblem | IsingProblem
    qaoa_config: QAOAConfig = field(default_factory=lambda: QAOAConfig(shots=256, seed=123))
    integration_config: AIQuantumIntegrationConfig = field(default_factory=AIQuantumIntegrationConfig)
    tasks: tuple[Mapping[str, Any], ...] = (
        {
            "id": "e9-task-1",
            "title": "Validate quantum optimization evidence",
            "task_type": "validation",
            "priority": 4,
            "estimated_duration": 1.0,
            "goal_id": "e9-goal",
        },
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _safe_text(self.case_id, "case_id"))
        if not isinstance(self.problem, (QUBOProblem, IsingProblem)):
            raise ValueError("problem must be a QUBOProblem or IsingProblem.")
        if not isinstance(self.qaoa_config, QAOAConfig):
            raise ValueError("qaoa_config must be a QAOAConfig.")
        if not isinstance(self.integration_config, AIQuantumIntegrationConfig):
            raise ValueError("integration_config must be an AIQuantumIntegrationConfig.")
        if not isinstance(self.tasks, tuple) or not self.tasks:
            raise ValueError("tasks must be a non-empty tuple.")
        frozen_tasks = []
        for task in self.tasks:
            if not isinstance(task, Mapping):
                raise ValueError("tasks must contain mappings.")
            frozen_tasks.append(_freeze_mapping(task))
        object.__setattr__(self, "tasks", tuple(frozen_tasks))


@dataclass(frozen=True)
class E9BenchmarkResult:
    """Immutable benchmark and verification result for one E.9 case."""

    case_id: str
    problem_id: str
    problem_type: str
    variable_count: int
    constraint_count: int
    objective_sense: str
    classical_exact_energy: float
    independent_exact_energy: float
    quantum_candidate_energy: float | None
    selected_energy: float | None
    absolute_gap: float | None
    relative_gap: float | None
    exact_match: bool | None
    selected_solver: str | None
    selected_candidate_type: str | None
    feasible: bool | None
    quantum_used: bool
    classical_used: bool
    execution_path: str
    qaoa_depth: int
    qaoa_shots: int
    exact_runtime_ms: float
    qaoa_runtime_ms: float | None
    hybrid_runtime_ms: float | None
    integration_runtime_ms: float
    executive_runtime_ms: float
    math_verified: bool
    executive_quantum_present: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _safe_text(self.case_id, "case_id"))
        object.__setattr__(self, "problem_id", _safe_text(self.problem_id, "problem_id"))
        if self.problem_type not in {"QUBO", "Ising"}:
            raise ValueError("problem_type must be QUBO or Ising.")
        object.__setattr__(self, "variable_count", _non_negative_int(self.variable_count, "variable_count"))
        object.__setattr__(self, "constraint_count", _non_negative_int(self.constraint_count, "constraint_count"))
        if self.objective_sense not in {"MINIMIZE", "MAXIMIZE"}:
            raise ValueError("objective_sense must be MINIMIZE or MAXIMIZE.")
        for field_name in (
            "classical_exact_energy",
            "independent_exact_energy",
            "exact_runtime_ms",
            "integration_runtime_ms",
            "executive_runtime_ms",
        ):
            object.__setattr__(self, field_name, _finite(getattr(self, field_name), field_name))
        for field_name in ("quantum_candidate_energy", "selected_energy", "absolute_gap", "relative_gap", "qaoa_runtime_ms", "hybrid_runtime_ms"):
            value = getattr(self, field_name)
            if value is not None:
                parsed = _finite(value, field_name)
                if field_name in {"absolute_gap", "relative_gap"} and parsed < -ENERGY_TOLERANCE:
                    raise ValueError(f"{field_name} cannot be negative.")
                object.__setattr__(self, field_name, max(0.0, parsed) if field_name in {"absolute_gap", "relative_gap"} else parsed)
        if self.exact_match is not None and not isinstance(self.exact_match, bool):
            raise ValueError("exact_match must be a boolean or None.")
        if self.selected_solver is not None:
            object.__setattr__(self, "selected_solver", _safe_text(self.selected_solver, "selected_solver"))
        if self.selected_candidate_type is not None:
            object.__setattr__(self, "selected_candidate_type", _safe_text(self.selected_candidate_type, "selected_candidate_type"))
        if self.feasible is not None and not isinstance(self.feasible, bool):
            raise ValueError("feasible must be a boolean or None.")
        for field_name in ("quantum_used", "classical_used", "math_verified", "executive_quantum_present"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean.")
        object.__setattr__(self, "execution_path", _safe_text(self.execution_path, "execution_path"))
        object.__setattr__(self, "qaoa_depth", _positive_int(self.qaoa_depth, "qaoa_depth"))
        object.__setattr__(self, "qaoa_shots", _positive_int(self.qaoa_shots, "qaoa_shots"))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly benchmark result."""

        return {
            "case_id": self.case_id,
            "problem_id": self.problem_id,
            "problem_type": self.problem_type,
            "variable_count": self.variable_count,
            "constraint_count": self.constraint_count,
            "objective_sense": self.objective_sense,
            "classical_exact_energy": self.classical_exact_energy,
            "independent_exact_energy": self.independent_exact_energy,
            "quantum_candidate_energy": self.quantum_candidate_energy,
            "selected_energy": self.selected_energy,
            "absolute_gap": self.absolute_gap,
            "relative_gap": self.relative_gap,
            "exact_match": self.exact_match,
            "selected_solver": self.selected_solver,
            "selected_candidate_type": self.selected_candidate_type,
            "feasible": self.feasible,
            "quantum_used": self.quantum_used,
            "classical_used": self.classical_used,
            "execution_path": self.execution_path,
            "qaoa_depth": self.qaoa_depth,
            "qaoa_shots": self.qaoa_shots,
            "exact_runtime_ms": self.exact_runtime_ms,
            "qaoa_runtime_ms": self.qaoa_runtime_ms,
            "hybrid_runtime_ms": self.hybrid_runtime_ms,
            "integration_runtime_ms": self.integration_runtime_ms,
            "executive_runtime_ms": self.executive_runtime_ms,
            "math_verified": self.math_verified,
            "executive_quantum_present": self.executive_quantum_present,
            "metadata": _thaw_mapping(self.metadata),
        }


@dataclass(frozen=True)
class E9ArchitectureAudit:
    """Immutable source-level audit summary for the quantum stack."""

    forbidden_import_findings: tuple[str, ...]
    anti_cheating_findings: tuple[str, ...]
    architecture_findings: tuple[str, ...]
    passed: bool

    def __post_init__(self) -> None:
        for field_name in ("forbidden_import_findings", "anti_cheating_findings", "architecture_findings"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple):
                raise ValueError(f"{field_name} must be a tuple.")
            object.__setattr__(self, field_name, tuple(_safe_text(value, field_name) for value in values))
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a boolean.")


@dataclass(frozen=True)
class E9ValidationReport:
    """Immutable aggregate E.9 validation report."""

    benchmark_results: tuple[E9BenchmarkResult, ...]
    architecture_audit: E9ArchitectureAudit
    determinism_verified: bool
    failure_checks: Mapping[str, str]
    summary: str

    def __post_init__(self) -> None:
        if not isinstance(self.benchmark_results, tuple) or not self.benchmark_results:
            raise ValueError("benchmark_results must be a non-empty tuple.")
        if any(not isinstance(result, E9BenchmarkResult) for result in self.benchmark_results):
            raise ValueError("benchmark_results must contain E9BenchmarkResult instances.")
        if not isinstance(self.architecture_audit, E9ArchitectureAudit):
            raise ValueError("architecture_audit must be an E9ArchitectureAudit.")
        if not isinstance(self.determinism_verified, bool):
            raise ValueError("determinism_verified must be a boolean.")
        if not isinstance(self.failure_checks, Mapping) or not self.failure_checks:
            raise ValueError("failure_checks must be a non-empty mapping.")
        object.__setattr__(self, "failure_checks", _freeze_mapping(self.failure_checks))
        object.__setattr__(self, "summary", _safe_text(self.summary, "summary"))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly validation report."""

        return {
            "benchmark_results": [result.to_dict() for result in self.benchmark_results],
            "architecture_audit": {
                "forbidden_import_findings": list(self.architecture_audit.forbidden_import_findings),
                "anti_cheating_findings": list(self.architecture_audit.anti_cheating_findings),
                "architecture_findings": list(self.architecture_audit.architecture_findings),
                "passed": self.architecture_audit.passed,
            },
            "determinism_verified": self.determinism_verified,
            "failure_checks": _thaw_mapping(self.failure_checks),
            "summary": self.summary,
        }


class E9QuantumValidationHarness:
    """Validate and benchmark E.1-E.8 using independent deterministic checks."""

    def __init__(
        self,
        *,
        exact_solver: ExactClassicalSolver | None = None,
        qaoa_engine: QAOAEngine | None = None,
        hybrid_engine: HybridOptimizationEngine | None = None,
        integration_engine: AIQuantumIntegrationEngine | None = None,
        executive_brain: ExecutiveCognitiveBrain | None = None,
    ) -> None:
        self.exact_solver = exact_solver or ExactClassicalSolver()
        self.qaoa_engine = qaoa_engine or QAOAEngine()
        self.hybrid_engine = hybrid_engine or HybridOptimizationEngine()
        self.integration_engine = integration_engine or AIQuantumIntegrationEngine()
        self.executive_brain = executive_brain or ExecutiveCognitiveBrain()
        self.qubo_to_ising = QUBOToIsingConverter()
        self.ising_to_qubo = IsingToQUBOConverter()

    def independent_qubo_energy(self, problem: QUBOProblem, assignment: Mapping[str, int]) -> float:
        """Evaluate QUBO energy independently from E.3 and E.6."""

        if not isinstance(problem, QUBOProblem):
            raise ValueError("problem must be a QUBOProblem.")
        energy = float(problem.constant_offset)
        variable_ids = {variable.variable_id for variable in problem.variables}
        if set(assignment) != variable_ids:
            raise ValueError("assignment must exactly match QUBO variables.")
        for variable_id in sorted(variable_ids):
            _binary_value(assignment[variable_id], variable_id)
        for variable_id in sorted(problem.linear_coefficients):
            energy += problem.linear_coefficients[variable_id] * int(assignment[variable_id])
        for left, right in sorted(problem.quadratic_coefficients):
            energy += problem.quadratic_coefficients[(left, right)] * int(assignment[left]) * int(assignment[right])
        return energy

    def independent_ising_energy(self, problem: IsingProblem, assignment: Mapping[str, int]) -> float:
        """Evaluate Ising energy independently using binary assignment to spin mapping."""

        if not isinstance(problem, IsingProblem):
            raise ValueError("problem must be an IsingProblem.")
        if set(assignment) != set(problem.variables):
            raise ValueError("assignment must exactly match Ising variables.")
        spins = {variable_id: (2 * _binary_value(assignment[variable_id], variable_id)) - 1 for variable_id in problem.variables}
        energy = float(problem.constant_offset)
        for variable_id in sorted(problem.linear_coefficients):
            energy += problem.linear_coefficients[variable_id] * spins[variable_id]
        for left, right in sorted(problem.quadratic_coefficients):
            energy += problem.quadratic_coefficients[(left, right)] * spins[left] * spins[right]
        return energy

    def independent_exact_energy(self, problem: QUBOProblem | IsingProblem) -> tuple[float, Mapping[str, int]]:
        """Enumerate all states with harness-owned math to find an exact reference."""

        variable_order = self._variable_order(problem)
        comparison = self._comparison_mode(problem)
        best_energy: float | None = None
        best_assignment: dict[str, int] | None = None
        for values in itertools.product((0, 1), repeat=len(variable_order)):
            assignment = dict(zip(variable_order, values))
            energy = (
                self.independent_qubo_energy(problem, assignment)
                if isinstance(problem, QUBOProblem)
                else self.independent_ising_energy(problem, assignment)
            )
            if best_energy is None or self._better(energy, assignment, best_energy, best_assignment, comparison, variable_order):
                best_energy = energy
                best_assignment = assignment
        if best_energy is None or best_assignment is None:
            raise ValueError("no states were enumerated.")
        return best_energy, MappingProxyType(dict(best_assignment))

    def verify_exact_reference(self, problem: QUBOProblem | IsingProblem) -> bool:
        """Compare E.3 exact solution against independent enumeration."""

        exact_solution = self.exact_solver.solve(problem)
        independent_energy, independent_assignment = self.independent_exact_energy(problem)
        return math.isclose(exact_solution.objective_value, independent_energy, abs_tol=ENERGY_TOLERANCE) and tuple(
            exact_solution.assignments[key] for key in self._variable_order(problem)
        ) == tuple(independent_assignment[key] for key in self._variable_order(problem))

    def verify_qubo_ising_equivalence(self, problem: QUBOProblem) -> bool:
        """Verify E.2 QUBO-to-Ising energy equivalence over every assignment."""

        ising = self.qubo_to_ising.convert(problem)
        for assignment in self._all_assignments(self._variable_order(problem)):
            if not math.isclose(
                self.independent_qubo_energy(problem, assignment),
                self.independent_ising_energy(ising, assignment),
                abs_tol=ENERGY_TOLERANCE,
            ):
                return False
        return True

    def verify_ising_qubo_equivalence(self, problem: IsingProblem) -> bool:
        """Verify E.2 Ising-to-QUBO energy equivalence over every assignment."""

        qubo = self.ising_to_qubo.convert(problem)
        for assignment in self._all_assignments(self._variable_order(problem)):
            if not math.isclose(
                self.independent_ising_energy(problem, assignment),
                self.independent_qubo_energy(qubo, assignment),
                abs_tol=ENERGY_TOLERANCE,
            ):
                return False
        return True

    def audit_qaoa_circuit(self, problem: QUBOProblem | IsingProblem, config: QAOAConfig) -> Mapping[str, Any]:
        """Audit E.5 QAOA circuit construction without running an exact solver."""

        cost_evaluator = QAOACostEvaluator()
        ising_problem, _ = cost_evaluator.normalize_problem(problem)
        parameters = config.parameters
        if parameters is None:
            parameters = next(QAOAEngine().parameter_optimizer.candidate_parameters(config))
        circuit = QAOACircuitBuilder().build(ising_problem, parameters, config)
        gates = tuple(operation.gate for operation in circuit.operations)
        linear_nonzero = any(value != 0.0 for value in ising_problem.linear_coefficients.values())
        quadratic_nonzero = any(value != 0.0 for value in ising_problem.quadratic_coefficients.values())
        findings = {
            "qubit_count": circuit.qubit_count,
            "operation_count": len(circuit.operations),
            "has_h_initialization": gates[: len(ising_problem.variables)] == tuple("H" for _ in ising_problem.variables),
            "has_rx_mixer": "RX" in gates,
            "has_rz_cost": (not linear_nonzero) or "RZ" in gates,
            "has_rzz_cost": (not quadratic_nonzero) or "RZZ" in gates,
            "depth": parameters.depth,
        }
        return MappingProxyType(findings)

    def run_case(self, case: E9BenchmarkCase) -> E9BenchmarkResult:
        """Execute one full E.3-E.8 benchmark and validation case."""

        exact_start = time.perf_counter()
        exact_solution = self.exact_solver.solve(case.problem)
        exact_runtime_ms = _elapsed_ms(exact_start)
        independent_energy, _ = self.independent_exact_energy(case.problem)
        if not math.isclose(exact_solution.objective_value, independent_energy, abs_tol=ENERGY_TOLERANCE):
            raise ValueError("E.3 exact energy does not match independent enumeration.")

        qaoa_result = None
        qaoa_runtime_ms = None
        try:
            qaoa_start = time.perf_counter()
            qaoa_result = self.qaoa_engine.solve(case.problem, case.qaoa_config)
            qaoa_runtime_ms = _elapsed_ms(qaoa_start)
        except ValueError:
            qaoa_result = None

        hybrid_result = None
        hybrid_runtime_ms = None
        try:
            hybrid_start = time.perf_counter()
            hybrid_result = self.hybrid_engine.optimize(case.problem, qaoa_config=case.qaoa_config)
            hybrid_runtime_ms = _elapsed_ms(hybrid_start)
        except ValueError:
            hybrid_result = None

        integration_start = time.perf_counter()
        integration_result = self.integration_engine.optimize(
            f"e9_{case.case_id}",
            case.problem,
            config=case.integration_config,
            qaoa_config=case.qaoa_config,
        )
        integration_runtime_ms = _elapsed_ms(integration_start)

        executive_start = time.perf_counter()
        executive_result = self.executive_brain.execute_planning_request(
            [dict(task) for task in case.tasks],
            quantum_result=integration_result,
        )
        executive_runtime_ms = _elapsed_ms(executive_start)

        selected_candidate = integration_result.selected_candidate
        selected_type = None if selected_candidate is None else selected_candidate.candidate_type
        selected_energy = integration_result.energy
        if selected_candidate is not None:
            self._verify_candidate_energy(case.problem, selected_candidate.assignment, selected_candidate.objective_value)
        if integration_result.quantum_candidate is not None:
            self._verify_candidate_energy(
                case.problem,
                integration_result.quantum_candidate.assignment,
                integration_result.quantum_candidate.objective_value,
            )
        math_verified = self.verify_exact_reference(case.problem)
        if isinstance(case.problem, QUBOProblem):
            math_verified = math_verified and self.verify_qubo_ising_equivalence(case.problem)
        else:
            math_verified = math_verified and self.verify_ising_qubo_equivalence(case.problem)

        return E9BenchmarkResult(
            case_id=case.case_id,
            problem_id=case.problem.problem_id,
            problem_type="QUBO" if isinstance(case.problem, QUBOProblem) else "Ising",
            variable_count=len(self._variable_order(case.problem)),
            constraint_count=len(case.problem.constraints) if isinstance(case.problem, QUBOProblem) else 0,
            objective_sense=case.problem.objective.sense.value,
            classical_exact_energy=exact_solution.objective_value,
            independent_exact_energy=independent_energy,
            quantum_candidate_energy=None if qaoa_result is None else qaoa_result.best_solution.objective_value,
            selected_energy=selected_energy,
            absolute_gap=integration_result.energy_gap,
            relative_gap=integration_result.relative_gap,
            exact_match=integration_result.exact_match,
            selected_solver=integration_result.selected_solver,
            selected_candidate_type=selected_type,
            feasible=integration_result.feasible,
            quantum_used=integration_result.quantum_used,
            classical_used=integration_result.classical_used,
            execution_path=integration_result.execution_path,
            qaoa_depth=case.qaoa_config.depth,
            qaoa_shots=case.qaoa_config.shots,
            exact_runtime_ms=exact_runtime_ms,
            qaoa_runtime_ms=qaoa_runtime_ms,
            hybrid_runtime_ms=hybrid_runtime_ms,
            integration_runtime_ms=integration_runtime_ms,
            executive_runtime_ms=executive_runtime_ms,
            math_verified=math_verified,
            executive_quantum_present="executive_quantum_summary" in executive_result,
            metadata={
                "hybrid_used": hybrid_result is not None,
                "e6_used": integration_result.execution_metadata.get("e6_used", False),
                "qaoa_executed": integration_result.execution_metadata.get("qaoa_executed", False),
                "hardware_execution": integration_result.execution_metadata.get("hardware_execution", False),
            },
        )

    def run_suite(self, cases: tuple[E9BenchmarkCase, ...]) -> E9ValidationReport:
        """Run cases, deterministic repeat checks, failure checks, and source audit."""

        if not cases:
            raise ValueError("cases must be non-empty.")
        results = tuple(self.run_case(case) for case in cases)
        repeat_results = tuple(self.run_case(case) for case in cases)
        determinism_verified = tuple(_deterministic_signature(result) for result in results) == tuple(
            _deterministic_signature(result) for result in repeat_results
        )
        audit = self.architecture_audit()
        failure_checks = self.failure_checks()
        all_verified = all(result.math_verified and result.executive_quantum_present for result in results)
        return E9ValidationReport(
            benchmark_results=results,
            architecture_audit=audit,
            determinism_verified=determinism_verified,
            failure_checks=failure_checks,
            summary=(
                "E.9 validation passed"
                if all_verified and audit.passed and determinism_verified
                else "E.9 validation found issues"
            ),
        )

    def failure_checks(self) -> Mapping[str, str]:
        """Run representative invalid-input checks and return deterministic outcomes."""

        checks: dict[str, str] = {}
        invalid_cases = (
            ("invalid_qaoa_shots", lambda: QAOAConfig(shots=0)),
            ("invalid_qaoa_nan", lambda: QAOAConfig(angle_grid=(math.nan,))),
            ("invalid_case_id", lambda: E9BenchmarkCase("", self._tiny_qubo())),
        )
        for name, action in invalid_cases:
            try:
                action()
            except ValueError:
                checks[name] = "rejected"
            else:
                checks[name] = "not_rejected"
        return MappingProxyType(dict(sorted(checks.items())))

    def architecture_audit(self, root: Path | None = None) -> E9ArchitectureAudit:
        """Inspect quantum source boundaries for forbidden coupling and cheating risks."""

        root = root or Path(__file__).resolve().parents[4]
        findings: list[str] = []
        anti_cheating: list[str] = []
        architecture: list[str] = []
        integration_dir = root / "backend" / "app" / "quantum" / "integration"
        qaoa_engine = root / "backend" / "app" / "quantum" / "optimization" / "qaoa_engine.py"
        for path in sorted(integration_dir.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for forbidden in ("executive_cognitive_brain", "ai_orchestrator", "fastapi", "sqlalchemy"):
                if forbidden in text.lower():
                    findings.append(f"{path.name} imports or references forbidden boundary {forbidden}.")
        qaoa_text = qaoa_engine.read_text(encoding="utf-8")
        if "ExactClassicalSolver" in qaoa_text or ".solve_qubo(" in qaoa_text or ".solve_ising(" in qaoa_text:
            anti_cheating.append("qaoa_engine.py references exact solving.")
        if "quantum_advantage_claimed" in qaoa_text:
            anti_cheating.append("qaoa_engine.py claims quantum advantage.")
        architecture.append("E.7 integration remains quantum-package scoped.")
        architecture.append("E.8 consumes E.7 through executive quantum evidence adapter.")
        passed = not findings and not anti_cheating
        return E9ArchitectureAudit(
            forbidden_import_findings=tuple(findings),
            anti_cheating_findings=tuple(anti_cheating),
            architecture_findings=tuple(architecture),
            passed=passed,
        )

    def _verify_candidate_energy(self, problem: QUBOProblem | IsingProblem, assignment: Mapping[str, int], reported: float) -> None:
        energy = (
            self.independent_qubo_energy(problem, assignment)
            if isinstance(problem, QUBOProblem)
            else self.independent_ising_energy(problem, assignment)
        )
        if not math.isclose(energy, reported, abs_tol=ENERGY_TOLERANCE):
            raise ValueError(f"candidate energy mismatch: reported {reported}, independent {energy}.")

    @staticmethod
    def _variable_order(problem: QUBOProblem | IsingProblem) -> tuple[str, ...]:
        if isinstance(problem, QUBOProblem):
            return tuple(variable.variable_id for variable in problem.variables)
        return tuple(problem.variables)

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
    def _better(
        energy: float,
        assignment: Mapping[str, int],
        best_energy: float,
        best_assignment: Mapping[str, int] | None,
        comparison: str,
        variable_order: tuple[str, ...],
    ) -> bool:
        if comparison == "MAXIMIZE":
            if energy > best_energy + ENERGY_TOLERANCE:
                return True
            if energy < best_energy - ENERGY_TOLERANCE:
                return False
        else:
            if energy < best_energy - ENERGY_TOLERANCE:
                return True
            if energy > best_energy + ENERGY_TOLERANCE:
                return False
        if best_assignment is None:
            return True
        return tuple(assignment[key] for key in variable_order) < tuple(best_assignment[key] for key in variable_order)

    @staticmethod
    def _all_assignments(variable_order: tuple[str, ...]) -> tuple[Mapping[str, int], ...]:
        return tuple(MappingProxyType(dict(zip(variable_order, values))) for values in itertools.product((0, 1), repeat=len(variable_order)))

    @staticmethod
    def _tiny_qubo() -> QUBOProblem:
        from backend.app.quantum.domain import QuantumObjective, QuantumVariable

        return QUBOProblem(
            problem_id="tiny_qubo",
            name="Tiny QUBO",
            variables=(QuantumVariable("x0", "x0", 0),),
            linear_coefficients={"x0": 1.0},
            quadratic_coefficients={},
            constant_offset=0.0,
            objective=QuantumObjective("obj_tiny", "Tiny objective", "MINIMIZE"),
        )


def _deterministic_signature(result: E9BenchmarkResult) -> tuple[Any, ...]:
    return (
        result.case_id,
        result.problem_id,
        result.classical_exact_energy,
        result.independent_exact_energy,
        result.quantum_candidate_energy,
        result.selected_energy,
        result.absolute_gap,
        result.relative_gap,
        result.exact_match,
        result.selected_solver,
        result.selected_candidate_type,
        result.feasible,
        result.quantum_used,
        result.classical_used,
        result.execution_path,
        result.math_verified,
        result.executive_quantum_present,
    )


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 6)


def _safe_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    text = value.strip()
    if any(ord(character) < 32 for character in text):
        raise ValueError(f"{field_name} cannot contain control characters.")
    return text


def _finite(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be numeric.") from None
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number


def _non_negative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer.") from None
    if number < 0:
        raise ValueError(f"{field_name} cannot be negative.")
    return number


def _positive_int(value: object, field_name: str) -> int:
    number = _non_negative_int(value, field_name)
    if number <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return number


def _binary_value(value: object, variable_id: str) -> int:
    if isinstance(value, bool) or value not in (0, 1):
        raise ValueError(f"assignment for {variable_id} must be 0 or 1.")
    return int(value)


def _freeze_mapping(values: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(values, Mapping):
        raise ValueError("mapping value must be a mapping.")
    return MappingProxyType({str(key): values[key] for key in sorted(values)})


def _thaw_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): values[key] for key in sorted(values)}
