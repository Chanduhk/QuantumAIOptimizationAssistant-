from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.db import get_db
from backend.app.ml.datasets import (
    DatasetQualityAudit,
    DatasetQualityAuditor,
    DatasetRow,
    TaskCollectionReporter,
    TaskDataExtractor,
)
from backend.app.models.base import Base
from backend.app.models.behavior_data import BehaviorData as _BehaviorData
from backend.app.models.task import Task
from backend.app.services.task_lifecycle_service import TaskLifecycleService
from backend.main import app


BASE = datetime(2026, 1, 1, 9, 0, 0)


def memory_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    return Session()


def completed_task(
    service: TaskLifecycleService,
    *,
    user_id: int = 1,
    task_type: str = "focus",
    estimate: float = 60.0,
    actual: float = 60.0,
    created_offset: int = 0,
    start_delay: int = 5,
    priority: int = 3,
) -> Task:
    task = service.create_task(
        user_id=user_id,
        title="private audit task",
        task_type=task_type,
        priority=priority,
        estimated_duration=estimate,
        created_at=BASE + timedelta(minutes=created_offset),
    )
    service.start_task(
        task_id=task.id,
        user_id=user_id,
        started_at=BASE + timedelta(minutes=created_offset + start_delay),
    )
    return service.complete_task(
        task_id=task.id,
        user_id=user_id,
        completed_at=BASE + timedelta(minutes=created_offset + start_delay + actual),
    )


def audit_session(session):
    return DatasetQualityAuditor().audit_session(session)


def extraction_with_rows(session):
    extraction = TaskDataExtractor(session).extract()
    collection = TaskCollectionReporter(session).report()
    return extraction, collection


def test_zero_row_dataset_is_not_ready_no_data():
    audit = audit_session(memory_session())

    assert audit.readiness_status == "NOT_READY_NO_DATA"
    assert audit.sample_counts["dataset_rows"] == 0
    assert audit.leakage_status == "INCONCLUSIVE"


def test_one_valid_row_is_insufficient_but_structurally_valid():
    session = memory_session()
    completed_task(TaskLifecycleService(session))

    audit = audit_session(session)

    assert audit.readiness_status == "NOT_READY_INSUFFICIENT_DATA"
    assert audit.sample_counts["f3_eligible_records"] == 1
    assert audit.label_statistics["count"] == 1
    assert audit.leakage_status == "PASS"


def test_multiple_valid_rows_are_conditionally_ready_for_training_audit():
    session = memory_session()
    service = TaskLifecycleService(session)
    completed_task(service, actual=60, created_offset=0)
    completed_task(service, actual=30, created_offset=120, task_type="admin")
    completed_task(service, actual=90, created_offset=240, user_id=2)

    audit = audit_session(session)

    assert audit.readiness_status == "CONDITIONALLY_READY_FOR_TRAINING_AUDIT"
    assert audit.sample_counts["dataset_rows"] == 3


def test_label_statistics_include_descriptive_values_only_when_rows_exist():
    session = memory_session()
    service = TaskLifecycleService(session)
    completed_task(service, estimate=60, actual=30)
    completed_task(service, estimate=60, actual=60, created_offset=120)
    completed_task(service, estimate=60, actual=90, created_offset=240)

    stats = audit_session(session).label_statistics

    assert stats["min"] == 0.5
    assert stats["max"] == 1.5
    assert stats["mean"] == 1.0
    assert stats["median"] == 1.0
    assert stats["p25"] == 0.75
    assert stats["p75"] == 1.25


def test_missing_estimated_duration_is_counted_from_collection_report():
    session = memory_session()
    session.add(
        Task(
            user_id=1,
            title="legacy missing estimate",
            task_type="focus",
            priority=3,
            created_at=BASE,
            start_time=BASE + timedelta(minutes=5),
            end_time=BASE + timedelta(minutes=65),
            actual_duration=60,
            completed=True,
            outcome_valid=True,
        )
    )
    session.commit()

    audit = audit_session(session)

    assert audit.sample_counts["raw_task_records"] == 1
    assert audit.readiness_status == "NOT_READY_INSUFFICIENT_DATA"


def test_missing_task_type_is_rejected_before_dataset_rows():
    session = memory_session()
    session.add(
        Task(
            user_id=1,
            title="legacy missing type",
            task_type="",
            priority=3,
            estimated_duration=60,
            created_at=BASE,
            start_time=BASE + timedelta(minutes=5),
            end_time=BASE + timedelta(minutes=65),
            actual_duration=60,
            completed=True,
            outcome_valid=True,
        )
    )
    session.commit()

    audit = audit_session(session)

    assert audit.sample_counts["f3_eligible_records"] == 0
    assert audit.sample_counts["rejected_records"] >= 1


def test_missing_timestamps_are_reflected_in_counts():
    session = memory_session()
    TaskLifecycleService(session).create_task(
        user_id=1,
        title="private pending task",
        task_type="focus",
        priority=3,
        estimated_duration=60,
        created_at=BASE,
    )

    collection = TaskCollectionReporter(session).report()

    assert collection.missing_start_time_records == 1
    assert collection.incomplete_records == 1


def test_zero_estimated_duration_prevents_eligible_label():
    session = memory_session()
    session.add(
        Task(
            user_id=1,
            title="legacy zero estimate",
            task_type="focus",
            priority=3,
            estimated_duration=0,
            created_at=BASE,
            start_time=BASE + timedelta(minutes=5),
            end_time=BASE + timedelta(minutes=65),
            actual_duration=60,
            completed=True,
            outcome_valid=True,
        )
    )
    session.commit()

    audit = audit_session(session)

    assert audit.sample_counts["f3_eligible_records"] == 0
    assert audit.sample_counts["rejected_records"] >= 1


def test_negative_duration_prevents_eligible_label():
    session = memory_session()
    session.add(
        Task(
            user_id=1,
            title="legacy negative duration",
            task_type="focus",
            priority=3,
            estimated_duration=60,
            created_at=BASE,
            start_time=BASE + timedelta(minutes=65),
            end_time=BASE + timedelta(minutes=5),
            actual_duration=-60,
            completed=True,
            outcome_valid=True,
        )
    )
    session.commit()

    audit = audit_session(session)

    assert audit.sample_counts["f3_eligible_records"] == 0


def test_extreme_duration_ratio_is_warned_not_deleted():
    session = memory_session()
    service = TaskLifecycleService(session)
    completed_task(service, estimate=60, actual=300)

    audit = audit_session(session)

    assert audit.duration_ratio_quality["suspicious_high_count"] == 1
    assert "unusually_large_duration_ratios_observed" in audit.warnings
    assert audit.sample_counts["dataset_rows"] == 1


def test_duplicate_task_ids_are_blocking_data_quality_issue():
    session = memory_session()
    service = TaskLifecycleService(session)
    completed_task(service, actual=60)
    extraction, collection = extraction_with_rows(session)
    row = extraction.dataset_build.rows[0]
    duplicate_extraction = replace(
        extraction,
        dataset_build=replace(extraction.dataset_build, rows=(row, row)),
        dataset_split=replace(extraction.dataset_split, train=(row, row)),
    )

    audit = DatasetQualityAuditor().audit_extraction(duplicate_extraction, collection_report=collection)

    assert audit.readiness_status == "NOT_READY_DATA_QUALITY"
    assert audit.duplicate_audit["duplicate_task_ids"] == ("1",)


def test_multiple_users_are_counted_without_exposing_private_fields():
    session = memory_session()
    service = TaskLifecycleService(session)
    completed_task(service, user_id=1)
    completed_task(service, user_id=2, created_offset=120)

    audit = audit_session(session)

    assert audit.user_diversity["user_count"] == 2
    assert "private audit task" not in str(audit.to_dict())


def test_multiple_task_types_are_counted():
    session = memory_session()
    service = TaskLifecycleService(session)
    completed_task(service, task_type="focus")
    completed_task(service, task_type="admin", created_offset=120)

    audit = audit_session(session)

    assert audit.task_type_diversity["task_type_count"] == 2


def test_single_user_concentration_warning():
    session = memory_session()
    service = TaskLifecycleService(session)
    completed_task(service)

    assert "single_user_dataset_limits_generalization" in audit_session(session).warnings


def test_single_task_type_concentration_warning():
    session = memory_session()
    service = TaskLifecycleService(session)
    completed_task(service)

    assert "single_task_type_dataset_limits_generalization" in audit_session(session).warnings


def test_cold_start_historical_features_are_not_corruption():
    session = memory_session()
    completed_task(TaskLifecycleService(session))

    audit = audit_session(session)

    assert audit.historical_feature_audit["cold_start_rows"] == 1
    assert audit.historical_feature_audit["negative_prior_completed_task_count"] == ()


def test_historical_feature_chronology_uses_only_prior_outcomes():
    session = memory_session()
    service = TaskLifecycleService(session)
    completed_task(service, actual=100, created_offset=0)
    completed_task(service, actual=30, created_offset=10)
    completed_task(service, actual=60, created_offset=120)

    rows = {row.task_id: row for row in TaskDataExtractor(session).extract().dataset_build.rows}
    audit = audit_session(session)

    assert rows["2"].features["prior_completed_task_count"] == 0
    assert rows["3"].features["prior_completed_task_count"] == 2
    assert audit.historical_feature_audit["possible_self_history_leakage"] == ()


def test_future_feature_name_is_detected_as_leakage():
    row = DatasetRow(
        example_id="e1",
        task_id="t1",
        user_id="u1",
        prediction_timestamp=BASE,
        features={"future_workload": 10},
        target={"duration_ratio": 1.0},
        provenance={"feature_provenance": (("future_workload", "available_at_prediction_time"),)},
        dataset_version="v",
        schema_version="s",
        feature_version="f",
        label_version="l",
    )
    extraction = TaskDataExtractor(memory_session()).extract()
    audit = DatasetQualityAuditor().audit_extraction(
        replace(extraction, dataset_build=replace(extraction.dataset_build, rows=(row,)))
    )

    assert audit.leakage_status == "FAIL"
    assert audit.readiness_status == "NOT_READY_LEAKAGE"


def test_current_task_target_leakage_name_is_detected():
    row = DatasetRow(
        example_id="e1",
        task_id="t1",
        user_id="u1",
        prediction_timestamp=BASE,
        features={"completed": True},
        target={"duration_ratio": 1.0},
        provenance={"feature_provenance": (("completed", "available_at_prediction_time"),)},
        dataset_version="v",
        schema_version="s",
        feature_version="f",
        label_version="l",
    )
    extraction = TaskDataExtractor(memory_session()).extract()
    audit = DatasetQualityAuditor().audit_extraction(
        replace(extraction, dataset_build=replace(extraction.dataset_build, rows=(row,)))
    )

    assert "leakage_feature:e1:completed" in audit.issues


def test_behavior_data_leakage_name_is_detected():
    row = DatasetRow(
        example_id="e1",
        task_id="t1",
        user_id="u1",
        prediction_timestamp=BASE,
        features={"productivity_score": 90},
        target={"duration_ratio": 1.0},
        provenance={"feature_provenance": (("productivity_score", "available_at_prediction_time"),)},
        dataset_version="v",
        schema_version="s",
        feature_version="f",
        label_version="l",
    )
    extraction = TaskDataExtractor(memory_session()).extract()
    audit = DatasetQualityAuditor().audit_extraction(
        replace(extraction, dataset_build=replace(extraction.dataset_build, rows=(row,)))
    )

    assert audit.leakage_status == "FAIL"


def test_temporal_split_correctness_for_chronological_rows():
    session = memory_session()
    service = TaskLifecycleService(session)
    for index in range(5):
        completed_task(service, created_offset=index * 120)

    audit = audit_session(session)

    assert audit.temporal_split_audit["issues"] == ()
    assert audit.temporal_split_audit["train_size"] > 0


def test_duplicate_split_membership_is_detected():
    session = memory_session()
    service = TaskLifecycleService(session)
    completed_task(service)
    extraction, collection = extraction_with_rows(session)
    row = extraction.dataset_build.rows[0]
    bad_split = replace(extraction.dataset_split, train=(row,), validation=(row,), test=())
    audit = DatasetQualityAuditor().audit_extraction(
        replace(extraction, dataset_split=bad_split),
        collection_report=collection,
    )

    assert "duplicate_split_membership" in audit.temporal_split_audit["issues"]


def test_missingness_reports_feature_and_label_fields():
    session = memory_session()
    completed_task(TaskLifecycleService(session))

    audit = audit_session(session)

    assert audit.missingness["estimated_duration_minutes"]["missing_count"] == 0
    assert audit.missingness["duration_ratio_label"]["missing_count"] == 0


def test_audit_output_is_deterministic():
    session = memory_session()
    service = TaskLifecycleService(session)
    completed_task(service)

    first = audit_session(session).to_dict()
    second = audit_session(session).to_dict()

    assert first == second


def test_audit_serialization_is_machine_readable():
    session = memory_session()
    audit = audit_session(session).to_dict()

    assert audit["readiness_status"] == "NOT_READY_NO_DATA"
    assert "blocking_reasons" in audit


def test_invalid_audit_status_validation():
    try:
        DatasetQualityAudit(
            readiness_status="BAD",
            leakage_status="PASS",
            sample_counts={},
            label_statistics={},
            missingness={},
            duration_ratio_quality={},
            temporal_coverage={},
            user_diversity={},
            task_type_diversity={},
            historical_feature_audit={},
            duplicate_audit={},
            temporal_split_audit={},
            representativeness={},
            issues=(),
            warnings=(),
            blocking_reasons=(),
        )
    except ValueError as exc:
        assert "readiness_status" in str(exc)
    else:
        raise AssertionError("invalid readiness status should fail")


def test_api_response_includes_quality_audit():
    session = memory_session()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/api/v1/tasks/data-collection/status")
        payload = response.json()["result"]
        assert response.status_code == 200
        assert payload["quality_audit"]["readiness_status"] == "NOT_READY_NO_DATA"
    finally:
        app.dependency_overrides.clear()


def test_readiness_endpoint_includes_quality_audit():
    session = memory_session()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/api/v1/tasks/ml-dataset/readiness")
        payload = response.json()["result"]
        assert response.status_code == 200
        assert "quality_audit" in payload
    finally:
        app.dependency_overrides.clear()


def test_real_database_shape_can_be_audited_with_empty_isolated_database():
    audit = DatasetQualityAuditor().audit_session(memory_session())

    assert audit.sample_counts["raw_task_records"] == 0
    assert audit.blocking_reasons == ("no_real_task_records", "no_f3_dataset_rows")
