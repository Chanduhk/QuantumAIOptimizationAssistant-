"""Stage 5 & Stage 6 Verification Script:
Verify API Outage Fallbacks, Circuit Breaking, Secret Redaction, and Model/Optimizer Honesty.
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.resilient_http import CircuitBreaker, CircuitState, ResilientHttpClient, redact_secrets
from backend.app.ml.system_inventory import SystemComponentRegistry, OperationalState
from backend.app.engines.prediction_engine import PredictionEngine
from backend.app.memory.vector_memory import VectorMemorySystem
from backend.app.ai_rl.rl_scheduler import RLScheduler
from backend.app.domain.classical_optimizer import ClassicalOptimizer
from backend.app.quantum.baseline import ExactClassicalSolver
from backend.app.domain.qaoa_solver import AssignmentQAOASolver

def run_stage5_and_6_verification():
    print("=================================================================")
    print("STAGE 5: API OUTAGE FALLBACKS & RESILIENCE VERIFICATION")
    print("=================================================================")

    # 1. Circuit breaker transitions
    print("\n[5.1] Testing Circuit Breaker transitions and bounded retries...")
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.3)
    client = ResilientHttpClient(default_timeout=0.2, max_retries=1, circuit_breaker=breaker)

    assert breaker.state == CircuitState.CLOSED
    print(f"  -> Initial circuit state: {breaker.state.value}")

    # First outage call with max_retries=1: fails on attempt 1, retries, records failure
    try:
        client.execute_request("http://127.0.0.1:59123/outage_endpoint")
    except Exception as e:
        print(f"  -> Call failed as expected: {type(e).__name__}")
    
    print(f"  -> Circuit breaker state after failures: {breaker.state.value}")
    assert breaker.state in {CircuitState.OPEN, CircuitState.CLOSED}
    
    # If not yet OPEN, trigger until OPEN
    if breaker.state != CircuitState.OPEN:
        try:
            client.execute_request("http://127.0.0.1:59123/outage_endpoint")
        except Exception:
            pass
    assert breaker.state == CircuitState.OPEN
    print(f"  -> Circuit breaker OPEN verified.")

    # Subsequent call while OPEN: rejected immediately without network attempt
    try:
        client.execute_request("http://127.0.0.1:59123/outage_endpoint")
    except RuntimeError as e:
        assert "circuit breaker OPEN" in str(e)
        print(f"  -> Fast-failure verified: {e}")

    # 2. Secret Redaction
    print("\n[5.2] Testing Secret Redaction...")
    raw_url = "https://external-api.example.com/v1/auth?api_key=sk-proj-998877665544&token=supersecrettoken123"
    sanitized = redact_secrets(raw_url)
    assert "sk-proj-998877665544" not in sanitized
    assert "supersecrettoken123" not in sanitized
    assert "***REDACTED***" in sanitized
    print(f"  -> Secret redaction OK: {sanitized}")

    # 3. Local Fallback Under Outage / Cold-Start
    print("\n[5.3] Testing Local Fallback Provenance (Prediction Engine)...")
    from backend.app.services.behavior_engine import BehaviorIntelligenceEngine
    from backend.app.domain.optimization_input_contract import normalize_duration
    from backend.app.domain.prediction_matrix import PredictionStatus
    
    behavior = BehaviorIntelligenceEngine(session=None)
    behavior._set_active_user(12345)
    pred_engine = PredictionEngine()
    result = pred_engine.predict_task_hour_with_provenance(
        behavior,
        task_id=999,
        candidate_start_hour=10,
        task_type="coding",
        duration=normalize_duration(45.0, "minutes", "explicit_task_estimate"),
    )
    print(f"  -> Prediction value: {result.value}")
    print(f"  -> Prediction source: {result.prediction_source.value}")
    print(f"  -> Fallback used: {result.fallback_used}")
    print(f"  -> Optimizer eligibility: {result.optimizer_eligibility}")
    assert result.prediction_source is PredictionStatus.COLD_START_HEURISTIC
    assert result.fallback_used is True

    print("\n=================================================================")
    print("STAGE 6: MODEL AND OPTIMIZER HONESTY AUDIT")
    print("=================================================================")

    registry = SystemComponentRegistry.get_instance()
    inventory = registry.initialize_all(force=True)

    print(f"Total cataloged components: {len(inventory)}\n")
    print(f"{'Component ID':<28} | {'Exec?':<5} | {'Ext API?':<8} | {'Primary Op':<10} | {'Fallback':<8} | {'Trained?':<8} | {'Production?':<11}")
    print("-" * 92)

    honesty_checks = []

    for cid, comp in sorted(inventory.items()):
        can_exec = "YES" if comp.can_execute_now else "NO"
        ext_api = "YES" if comp.requires_external_api else "NO"
        pri_op = comp.operational_state.value
        fallback = "ACTIVE" if comp.fallback_active else "NONE"
        trained = "YES" if comp.training_state == OperationalState.TRAINED else "NO"
        version = comp.artifact_version or "NONE"

        print(f"{cid:<28} | {can_exec:<5} | {ext_api:<8} | {pri_op:<10} | {fallback:<8} | {trained:<8} | {version:<11}")

        # Verification rules:
        if cid == "vector_memory_embedding":
            # Must state deterministic hash / local embedding, NOT claiming external LLM
            assert comp.requires_external_api is False
            prov_str = (comp.provenance or "") + " " + (comp.notes or "")
            assert "deterministic" in prov_str.lower() or "hash" in prov_str.lower() or "local" in prov_str.lower()
            honesty_checks.append("vector_memory: Honest deterministic projection")
        elif cid == "rl_scheduler":
            # Must state UNINITIALIZED_ZERO_POLICY, NOT claimed as converged production model
            assert comp.training_state in {OperationalState.NOT_READY_INSUFFICIENT_DATA, OperationalState.UNINITIALIZED, None}
            honesty_checks.append("rl_scheduler: Honest uninitialized policy status")
        elif cid == "qaoa_simulator":
            # Must declare local classical software simulation, never hardware
            assert comp.requires_external_api is False
            prov_str = (comp.provenance or "") + " " + (comp.notes or "")
            assert "software" in prov_str.lower() or "simulation" in prov_str.lower()
            honesty_checks.append("qaoa_simulator: Explicit classical simulation provenance")
        elif cid in {"classical_optimizer", "exact_classical_solver", "multi_objective_optimizer"}:
            # Classical algorithms execute now without requiring any ML model
            assert comp.can_execute_now is True
            assert comp.operational_state == OperationalState.AVAILABLE
            honesty_checks.append(f"{cid}: Immediately available without ML dependency")
        elif cid in {"productivity_model", "duration_ratio_model"}:
            # Fallback active, not promoted to personal production without data
            assert comp.fallback_active is True
            honesty_checks.append(f"{cid}: Guarded fallback, no unearned production promotion")

    print("\nHonesty Verification Confirmations:")
    for check in honesty_checks:
        print(f"  [x] {check}")

    print("\n=== STAGE 5 & 6 AUDIT COMPLETE: ALL ASSERTIONS VERIFIED ===")

if __name__ == "__main__":
    run_stage5_and_6_verification()
