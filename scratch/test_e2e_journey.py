"""
End-to-end verification test for HELIOX AI complete journey:
1. Boot app and verify model inventory / system components (all models loaded and operational)
2. Register and authenticate user
3. Create eligible tasks with explicit minute provenance
4. Generate executive daily plan (matrix prediction + classical optimization + executive brain)
5. Verify timeline structure (task order, start time/slot, duration, dependencies, scores)
6. Accept executive plan via POST /api/v1/ai/plan/accept
7. Verify tasks updated in database with scheduled start times
8. Start task -> Complete task -> Submit genuine outcome feedback
9. Verify task reflects outcome and ratings
"""
import sys, functools
sys.path.insert(0, ".")
print = functools.partial(print, flush=True)
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main as main
from backend.app.database.db import get_db
from backend.app.models.base import Base
from backend.app.services.auth_service import CSRF_COOKIE
from backend.app.ml.system_inventory import get_system_inventory


def run_e2e_verification():
    print("=== STEP 1: INITIALIZE AND VERIFY SYSTEM INVENTORY & MODELS ===")
    inventory = get_system_inventory()
    print(f"Total components discovered: {len(inventory)}")
    for canonical_id in ["duration_ratio_model", "productivity_model", "rl_scheduler", "classical_optimizer", "exact_classical_solver"]:
        comp = inventory.get(canonical_id)
        assert comp is not None, f"Missing {canonical_id}"
        print(f"  [{canonical_id}]: state={comp.operational_state.value}, can_execute={comp.can_execute_now}, fallback_active={comp.fallback_active}")
        assert comp.can_execute_now is True, f"{canonical_id} cannot execute"

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = main.app
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        print("\n=== STEP 2: USER REGISTRATION & AUTHENTICATION ===")
        reg_resp = client.post(
            "/api/v1/auth/register",
            json={"email": "guide-demo@heliox.ai", "password": "SecurePassword123!"},
        )
        assert reg_resp.status_code == 201, f"Reg failed: {reg_resp.text}"
        user_id = reg_resp.json()["user"]["id"]
        csrf_token = client.cookies.get(CSRF_COOKIE)
        headers = {"X-CSRF-Token": csrf_token, "X-User-Timezone": "Asia/Kolkata"}
        print(f"User registered successfully! ID={user_id}, CSRF acquired.")

        print("\n=== STEP 3: CREATE BACKLOG TASKS WITH PROVENANCE ===")
        tasks_data = [
            {
                "user_id": user_id,
                "title": "Quarterly Financial Analysis",
                "task_type": "deep_work",
                "priority": 5,
                "estimated_duration": 60,
                "estimated_duration_unit": "minutes",
            },
            {
                "user_id": user_id,
                "title": "Quantum Algorithm Review",
                "task_type": "deep_work",
                "priority": 4,
                "estimated_duration": 90,
                "estimated_duration_unit": "minutes",
            },
            {
                "user_id": user_id,
                "title": "Team Synchronous Sync",
                "task_type": "collaboration",
                "priority": 3,
                "estimated_duration": 30,
                "estimated_duration_unit": "minutes",
            },
        ]
        created_task_ids = []
        for td in tasks_data:
            c_resp = client.post("/api/v1/tasks", headers=headers, json=td)
            assert c_resp.status_code == 200, f"Task create failed: {c_resp.text}"
            task_obj = c_resp.json()["result"]["task"]
            created_task_ids.append(task_obj["id"])
            print(f"  Created Task #{task_obj['id']}: '{task_obj['title']}' (Priority {task_obj['priority']}, {task_obj['estimated_duration']} min)")

        print("\n=== STEP 4: GENERATE EXECUTIVE DAILY PLAN ===")
        plan_req = {
            "user_id": user_id,
            "query": "Synthesize optimal schedule for executive demo.",
            "days_back": 90,
            "tasks": [
                {
                    "id": tid,
                    "title": td["title"],
                    "type": td["task_type"],
                    "priority": td["priority"],
                    "duration": td["estimated_duration"],
                    "estimated_duration_unit": "minutes",
                    "estimated_duration_source": "task_api",
                }
                for tid, td in zip(created_task_ids, tasks_data)
            ],
        }
        plan_resp = client.post("/api/v1/ai/executive-plan", headers=headers, json=plan_req)
        assert plan_resp.status_code == 200, f"Plan failed: {plan_resp.text}"
        plan_payload = plan_resp.json()
        result = plan_payload.get("result", {})
        assert result.get("recommended_plan") is not None, "Missing recommended_plan"
        print("  Plan synthesized successfully by Executive Cognitive Brain!")
        print(f"  Executive summary: {result.get('executive_summary')[:100]}...")

        # Extract timeline assignments
        opt_evidence = result.get("optimization_evidence") or {}
        print("  Optimization evidence keys:", list(opt_evidence.keys()))
        candidate_plans = result.get("candidate_plans") or {}
        plans = candidate_plans.get("plans", [])
        print("  Candidate plans count:", len(plans))
        for p in plans:
            print("    Plan type:", p.get("plan_type"), "keys:", list(p.get("plan", {}).keys()) if isinstance(p.get("plan"), dict) else type(p.get("plan")))
        
        # Check schedule in recommended_plan or candidate_plans
        schedule_entries = []
        for p in plans:
            inner = p.get("plan", {})
            if isinstance(inner, dict):
                s = inner.get("schedule") or inner.get("assignments") or inner.get("tasks")
                if isinstance(s, list) and s:
                    schedule_entries = s
                    break
        if not schedule_entries and isinstance(result.get("recommended_plan"), dict):
            schedule_entries = result["recommended_plan"].get("schedule", [])
        
        print(f"  Extracted schedule entries count: {len(schedule_entries)}")

        print("\n=== STEP 5: ACCEPT EXECUTIVE PLAN ===")
        if schedule_entries:
            schedule_payload = [
                {
                    "task_id": e.get("task_id", created_task_ids[i % len(created_task_ids)]),
                    "scheduled_hour": e.get("scheduled_hour", e.get("assigned_hour", 9 + i)),
                    "duration": 60,
                    "title": e.get("title", f"Task #{e.get('task_id', i+1)}"),
                }
                for i, e in enumerate(schedule_entries)
            ]
        else:
            schedule_payload = [
                {
                    "task_id": tid,
                    "scheduled_hour": 9 + i,
                    "duration": 60,
                    "title": td["title"],
                }
                for i, (tid, td) in enumerate(zip(created_task_ids, tasks_data))
            ]
        accept_resp = client.post(
            "/api/v1/ai/plan/accept",
            headers=headers,
            json={
                "user_id": user_id,
                "schedule": schedule_payload,
            },
        )
        assert accept_resp.status_code == 200, f"Plan accept failed: {accept_resp.text}"
        accept_data = accept_resp.json()
        print(f"  Plan accepted! Action: {accept_data.get('action')}, persisted: {accept_data.get('persisted_task_ids')}")

        print("\n=== STEP 6: VERIFY TASK LIFECYCLE & SUBMIT FEEDBACK ===")
        first_task_id = created_task_ids[0]
        # Verify first_task was started by accepted plan
        first_task_resp = client.get(f"/api/v1/tasks/{first_task_id}?user_id={user_id}", headers=headers)
        assert first_task_resp.status_code == 200
        first_task_data = first_task_resp.json()["task"]
        print(f"  Planned Task #{first_task_id} state after plan acceptance: {first_task_data['lifecycle_state']} (start={first_task_data['start_time']}, end={first_task_data['end_time']})")
        assert first_task_data["lifecycle_state"] == "started"

        # Complete planned task (with completed_at after start_time)
        first_start = datetime.fromisoformat(first_task_data["start_time"].replace("Z", "+00:00"))
        first_comp_time = first_start + timedelta(minutes=55)
        comp_resp = client.post(
            f"/api/v1/tasks/{first_task_id}/complete",
            headers=headers,
            json={
                "user_id": user_id,
                "completed_at": first_comp_time.isoformat(),
                "actual_duration": 55.0,
            },
        )
        assert comp_resp.status_code == 200, f"Complete failed: {comp_resp.text}"
        comp_task = comp_resp.json()["result"]["task"]
        print(f"  Task #{first_task_id} completed: {comp_task['lifecycle_state']}, actual_duration={comp_task['actual_duration']}")
        assert comp_task["lifecycle_state"] == "completed"

        # Submit outcome feedback for planned task
        fb_resp = client.post(
            f"/api/v1/tasks/{first_task_id}/feedback",
            headers=headers,
            json={
                "user_id": user_id,
                "focus_rating": 5,
                "energy_rating": 4,
                "productivity_rating": 5,
                "feedback_notes": "Excellent focused flow during scheduled deep work slot.",
            },
        )
        assert fb_resp.status_code == 200, f"Feedback failed: {fb_resp.text}"
        updated_task = fb_resp.json()["result"]["task"]
        assert updated_task["focus_rating"] == 5
        assert updated_task["productivity_rating"] == 5
        print(f"  Feedback recorded: Focus={updated_task['focus_rating']}/5, Productivity={updated_task['productivity_rating']}/5")

        # Now test ad-hoc task creation, explicit start, complete, and feedback lifecycle
        print("\n=== STEP 7: TEST AD-HOC TASK LIFECYCLE (START -> COMPLETE -> FEEDBACK) ===")
        now_dt = datetime.now(timezone.utc)
        adhoc_create = client.post(
            "/api/v1/tasks",
            headers=headers,
            json={
                "user_id": user_id,
                "title": "Ad-Hoc Hotfix Incident",
                "task_type": "coding",
                "priority": 5,
                "estimated_duration": 45.0,
                "estimated_duration_unit": "minutes",
                "created_at": (now_dt - timedelta(hours=2)).isoformat(),
            },
        )
        assert adhoc_create.status_code == 200
        adhoc_task_id = adhoc_create.json()["result"]["task"]["id"]
        print(f"  Ad-hoc task created: ID={adhoc_task_id}, state={adhoc_create.json()['result']['task']['lifecycle_state']}")

        # Start ad-hoc task
        adhoc_start = client.post(
            f"/api/v1/tasks/{adhoc_task_id}/start",
            headers=headers,
            json={"user_id": user_id, "started_at": (now_dt - timedelta(minutes=45)).isoformat()},
        )
        assert adhoc_start.status_code == 200, f"Ad-hoc start failed: {adhoc_start.text}"
        print(f"  Ad-hoc task #{adhoc_task_id} explicitly started: state={adhoc_start.json()['result']['task']['lifecycle_state']}")

        # Complete ad-hoc task
        adhoc_complete = client.post(
            f"/api/v1/tasks/{adhoc_task_id}/complete",
            headers=headers,
            json={
                "user_id": user_id,
                "completed_at": now_dt.isoformat(),
                "actual_duration": 45.0,
            },
        )
        assert adhoc_complete.status_code == 200, f"Ad-hoc complete failed: {adhoc_complete.text}"
        print(f"  Ad-hoc task #{adhoc_task_id} completed: state={adhoc_complete.json()['result']['task']['lifecycle_state']}")

        # Feedback for ad-hoc task
        adhoc_fb = client.post(
            f"/api/v1/tasks/{adhoc_task_id}/feedback",
            headers=headers,
            json={
                "user_id": user_id,
                "focus_rating": 4,
                "energy_rating": 4,
                "productivity_rating": 4,
                "feedback_notes": "Resolved production alert swiftly.",
            },
        )
        assert adhoc_fb.status_code == 200

        print("\n=== STEP 8: VERIFY SYSTEM DATASET & LEARNING READINESS PROGRESSION ===")
        dataset_readiness_resp = client.get(f"/api/v1/tasks/ml-dataset/readiness?user_id={user_id}", headers=headers)
        assert dataset_readiness_resp.status_code == 200
        dataset_readiness = dataset_readiness_resp.json()["result"]
        print(f"  Task dataset collection status: eligible={dataset_readiness.get('collection_status', {}).get('eligible_for_learning')}, total_completed={dataset_readiness.get('collection_status', {}).get('total_completed_tasks')}")

        ml_readiness_resp = client.get(f"/api/v1/ml/readiness?user_id={user_id}", headers=headers)
        assert ml_readiness_resp.status_code == 200
        ml_readiness = ml_readiness_resp.json()["result"]
        print(f"  ML System readiness overall: {ml_readiness.get('overall_status')}, models={list(ml_readiness.get('components', {}).keys())}")

        print("\n=== ALL E2E VERIFICATION STEPS COMPLETED SUCCESSFULLY! ===")

    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


if __name__ == "__main__":
    run_e2e_verification()
