# F.4.5 Dataset Quality and Statistical Audit

## Objective

F.4.5 adds a read-only quality gate between real task data collection and future model training. It audits F.4.2/F.3 dataset output for structural validity, label availability, missingness, leakage, temporal safety, diversity, duplicates, outliers, and training-readiness state.

F.4.5 does not train models, create model artifacts, populate synthetic production data, or modify quantum optimization code.

## Audit Architecture

Input flow:

`Task` records -> `TaskDataExtractor` -> F.3 dataset rows -> `DatasetQualityAuditor`

The audit consumes existing F.3/F.4 outputs. It does not rebuild features differently and does not duplicate dataset-generation logic.

## Audit Categories

- Sample counts: raw tasks, completed tasks, lifecycle-valid rows, F.3 eligible rows, rejected records, dataset rows.
- Label audit: duration-ratio count and descriptive statistics only when rows exist.
- Missingness: feature and label missing counts/percentages.
- Duration-ratio quality: hard-invalid values and unusual small/large ratios are reported, not deleted.
- Temporal coverage: earliest/latest prediction timestamp and span when data exists.
- User diversity: record counts by user identifier without exposing private content.
- Task-type diversity: observed task-type distribution.
- Historical feature audit: cold-start rows and possible self-history leakage signals.
- Leakage audit: forbidden prediction feature names and invalid provenance.
- Duplicate audit: duplicate task/example identities.
- Temporal split audit: chronological split ordering and duplicate split membership.
- Representativeness: descriptive-only diagnostics.

## Readiness Decision

Machine-readable states:

- `NOT_READY_NO_DATA`
- `NOT_READY_INSUFFICIENT_DATA`
- `NOT_READY_DATA_QUALITY`
- `NOT_READY_LEAKAGE`
- `CONDITIONALLY_READY_FOR_TRAINING_AUDIT`

The audit intentionally does not declare full F.5 training readiness from tiny datasets. F.5 can begin only after legitimate real data has accumulated and quality, leakage, temporal, label, missingness, and diversity checks are acceptable.

## Leakage Rules

Prediction features must not include current-task post-outcome or target-derived fields:

- `actual_duration`
- `actual_duration_minutes`
- `end_time`
- `completion_timestamp`
- `completed`
- `outcome_valid`
- `duration_ratio`
- `target`
- `label`
- `duration`
- `completion_time`
- `productivity_score`
- `future_*`
- `post_*`

The audit fails readiness with `NOT_READY_LEAKAGE` if any such feature is detected.

## Current Real Database Result

At implementation time, the configured database was audited as:

- task records: 0
- completed task records: 0
- lifecycle-valid records: 0
- F.3 eligible records: 0
- dataset rows: 0

The current real database contains no legitimate training samples, therefore F.5 model training is not yet justified.

## Isolated Validation

Automated tests and practical smoke checks use isolated in-memory databases and synthetic validation records only. These records are not real user data and are not inserted into the configured application database.

## Limitations

F.4.5 provides descriptive statistics and machine-checkable readiness. It does not establish model-performance thresholds, train/validation quality targets, or model-specific sample-size requirements. Those belong to future F.5/F.6 work after real data exists.

## F.5 Prerequisites

Before training:

- accumulate legitimate completed task lifecycle records
- verify leakage audit passes
- verify temporal split safety
- inspect label distribution and outliers
- inspect missingness
- inspect task-type and user/history diversity
- decide model-specific minimum data requirements
- keep synthetic/test data separate from real training data
