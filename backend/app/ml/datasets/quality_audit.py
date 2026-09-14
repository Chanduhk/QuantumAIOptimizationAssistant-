from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from statistics import median, pstdev
from typing import Any, Mapping

from sqlalchemy.orm import Session

from backend.app.ml.datasets.models import DatasetRow, _freeze_mapping
from backend.app.ml.datasets.task_collection_report import TaskCollectionReport, TaskCollectionReporter
from backend.app.ml.datasets.task_database_adapter import TaskDataExtractor, TaskExtractionResult


READINESS_NOT_READY_NO_DATA = "NOT_READY_NO_DATA"
READINESS_NOT_READY_INSUFFICIENT_DATA = "NOT_READY_INSUFFICIENT_DATA"
READINESS_NOT_READY_DATA_QUALITY = "NOT_READY_DATA_QUALITY"
READINESS_NOT_READY_LEAKAGE = "NOT_READY_LEAKAGE"
READINESS_CONDITIONALLY_READY_FOR_TRAINING_AUDIT = "CONDITIONALLY_READY_FOR_TRAINING_AUDIT"
LEAKAGE_PASS = "PASS"
LEAKAGE_FAIL = "FAIL"
LEAKAGE_INCONCLUSIVE = "INCONCLUSIVE"
MINIMUM_AUDITABLE_ROWS = 3
SUSPICIOUS_RATIO_LOW = 0.25
SUSPICIOUS_RATIO_HIGH = 4.0
FORBIDDEN_FEATURE_NAMES = frozenset(
    {
        "actual_duration",
        "actual_duration_minutes",
        "end_time",
        "completion_timestamp",
        "completed",
        "outcome_valid",
        "duration_ratio",
        "target",
        "label",
        "duration",
        "completion_time",
        "productivity_score",
    }
)
FORBIDDEN_FEATURE_TOKENS = ("actual_duration", "completion_", "future_", "post_", "target", "label")


@dataclass(frozen=True)
class DatasetQualityAudit:
    """Immutable F.4.5 dataset-quality and training-readiness audit result."""

    readiness_status: str
    leakage_status: str
    sample_counts: Mapping[str, int]
    label_statistics: Mapping[str, Any]
    missingness: Mapping[str, Mapping[str, float | int]]
    duration_ratio_quality: Mapping[str, Any]
    temporal_coverage: Mapping[str, Any]
    user_diversity: Mapping[str, Any]
    task_type_diversity: Mapping[str, Any]
    historical_feature_audit: Mapping[str, Any]
    duplicate_audit: Mapping[str, Any]
    temporal_split_audit: Mapping[str, Any]
    representativeness: Mapping[str, Any]
    issues: tuple[str, ...]
    warnings: tuple[str, ...]
    blocking_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.readiness_status not in {
            READINESS_NOT_READY_NO_DATA,
            READINESS_NOT_READY_INSUFFICIENT_DATA,
            READINESS_NOT_READY_DATA_QUALITY,
            READINESS_NOT_READY_LEAKAGE,
            READINESS_CONDITIONALLY_READY_FOR_TRAINING_AUDIT,
        }:
            raise ValueError("readiness_status is invalid.")
        if self.leakage_status not in {LEAKAGE_PASS, LEAKAGE_FAIL, LEAKAGE_INCONCLUSIVE}:
            raise ValueError("leakage_status is invalid.")
        for field_name in (
            "sample_counts",
            "label_statistics",
            "missingness",
            "duration_ratio_quality",
            "temporal_coverage",
            "user_diversity",
            "task_type_diversity",
            "historical_feature_audit",
            "duplicate_audit",
            "temporal_split_audit",
            "representativeness",
        ):
            object.__setattr__(self, field_name, _freeze_mapping(getattr(self, field_name), field_name))
        for field_name in ("issues", "warnings", "blocking_reasons"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple):
                raise ValueError(f"{field_name} must be a tuple.")
            object.__setattr__(self, field_name, tuple(str(item) for item in value))

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-friendly audit representation."""

        return {
            "readiness_status": self.readiness_status,
            "leakage_status": self.leakage_status,
            "sample_counts": self._thaw(self.sample_counts),
            "label_statistics": self._thaw(self.label_statistics),
            "missingness": self._thaw(self.missingness),
            "duration_ratio_quality": self._thaw(self.duration_ratio_quality),
            "temporal_coverage": self._thaw(self.temporal_coverage),
            "user_diversity": self._thaw(self.user_diversity),
            "task_type_diversity": self._thaw(self.task_type_diversity),
            "historical_feature_audit": self._thaw(self.historical_feature_audit),
            "duplicate_audit": self._thaw(self.duplicate_audit),
            "temporal_split_audit": self._thaw(self.temporal_split_audit),
            "representativeness": self._thaw(self.representativeness),
            "issues": self.issues,
            "warnings": self.warnings,
            "blocking_reasons": self.blocking_reasons,
        }

    @classmethod
    def _thaw(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(key): cls._thaw(value[key]) for key in sorted(value)}
        if isinstance(value, tuple):
            return tuple(cls._thaw(item) for item in value)
        return value


class DatasetQualityAuditor:
    """Audit F.3/F.4 dataset outputs without training models or mutating data."""

    def audit_session(self, session: Session, *, user_id: int | None = None) -> DatasetQualityAudit:
        """Extract Task rows through F.4.2/F.3 and audit the resulting dataset."""

        extraction = TaskDataExtractor(session).extract(user_id=user_id)
        collection = TaskCollectionReporter(session).report(user_id=user_id)
        return self.audit_extraction(extraction, collection_report=collection)

    def audit_extraction(
        self,
        extraction: TaskExtractionResult,
        *,
        collection_report: TaskCollectionReport | None = None,
    ) -> DatasetQualityAudit:
        """Return deterministic quality, leakage, temporal, and readiness diagnostics."""

        rows = extraction.dataset_build.rows
        split = extraction.dataset_split
        counts = self._sample_counts(extraction, collection_report)
        leakage_issues = self._leakage_issues(rows)
        label_stats = self._label_statistics(rows)
        missingness = self._missingness(rows)
        ratio_quality = self._duration_ratio_quality(rows)
        temporal = self._temporal_coverage(rows)
        user_diversity = self._user_diversity(rows)
        task_type_diversity = self._task_type_diversity(rows)
        historical = self._historical_feature_audit(rows)
        duplicates = self._duplicate_audit(rows)
        split_audit = self._temporal_split_audit(split)
        representativeness = self._representativeness(rows)

        issues = tuple(sorted({*leakage_issues, *duplicates["issues"], *split_audit["issues"]}))
        warnings = tuple(
            sorted(
                {
                    *ratio_quality["warnings"],
                    *temporal["warnings"],
                    *user_diversity["warnings"],
                    *task_type_diversity["warnings"],
                    *historical["warnings"],
                    *representativeness["warnings"],
                }
            )
        )
        readiness, blocking = self._readiness(
            rows=rows,
            counts=counts,
            leakage_issues=leakage_issues,
            duplicate_issues=duplicates["issues"],
            split_issues=split_audit["issues"],
            ratio_issues=ratio_quality["issues"],
        )
        return DatasetQualityAudit(
            readiness_status=readiness,
            leakage_status=LEAKAGE_FAIL if leakage_issues else LEAKAGE_PASS if rows else LEAKAGE_INCONCLUSIVE,
            sample_counts=counts,
            label_statistics=label_stats,
            missingness=missingness,
            duration_ratio_quality=ratio_quality,
            temporal_coverage=temporal,
            user_diversity=user_diversity,
            task_type_diversity=task_type_diversity,
            historical_feature_audit=historical,
            duplicate_audit=duplicates,
            temporal_split_audit=split_audit,
            representativeness=representativeness,
            issues=issues,
            warnings=warnings,
            blocking_reasons=blocking,
        )

    @staticmethod
    def _sample_counts(extraction: TaskExtractionResult, collection: TaskCollectionReport | None) -> dict[str, int]:
        return {
            "raw_task_records": 0 if collection is None else collection.total_task_records,
            "completed_task_records": 0 if collection is None else collection.completed_records,
            "lifecycle_valid_records": 0 if collection is None else collection.lifecycle_valid_records,
            "f3_eligible_records": extraction.report.eligible_records,
            "rejected_records": extraction.report.rejected_records,
            "dataset_rows": len(extraction.dataset_build.rows),
            "raw_events": len(extraction.events),
        }

    @staticmethod
    def _label_statistics(rows: tuple[DatasetRow, ...]) -> dict[str, Any]:
        ratios = [float(row.target["duration_ratio"]) for row in rows]
        if not ratios:
            return {"status": "NO_DATA", "count": 0}
        ordered = sorted(ratios)
        stats: dict[str, Any] = {
            "status": "VALID_DATA" if len(ratios) >= MINIMUM_AUDITABLE_ROWS else "INSUFFICIENT_DATA",
            "count": len(ratios),
            "min": ordered[0],
            "max": ordered[-1],
            "mean": round(sum(ratios) / len(ratios), 8),
            "median": round(float(median(ratios)), 8),
            "p25": DatasetQualityAuditor._percentile(ordered, 0.25),
            "p75": DatasetQualityAuditor._percentile(ordered, 0.75),
        }
        if len(ratios) >= 2:
            stats["std"] = round(float(pstdev(ratios)), 8)
        return stats

    @staticmethod
    def _missingness(rows: tuple[DatasetRow, ...]) -> dict[str, dict[str, float | int]]:
        if not rows:
            return {}
        feature_names = sorted({key for row in rows for key in row.features})
        result: dict[str, dict[str, float | int]] = {}
        for feature in feature_names:
            missing = sum(1 for row in rows if row.features.get(feature) is None)
            result[feature] = {"missing_count": missing, "missing_percentage": round((missing / len(rows)) * 100.0, 4)}
        label_missing = sum(1 for row in rows if row.target.get("duration_ratio") is None)
        result["duration_ratio_label"] = {
            "missing_count": label_missing,
            "missing_percentage": round((label_missing / len(rows)) * 100.0, 4),
        }
        return result

    @staticmethod
    def _duration_ratio_quality(rows: tuple[DatasetRow, ...]) -> dict[str, Any]:
        issues: list[str] = []
        warnings: list[str] = []
        ratios = [float(row.target["duration_ratio"]) for row in rows]
        invalid = sum(1 for value in ratios if not math.isfinite(value) or value <= 0)
        suspicious_low = sum(1 for value in ratios if 0 < value < SUSPICIOUS_RATIO_LOW)
        suspicious_high = sum(1 for value in ratios if value > SUSPICIOUS_RATIO_HIGH)
        if invalid:
            issues.append("invalid_duration_ratio_values")
        if suspicious_low:
            warnings.append("unusually_small_duration_ratios_observed")
        if suspicious_high:
            warnings.append("unusually_large_duration_ratios_observed")
        return {
            "invalid_count": invalid,
            "suspicious_low_count": suspicious_low,
            "suspicious_high_count": suspicious_high,
            "hard_invalid_threshold": "non_finite_or_less_than_or_equal_to_zero",
            "suspicious_low_threshold": SUSPICIOUS_RATIO_LOW,
            "suspicious_high_threshold": SUSPICIOUS_RATIO_HIGH,
            "issues": tuple(issues),
            "warnings": tuple(warnings),
        }

    @staticmethod
    def _temporal_coverage(rows: tuple[DatasetRow, ...]) -> dict[str, Any]:
        if not rows:
            return {"status": "UNAVAILABLE", "warnings": ("temporal_coverage_unavailable_no_rows",)}
        times = sorted(row.prediction_timestamp for row in rows)
        span_minutes = (times[-1] - times[0]).total_seconds() / 60.0
        return {
            "status": "OBSERVED",
            "earliest_prediction_timestamp": times[0].isoformat(),
            "latest_prediction_timestamp": times[-1].isoformat(),
            "span_minutes": round(span_minutes, 4),
            "distinct_prediction_days": len({time.date().isoformat() for time in times}),
            "warnings": () if len(rows) >= MINIMUM_AUDITABLE_ROWS else ("limited_temporal_coverage",),
        }

    @staticmethod
    def _user_diversity(rows: tuple[DatasetRow, ...]) -> dict[str, Any]:
        counts = DatasetQualityAuditor._counts(row.user_id for row in rows)
        warnings = ("single_user_dataset_limits_generalization",) if len(counts) == 1 and rows else ()
        return {"user_count": len(counts), "records_per_user": counts, "warnings": warnings}

    @staticmethod
    def _task_type_diversity(rows: tuple[DatasetRow, ...]) -> dict[str, Any]:
        counts = DatasetQualityAuditor._counts(str(row.features.get("task_type", "unknown")) for row in rows)
        warnings = ("single_task_type_dataset_limits_generalization",) if len(counts) == 1 and rows else ()
        return {"task_type_count": len(counts), "records_per_task_type": counts, "warnings": warnings}

    @staticmethod
    def _historical_feature_audit(rows: tuple[DatasetRow, ...]) -> dict[str, Any]:
        warnings: list[str] = []
        missing = [row.example_id for row in rows if "prior_completed_task_count" not in row.features]
        negative = [row.example_id for row in rows if float(row.features.get("prior_completed_task_count", 0)) < 0]
        chronological_errors = [
            row.example_id
            for row in rows
            if int(row.features.get("prior_completed_task_count", 0)) >= len([candidate for candidate in rows if candidate.user_id == row.user_id])
        ]
        if not rows:
            warnings.append("historical_feature_audit_unavailable_no_rows")
        return {
            "missing_prior_completed_task_count": tuple(sorted(missing)),
            "negative_prior_completed_task_count": tuple(sorted(negative)),
            "possible_self_history_leakage": tuple(sorted(chronological_errors)),
            "cold_start_rows": sum(1 for row in rows if int(row.features.get("prior_completed_task_count", 0)) == 0),
            "warnings": tuple(warnings),
        }

    @staticmethod
    def _leakage_issues(rows: tuple[DatasetRow, ...]) -> tuple[str, ...]:
        issues: list[str] = []
        for row in rows:
            for feature in sorted(row.features):
                normalized = str(feature).lower()
                if normalized in FORBIDDEN_FEATURE_NAMES or any(token in normalized for token in FORBIDDEN_FEATURE_TOKENS):
                    issues.append(f"leakage_feature:{row.example_id}:{feature}")
            provenance = row.provenance.get("feature_provenance")
            if provenance:
                for item in provenance:
                    if isinstance(item, tuple) and len(item) == 2 and item[1] != "available_at_prediction_time":
                        issues.append(f"invalid_feature_provenance:{row.example_id}:{item[0]}")
        return tuple(sorted(set(issues)))

    @staticmethod
    def _duplicate_audit(rows: tuple[DatasetRow, ...]) -> dict[str, Any]:
        task_counts = DatasetQualityAuditor._counts(row.task_id for row in rows)
        example_counts = DatasetQualityAuditor._counts(row.example_id for row in rows)
        duplicate_tasks = tuple(sorted(key for key, count in task_counts.items() if count > 1))
        duplicate_examples = tuple(sorted(key for key, count in example_counts.items() if count > 1))
        issues = []
        if duplicate_tasks:
            issues.append("duplicate_task_ids")
        if duplicate_examples:
            issues.append("duplicate_example_ids")
        return {
            "duplicate_task_ids": duplicate_tasks,
            "duplicate_example_ids": duplicate_examples,
            "issues": tuple(issues),
        }

    @staticmethod
    def _temporal_split_audit(split: Any) -> dict[str, Any]:
        partitions = (("train", split.train), ("validation", split.validation), ("test", split.test))
        memberships: dict[str, str] = {}
        issues: list[str] = []
        for name, rows in partitions:
            ordered = tuple(sorted(rows, key=lambda row: (row.prediction_timestamp, row.example_id)))
            if tuple(rows) != ordered:
                issues.append(f"{name}_split_not_chronological")
            for row in rows:
                if row.example_id in memberships:
                    issues.append("duplicate_split_membership")
                memberships[row.example_id] = name
        max_train = max((row.prediction_timestamp for row in split.train), default=None)
        min_val = min((row.prediction_timestamp for row in split.validation), default=None)
        max_val = max((row.prediction_timestamp for row in split.validation), default=None)
        min_test = min((row.prediction_timestamp for row in split.test), default=None)
        if max_train and min_val and max_train > min_val:
            issues.append("train_validation_temporal_overlap")
        if max_val and min_test and max_val > min_test:
            issues.append("validation_test_temporal_overlap")
        return {
            "train_size": len(split.train),
            "validation_size": len(split.validation),
            "test_size": len(split.test),
            "issues": tuple(sorted(set(issues))),
        }

    @staticmethod
    def _representativeness(rows: tuple[DatasetRow, ...]) -> dict[str, Any]:
        warnings: list[str] = []
        if len(rows) < MINIMUM_AUDITABLE_ROWS:
            warnings.append("too_few_rows_for_representativeness_claims")
        return {"status": "DESCRIPTIVE_ONLY", "warnings": tuple(warnings)}

    @staticmethod
    def _readiness(
        *,
        rows: tuple[DatasetRow, ...],
        counts: Mapping[str, int],
        leakage_issues: tuple[str, ...],
        duplicate_issues: tuple[str, ...],
        split_issues: tuple[str, ...],
        ratio_issues: tuple[str, ...],
    ) -> tuple[str, tuple[str, ...]]:
        blocking: list[str] = []
        if counts["raw_task_records"] == 0 and len(rows) == 0:
            return READINESS_NOT_READY_NO_DATA, ("no_real_task_records", "no_f3_dataset_rows")
        if leakage_issues:
            return READINESS_NOT_READY_LEAKAGE, ("feature_leakage_detected",)
        if duplicate_issues or split_issues or ratio_issues:
            blocking.extend([*duplicate_issues, *split_issues, *ratio_issues])
            return READINESS_NOT_READY_DATA_QUALITY, tuple(sorted(set(blocking)))
        if len(rows) < MINIMUM_AUDITABLE_ROWS:
            return READINESS_NOT_READY_INSUFFICIENT_DATA, ("insufficient_dataset_rows_for_statistical_audit",)
        return READINESS_CONDITIONALLY_READY_FOR_TRAINING_AUDIT, ()

    @staticmethod
    def _counts(values: Any) -> dict[str, int]:
        result: dict[str, int] = {}
        for value in values:
            key = str(value)
            result[key] = result.get(key, 0) + 1
        return {key: result[key] for key in sorted(result)}

    @staticmethod
    def _percentile(ordered: list[float], fraction: float) -> float | None:
        if not ordered:
            return None
        index = (len(ordered) - 1) * fraction
        lower = math.floor(index)
        upper = math.ceil(index)
        if lower == upper:
            return round(ordered[int(index)], 8)
        weight = index - lower
        return round(ordered[lower] * (1.0 - weight) + ordered[upper] * weight, 8)
