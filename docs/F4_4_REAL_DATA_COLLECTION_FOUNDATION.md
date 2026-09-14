# F.4.4 Real Data Collection Foundation

## Objective

F.4.4 makes normal task usage capable of producing future ML training records through the existing lifecycle path. It does not train models, create model artifacts, populate synthetic production data, or modify the quantum optimization architecture.

## Integration Points

- `backend/main.py` exposes task lifecycle API endpoints for create, start, complete, dataset readiness, and data-collection status.
- `backend/app/services/task_lifecycle_service.py` owns lifecycle validation and timestamp/duration recording.
- `backend/app/ml/datasets/task_database_adapter.py` converts eligible `Task` rows into F.3 `RawTaskEvent` records.
- `backend/app/ml/datasets/task_collection_report.py` reports whether stored `Task` rows are lifecycle-valid and F.3-eligible.

## Lifecycle Flow

1. Create task: records prediction-time fields only: `user_id`, `task_type`, `priority`, `estimated_duration`, and `created_at`.
2. Start task: records `start_time`; it must not be before `created_at`.
3. Complete task: records `end_time`, `actual_duration`, `completed=True`, `lifecycle_state=completed`, and `outcome_valid=True`.

`actual_duration` is derived from `end_time - start_time` unless a caller supplies a matching value. Conflicting supplied values are rejected.

## Prediction-Time vs Post-Outcome Data

Prediction-time data may become ML features:

- `estimated_duration`
- `priority`
- `task_type`
- `created_at`
- `start_time` only when legitimately recorded before completion
- historical aggregates from tasks completed before the prediction boundary

Post-outcome data is label/eligibility data only:

- `actual_duration`
- `end_time`
- `completed`
- `outcome_valid`
- `BehaviorData.duration`
- `BehaviorData.completion_time`
- `BehaviorData.productivity_score`

## Leakage Protections

F.3 still owns feature-level leakage validation. F.4.4 preserves leakage safety by routing all dataset generation through the F.4.2 adapter and F.3 builder. The collection report never exposes task titles or post-outcome behavior fields as features.

## Legacy Data Handling

Legacy rows are preserved. Missing lifecycle timestamps are not fabricated. Invalid or incomplete rows are counted and reported, not repaired silently. F.4.2 may still use `start_time` as a conservative prediction boundary for legacy rows without `created_at`.

## Privacy

The dataset path uses structured task metadata and avoids propagating task titles or free-form content into ML features. No sensitive credentials, contact details, or personal free-form notes are collected for ML training in F.4.4.

## Observability

The data-collection status report includes:

- total task records
- completed and incomplete records
- lifecycle-valid and lifecycle-invalid records
- F.3-eligible records
- rejected records and reasons
- valid actual-duration records
- missing estimates and timestamps
- users and task types represented
- whether real training samples are unavailable

## Current Real-Data Status

At implementation time, the configured real database contains no task rows and no eligible F.3 dataset rows. F.4.4 enables future legitimate data collection; it does not mean enough real data exists for model training.

## Remaining Limitations

Pause/resume, cancellation, failure, rescheduling, and full lifecycle event history remain future extensions. F.4.5 should audit the quality and statistical readiness of accumulated real task data before F.5 model training is considered.
