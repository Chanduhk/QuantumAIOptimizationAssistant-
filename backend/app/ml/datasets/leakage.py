from __future__ import annotations

from typing import Mapping


FORBIDDEN_FEATURE_TOKENS = (
    "actual_duration",
    "completion_time",
    "completion_timestamp",
    "completion_status",
    "post_completion",
    "post_task",
    "future_",
    "target",
    "label",
)
FORBIDDEN_EXACT_FEATURES = frozenset({"duration_ratio"})


class LeakageGuard:
    """Fail loudly when target or future-outcome fields enter features."""

    def __init__(self, forbidden_tokens: tuple[str, ...] = FORBIDDEN_FEATURE_TOKENS) -> None:
        self.forbidden_tokens = tuple(sorted(forbidden_tokens))

    def validate_features(self, features: Mapping[str, object]) -> None:
        """Reject features whose names indicate leakage."""

        if not isinstance(features, Mapping):
            raise ValueError("features must be a mapping.")
        for feature_name in sorted(features):
            normalized = str(feature_name).lower()
            if normalized in FORBIDDEN_EXACT_FEATURES:
                raise ValueError(f"feature '{feature_name}' violates leakage guard exact target field.")
            for token in self.forbidden_tokens:
                if token in normalized:
                    raise ValueError(f"feature '{feature_name}' violates leakage guard token '{token}'.")

    def validate_provenance(self, provenance: Mapping[str, object]) -> None:
        """Reject feature provenance marked as unavailable at prediction time."""

        if not isinstance(provenance, Mapping):
            raise ValueError("provenance must be a mapping.")
        for feature_name, availability in sorted(provenance.items()):
            if availability != "available_at_prediction_time":
                raise ValueError(f"feature '{feature_name}' has invalid prediction-time provenance.")
