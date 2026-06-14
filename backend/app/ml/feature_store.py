from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


class FeatureStore:
    """In-memory feature registry for reusable ML and behavior signals.

    The storage backend is a dictionary for now, but the API is designed to be
    replaceable with Redis or a database later.
    """

    def __init__(self) -> None:
        self._store: Dict[int, Dict[str, Any]] = {}

    def store_features(self, user_id: int, features: Dict[str, Any]) -> Dict[str, Any]:
        """Store or overwrite a user's feature bundle."""
        self._store[user_id] = deepcopy(features)
        return deepcopy(self._store[user_id])

    def get_features(self, user_id: int) -> Dict[str, Any]:
        """Return the primary feature set for a user."""
        return deepcopy(self._store.get(user_id, {}))

    def update_feature(self, user_id: int, feature_name: str, value: Any) -> Dict[str, Any]:
        """Update one feature entry for a user."""
        self._store.setdefault(user_id, {})
        self._store[user_id][feature_name] = deepcopy(value)
        return deepcopy(self._store[user_id])

    def get_all_features(self, user_id: int) -> Dict[str, Any]:
        """Return the full feature bundle for a user."""
        return deepcopy(self._store.get(user_id, {}))
