"""Leakage-safe ML dataset foundation for Phase F.3."""

from backend.app.ml.datasets.builder import DatasetBuildResult, DurationDatasetBuilder
from backend.app.ml.datasets.events import CanonicalEventHistory, EventType, RawTaskEvent
from backend.app.ml.datasets.leakage import LeakageGuard
from backend.app.ml.datasets.models import (
    DataQualityIssue,
    DatasetMetadata,
    DatasetRow,
    PredictionSnapshot,
)
from backend.app.ml.datasets.report import DatasetReport, DatasetReporter
from backend.app.ml.datasets.splitter import DatasetSplit, TemporalDatasetSplitter
from backend.app.ml.datasets.quality_audit import (
    DatasetQualityAudit,
    DatasetQualityAuditor,
)
from backend.app.ml.datasets.task_database_adapter import (
    TaskAdapterReport,
    TaskDataExtractor,
    TaskExtractionResult,
)
from backend.app.ml.datasets.task_collection_report import (
    TaskCollectionReport,
    TaskCollectionReporter,
)
from backend.app.ml.datasets.duration_quality_gate import (
    DurationExclusionReason,
    DurationQualityAssessment,
    DurationQualityGate,
)

__all__ = [
    "CanonicalEventHistory",
    "DataQualityIssue",
    "DatasetBuildResult",
    "DatasetMetadata",
    "DatasetReport",
    "DatasetReporter",
    "DatasetQualityAudit",
    "DatasetQualityAuditor",
    "DatasetRow",
    "DatasetSplit",
    "DurationDatasetBuilder",
    "DurationExclusionReason",
    "DurationQualityAssessment",
    "DurationQualityGate",
    "EventType",
    "LeakageGuard",
    "PredictionSnapshot",
    "RawTaskEvent",
    "TaskAdapterReport",
    "TaskCollectionReport",
    "TaskCollectionReporter",
    "TaskDataExtractor",
    "TaskExtractionResult",
    "TemporalDatasetSplitter",
]
