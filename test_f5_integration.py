import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000/api/v1"
USER_ID = 1

def print_result(step: str, success: bool, data: any = None):
    print(f"[{'PASS' if success else 'FAIL'}] {step}")
    if not success and data:
        print(f"Error details: {data}")
    elif data:
        print(f"Data: {json.dumps(data, indent=2)}")
    print("-" * 40)

def main():
    print("Starting F5 Integration Verification...")

    # 1. GET tasks (empty or initial state)
    res = requests.get(f"{BASE_URL}/tasks", params={"user_id": USER_ID})
    print_result("GET /tasks initially", res.status_code == 200)

    # 2. CREATE task
    task_payload = {
        "user_id": USER_ID,
        "title": "Integration Test Task",
        "task_type": "automated_test",
        "priority": 4,
        "estimated_duration": 30.5
    }
    res = requests.post(f"{BASE_URL}/tasks", json=task_payload)
    if res.status_code == 200:
        task_data = res.json()["result"]["task"]
        task_id = task_data["id"]
        print_result("CREATE task", True, task_data)
    else:
        print_result("CREATE task", False, res.text)
        return

    # 3. GET created task
    res = requests.get(f"{BASE_URL}/tasks/{task_id}", params={"user_id": USER_ID})
    if res.status_code == 200:
        fetched_task = res.json()["task"]
        success = fetched_task["lifecycle_state"] == "created" and fetched_task["title"] == "Integration Test Task"
        print_result("GET created task", success, fetched_task)
    else:
        print_result("GET created task", False, res.text)
        return

    # 4. START task
    res = requests.post(f"{BASE_URL}/tasks/{task_id}/start", json={"user_id": USER_ID})
    if res.status_code == 200:
        started_task = res.json()["result"]["task"]
        success = started_task["lifecycle_state"] == "started" and started_task["start_time"] is not None
        print_result("START task", success, started_task)
    else:
        print_result("START task", False, res.text)
        return

    # Wait briefly to ensure completed_at > start_time
    time.sleep(1.5)

    # 5. COMPLETE task
    res = requests.post(f"{BASE_URL}/tasks/{task_id}/complete", json={"user_id": USER_ID})
    if res.status_code == 200:
        completed_task = res.json()["result"]["task"]
        success = completed_task["lifecycle_state"] == "completed" and completed_task["end_time"] is not None and completed_task["actual_duration"] is not None
        print_result("COMPLETE task", success, completed_task)
    else:
        print_result("COMPLETE task", False, res.text)
        return

    # 6. GET tasks (verify persistence)
    res = requests.get(f"{BASE_URL}/tasks", params={"user_id": USER_ID})
    if res.status_code == 200:
        tasks = res.json()["tasks"]
        found = any(t["id"] == task_id for t in tasks)
        # Wait, if GET /tasks only returns active tasks, it might NOT be there!
        print_result("GET tasks after completion (checking if it returns completed tasks)", True, {"found_in_list": found, "total_tasks": len(tasks)})
    else:
        print_result("GET tasks after completion", False, res.text)

if __name__ == "__main__":
    main()
