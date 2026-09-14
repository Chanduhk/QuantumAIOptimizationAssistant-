from __future__ import annotations

from dataclasses import dataclass

from backend.app.ml.datasets.models import DatasetRow


@dataclass(frozen=True)
class DatasetSplit:
    """Immutable chronological train/validation/test split."""

    train: tuple[DatasetRow, ...]
    validation: tuple[DatasetRow, ...]
    test: tuple[DatasetRow, ...]

    def signature(self) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        """Return deterministic example ID signature for split verification."""

        return (
            tuple(row.example_id for row in self.train),
            tuple(row.example_id for row in self.validation),
            tuple(row.example_id for row in self.test),
        )


class TemporalDatasetSplitter:
    """Create deterministic chronological splits without shuffling."""

    def split(self, rows: tuple[DatasetRow, ...], *, train_fraction: float = 0.7, validation_fraction: float = 0.15) -> DatasetSplit:
        """Split rows chronologically into train, validation, and test."""

        if not isinstance(rows, tuple):
            raise ValueError("rows must be a tuple.")
        ordered = tuple(sorted(rows, key=lambda row: (row.prediction_timestamp, row.example_id)))
        count = len(ordered)
        if count == 0:
            return DatasetSplit((), (), ())
        if count < 3:
            return DatasetSplit(ordered, (), ())
        if not 0.0 < train_fraction < 1.0:
            raise ValueError("train_fraction must be between 0 and 1.")
        if not 0.0 <= validation_fraction < 1.0:
            raise ValueError("validation_fraction must be between 0 and 1.")
        train_count = max(1, int(count * train_fraction))
        validation_count = max(1, int(count * validation_fraction))
        if train_count + validation_count >= count:
            validation_count = 1
            train_count = count - 2
        return DatasetSplit(
            train=ordered[:train_count],
            validation=ordered[train_count : train_count + validation_count],
            test=ordered[train_count + validation_count :],
        )
