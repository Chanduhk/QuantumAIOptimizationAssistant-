import os
import sys
import tempfile
import time
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.ml.training_controller import (
    TrainingController,
    TrainingJobStatus,
    TrainingJobType,
)
from backend.app.ml.datasets.public_dataset_manager import (
    PublicDatasetManager,
    UCI_GARMENT_ID,
)
from backend.app.ml.model_registry import ModelRegistry, ModelStatus

def test_stage4_lifecycle():
    print("=== STAGE 4: AUTOMATIC TRAINING LIFECYCLE AUDIT ===")

    # 1. Dataset discovery and provenance
    pdm = PublicDatasetManager()
    prov = pdm.get_provenance(UCI_GARMENT_ID)
    assert prov is not None, "UCI Garment dataset provenance not found"
    print(f"[x] 1. Dataset discovered: {prov['name']} (ID: {prov['dataset_id']})")
    assert prov["sha256_checksum"] == "446026846b37d73800d1fd01b852ceaf95f086f15a626802d784154f63885bc2"
    print(f"[x] 2. Dataset checksum verified: {prov['sha256_checksum'][:16]}...")
    assert prov["total_records"] == 1197
    assert prov["train_records"] == 837
    assert prov["val_records"] == 179
    assert prov["test_records"] == 181
    print(f"[x] 3. Partition sizes verified: {prov['train_records']} train / {prov['val_records']} val / {prov['test_records']} test")

    # Use isolated temp directories and test registry to prevent test side effects
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_artifacts = Path(temp_dir) / "artifacts"
        temp_registry_dir = Path(temp_dir) / "registry"
        test_registry = ModelRegistry()
        controller = TrainingController(
            registry=test_registry,
            dataset_manager=pdm,
            artifacts_dir=temp_artifacts,
        )

        # 4. Background job creation
        print("\n--- Testing Background Job Creation & Duplicate Protection ---")
        job1 = controller.trigger_training(job_type="public_benchmark", force=True, triggered_by="audit_test")
        assert job1.status in (TrainingJobStatus.QUEUED, TrainingJobStatus.RUNNING), f"Expected QUEUED/RUNNING, got {job1.status}"
        print(f"[x] 4. Job created: {job1.job_id}, initial status: {job1.status.value}")

        # 5. Duplicate-job prevention
        try:
            controller.trigger_training(job_type="public_benchmark", force=True)
            duplicate_prevented = False
        except RuntimeError as e:
            duplicate_prevented = True
            print(f"[x] 5. Duplicate job prevented correctly: {e}")
        assert duplicate_prevented, "Duplicate job should have been rejected while job1 is in progress!"

        # 6. Wait for job1 completion and monitor progress logging
        timeout = 30
        start = time.time()
        while job1.status in (TrainingJobStatus.QUEUED, TrainingJobStatus.RUNNING):
            time.sleep(0.5)
            if time.time() - start > timeout:
                raise TimeoutError("Job did not finish in 30s")

        print(f"[x] 6. Job finished with status: {job1.status.value}, progress: {job1.progress_pct}%")
        assert job1.status == TrainingJobStatus.COMPLETED, f"Expected COMPLETED, got {job1.status}"
        assert job1.progress_pct == 100
        assert len(job1.step_logs) >= 5, f"Expected detailed step logs, got {len(job1.step_logs)}"
        print(f"     Step logs recorded ({len(job1.step_logs)} steps):")
        for s in job1.step_logs:
            print(f"       [{s.status}] ({s.progress_pct}%) {s.step}: {s.message[:60]}...")

        # 7. Redundant training cache check
        print("\n--- Testing Redundant Training Prevention (Fingerprint Cache) ---")
        job2 = controller.trigger_training(job_type="public_benchmark", force=False, triggered_by="audit_cached")
        while job2.status in (TrainingJobStatus.QUEUED, TrainingJobStatus.RUNNING):
            time.sleep(0.5)
        print(f"[x] 7. Cached training handled correctly: {job2.status.value}, current step: {job2.current_step}")
        assert any(log.step == "cache_check" and log.status == "SKIPPED" for log in job2.step_logs)
        print("     Log confirms: public dataset unchanged, redundant training safely skipped.")

        # 8. Candidate evaluation, artifact persistence, and registry status
        print("\n--- Testing Candidate Artifact & Promotion Rejection ---")
        models = test_registry.list_models("ProductivityModel")
        assert len(models) == 1, f"Expected 1 registered model, got {len(models)}"
        candidate = models[0]
        print(f"[x] 8. Registered model: {candidate.model_name} v{candidate.version}")
        assert candidate.status == ModelStatus.STAGING, f"Expected STAGING, got {candidate.status}"
        print(f"[x] 9. Governance verified: Model status is strictly STAGING (not promoted to production)")
        assert candidate.metrics.get("is_personalized") is False
        assert candidate.metrics.get("public_benchmark") is True
        print(f"[x] 10. Labeling verified: is_personalized=False, public_benchmark=True")

        # 9. Failure and Retry handling
        print("\n--- Testing Failure and Retry Handling ---")
        try:
            controller.trigger_training(job_type="invalid_job_type")
            invalid_rejected = False
        except ValueError as e:
            invalid_rejected = True
            print(f"[x] 11. Invalid job_type rejected: {e}")
        assert invalid_rejected

        # Retry API test
        retry_job = controller.retry_training()
        assert retry_job.status in (TrainingJobStatus.QUEUED, TrainingJobStatus.RUNNING)
        print(f"[x] 12. Retry initiated job: {retry_job.job_id}")
        while retry_job.status in (TrainingJobStatus.QUEUED, TrainingJobStatus.RUNNING):
            time.sleep(0.5)
        assert retry_job.status == TrainingJobStatus.COMPLETED
        print(f"[x] 13. Retry job completed successfully: {retry_job.status.value}")

    print("\nPASS: All Stage 4 Automatic Training Lifecycle checks verified successfully!")

if __name__ == "__main__":
    test_stage4_lifecycle()
