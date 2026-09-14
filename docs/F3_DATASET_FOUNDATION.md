# Phase F.3 Dataset Foundation

This document describes the leakage-safe dataset foundation for the first supervised ML target:

```text
duration_ratio = actual_duration_minutes / estimated_duration_minutes
```

F.3 does not train models, create model artifacts, download public datasets, or claim model performance. Synthetic data used in tests or smoke checks is demonstration data only.

## Architecture

The F.3 package lives in `backend/app/ml/datasets/` and is isolated from the existing engines, Executive Brain, and quantum architecture.

```text
RawTaskEvent
    -> EventHistoryBuilder
    -> CanonicalEventHistory
    -> PredictionSnapshot
    -> DurationDatasetBuilder
    -> LeakageGuard
    -> DatasetRow
    -> TemporalDatasetSplitter
    -> DatasetReporter
```

## Raw Events

The event contract supports task lifecycle events required to generate duration-ratio training examples:

- `task_created`
- `task_scheduled`
- `task_started`
- `task_paused`
- `task_resumed`
- `task_completed`
- `task_failed`
- `task_cancelled`
- `task_rescheduled`
- `context_recorded`

Each event carries `event_id`, `task_id`, `user_id`, `event_type`, `timestamp`, immutable payload, and schema version. Event validation rejects malformed identifiers, invalid timestamps, unsupported event types, invalid priorities, non-positive estimates, negative actual durations, NaN, and Infinity.

## Prediction-Time Freeze

Every generated row has an explicit `prediction_timestamp`. Feature extraction may only use values available at or before that timestamp.

The label pipeline observes the future task outcome separately. `actual_duration_minutes` is used only to generate `duration_ratio` and is never included in the feature vector.

## Feature Schema

Current F.3 features are intentionally compact:

- `estimated_duration_minutes`
- `priority`
- `task_type`
- `prediction_hour`
- `prediction_day_of_week`
- `time_since_task_created_minutes`
- `scheduled_start_hour`
- `hours_until_scheduled_start`
- `prior_completed_task_count`
- `prior_duration_ratio_mean`
- `prior_duration_ratio_median`
- `prior_same_type_duration_ratio_mean`

Historical features include only completed outcomes known before the current row's prediction timestamp.

## Leakage Rules

The leakage guard rejects feature names or provenance that indicate post-outcome information. Protected fields include actual duration, completion timestamps/status, post-completion fields, future-prefixed fields, target fields, labels, and direct `duration_ratio` features.

Historical duration-ratio aggregates are allowed only because they are computed from prior completed outcomes whose outcome timestamps are before the prediction timestamp.

## Label Generation

Rows are labeled only when a valid completed outcome exists. The builder rejects cancelled tasks, failed tasks without a completed outcome, incomplete tasks, missing estimates, zero estimates, non-finite durations, and outcomes that occur before or at the prediction timestamp.

If `actual_duration_minutes` is not supplied on completion, the builder can derive actual duration from `task_started` and `task_completed`, subtracting paused intervals.

## Data Quality

The builder returns valid rows and explicit rejected/quarantined issues. Invalid data is not silently discarded. Examples include duplicate event IDs, impossible pause/resume order, duplicate terminal outcomes, events after terminal outcomes, missing completed outcomes, and invalid label values.

## Dataset Versioning

F.3 records lightweight immutable metadata:

- dataset version
- schema version
- feature version
- label version
- deterministic creation marker
- source period
- raw event count
- valid/invalid event counts
- valid/rejected row counts

The version metadata is deterministic for identical source events.

## Temporal Splitting

`TemporalDatasetSplitter` sorts rows by prediction timestamp and example ID, then produces train/validation/test splits without random shuffling. This preserves chronological ordering and prevents future observations from entering earlier evaluation partitions.

## Reporting

`DatasetReporter` reports dataset inspection information only:

- event and example counts
- feature count
- user/task counts
- timestamp range
- missing values
- target distribution summary
- split sizes
- leakage checks
- quality warnings

It does not report model metrics.

## Limitations

F.3 defines and validates the dataset foundation. It does not yet connect to production database extraction, train a model, evaluate model metrics, persist dataset artifacts, or provide an API. Those belong to later F phases.
