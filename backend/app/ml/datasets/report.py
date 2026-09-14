from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from backend.app.ml.datasets.builder import DatasetBuildResult
from backend.app.ml.datasets.models import _freeze_mapping
from backend.app.ml.datasets.splitter import DatasetSplit


@dataclass(frozen=True)
class DatasetReport:
    """Immutable inspection report for F.3 datasets."""

    summary: Mapping[str, Any]
    leakage_checks: Mapping[str, Any]
    missing_value_summary: Mapping[str, int]
    target_summary: Mapping[str, float | None]
    split_sizes: Mapping[str, int]
    quality_warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "summary", _freeze_mapping(self.summary, "summary"))
        object.__setattr__(self, "leakage_checks", _freeze_mapping(self.leakage_checks, "leakage_checks"))
        object.__setattr__(self, "missing_value_summary", _freeze_mapping(self.missing_value_summary, "missing_value_summary"))
        object.__setattr__(self, "target_summary", _freeze_mapping(self.target_summary, "target_summary"))
        object.__setattr__(self, "split_sizes", _freeze_mapping(self.split_sizes, "split_sizes"))
        if not isinstance(self.quality_warnings, tuple):
            raise ValueError("quality_warnings must be a tuple.")


class DatasetReporter:
    """Build deterministic dataset inspection reports without model metrics."""

    def report(self, build: DatasetBuildResult, split: DatasetSplit | None = None) -> DatasetReport:
        """Return an inspection report for rows, issues, targets, and splits."""

        rows = build.rows
        ratios = [row.target["duration_ratio"] for row in rows]
        feature_names = sorted({feature for row in rows for feature in row.features})
        missing = {
            feature: sum(1 for row in rows if row.features.get(feature) is None)
            for feature in feature_names
        }
        split_sizes = {
            "train": 0 if split is None else len(split.train),
            "validation": 0 if split is None else len(split.validation),
            "test": 0 if split is None else len(split.test),
        }
        return DatasetReport(
            summary={
                "raw_event_count": build.metadata.raw_event_count,
                "valid_examples": build.metadata.valid_row_count,
                "rejected_examples": build.metadata.rejected_row_count,
                "feature_count": len(feature_names),
                "user_count": len({row.user_id for row in rows}),
                "task_count": len({row.task_id for row in rows}),
                "timestamp_start": None if build.metadata.source_period_start is None else build.metadata.source_period_start.isoformat(),
                "timestamp_end": None if build.metadata.source_period_end is None else build.metadata.source_period_end.isoformat(),
            },
            leakage_checks={
                "actual_duration_absent_from_features": all(
                    "actual_duration" not in feature for row in rows for feature in row.features
                ),
                "target_absent_from_features": all(
                    "duration_ratio" not in feature for row in rows for feature in row.features
                ),
                "feature_names": tuple(feature_names),
            },
            missing_value_summary=missing,
            target_summary={
                "min_duration_ratio": min(ratios) if ratios else None,
                "max_duration_ratio": max(ratios) if ratios else None,
                "mean_duration_ratio": (sum(ratios) / len(ratios)) if ratios else None,
            },
            split_sizes=split_sizes,
            quality_warnings=tuple(issue.message for issue in build.rejected),
        )
