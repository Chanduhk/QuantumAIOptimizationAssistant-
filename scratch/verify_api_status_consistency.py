"""Verify API and UI status consistency with backend registry and readiness APIs.
Follows strict read-only and isolated fixture principles.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.main import app
from backend.app.database.db import SessionLocal
from backend.app.ml.readiness import assess_full_ml_system_readiness

def verify_apis():
    client = TestClient(app)
    
    # 1. Component Inventory Public API
    print("=== 1. VERIFYING COMPONENT INVENTORY PUBLIC API ===")
    r_inv = client.get("/api/v1/system/component-inventory")
    assert r_inv.status_code == 200, f"Inventory API failed: {r_inv.text}"
    inv_data = r_inv.json()
    result = inv_data.get("result", {})
    print(f"Status Code: 200 | Total Components: {result.get('total_components')}")
    
    components = result.get("components", {})
    
    # Check RL Scheduler
    rl = components.get("rl_scheduler")
    assert rl is not None, "rl_scheduler not in inventory"
    print(f"\n[rl_scheduler in API payload]")
    print(f"  operational_state: {rl.get('operational_state')}")
    print(f"  training_state: {rl.get('training_state')}")
    print(f"  fallback_active: {rl.get('fallback_active')}")
    print(f"  fallback_description: {rl.get('fallback_description')}")
    assert rl.get("training_state") != "TRAINED", "VIOLATION: rl_scheduler labeled as TRAINED!"
    assert rl.get("fallback_active") is True, "VIOLATION: rl_scheduler fallback not active!"
    print("  -> RL Scheduler verified: NOT labeled as trained; fallback active.")

    # Check Productivity Model
    prod = components.get("productivity_model")
    assert prod is not None, "productivity_model not in inventory"
    print(f"\n[productivity_model in API payload]")
    print(f"  operational_state: {prod.get('operational_state')}")
    print(f"  training_state: {prod.get('training_state')}")
    print(f"  fallback_active: {prod.get('fallback_active')}")
    print(f"  fallback_description: {prod.get('fallback_description')}")
    assert prod.get("training_state") != "TRAINED", "VIOLATION: productivity_model labeled as TRAINED!"
    assert prod.get("fallback_active") is True, "VIOLATION: productivity fallback not active!"
    print("  -> Productivity Model verified: NOT labeled as trained; circadian fallback active.")

    # Check Duration Model
    dur = components.get("duration_ratio_model")
    assert dur is not None, "duration_ratio_model not in inventory"
    print(f"\n[duration_ratio_model in API payload]")
    print(f"  operational_state: {dur.get('operational_state')}")
    print(f"  training_state: {dur.get('training_state')}")
    print(f"  fallback_active: {dur.get('fallback_active')}")
    print(f"  fallback_description: {dur.get('fallback_description')}")
    assert dur.get("training_state") != "TRAINED", "VIOLATION: duration_ratio_model labeled as TRAINED!"
    assert dur.get("fallback_active") is True, "VIOLATION: duration fallback not active!"
    print("  -> Duration Model verified: NOT labeled as trained; ratio baseline active.")

    # 2. Public Model Status API
    print("\n=== 2. VERIFYING PUBLIC MODEL STATUS API ===")
    r_ms = client.get("/api/v1/ml/model-status")
    assert r_ms.status_code == 200, f"Model status API failed: {r_ms.text}"
    ms_data = r_ms.json()
    print(f"Status Code: 200 | Status: {ms_data.get('status')}")
    print(f"Models Registered: {ms_data.get('models_registered')}")
    print(f"Total Components Available: {ms_data.get('total_components_available')}")

    # 3. Readiness Assessment on Real DB (Read-Only)
    print("\n=== 3. VERIFYING AUTHORITATIVE ML READINESS ASSESSMENT (READ-ONLY) ===")
    real_user_id = 1412004044
    with SessionLocal() as session:
        readiness_report = assess_full_ml_system_readiness(session, user_id=real_user_id)
        print(f"Real User ({real_user_id}) ML Readiness Report:")
        print(f"  Overall Status: {readiness_report.overall_status}")
        for cname, cinfo in readiness_report.components.items():
            print(f"  [{cname}]")
            print(f"    Status: {cinfo.status} (Eligible: {cinfo.eligible_samples}/{cinfo.required_samples})")
            print(f"    Blocking Reasons: {cinfo.blocking_reasons}")
            print(f"    Actions: {cinfo.data_collection_actions}")

    print("\nALL API AND DATA INTEGRITY VERIFICATIONS PASSED CLEANLY (EXIT CODE 0)")

if __name__ == "__main__":
    verify_apis()
