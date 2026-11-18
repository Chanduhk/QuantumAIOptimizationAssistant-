from __future__ import annotations

import json
import io
import logging
import os
from pathlib import Path
from contextlib import redirect_stderr
from threading import Event, Lock, Thread
from typing import Any, Dict, List, Optional
from time import perf_counter

import numpy as np

try:
    import faiss  # type: ignore
except ImportError:  # pragma: no cover - runtime fallback
    faiss = None


class VectorMemorySystem:
    """Semantic task memory using embeddings with FAISS-backed retrieval when available."""

    _model_cache: Dict[str, Any] = {}
    _model_cache_lock = Lock()
    _model_load_started: set[str] = set()
    _model_load_events: Dict[str, Event] = {}
    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        storage_directory: Optional[str] = None,
        model_name: Optional[str] = "all-MiniLM-L6-v2",
    ) -> None:
        self.storage_directory = Path(
            storage_directory
            or os.getenv("HELIOX_VECTOR_MEMORY_DIR")
            or Path(__file__).resolve().parents[2] / "artifacts" / "vector_memory"
        )
        self.records_path = self.storage_directory / "memory_records.json"
        self.embeddings_path = self.storage_directory / "memory_embeddings.npy"
        self.embedding_metadata_path = self.storage_directory / "memory_embedding_metadata.json"
        self.index_path = self.storage_directory / "memory_faiss.index"
        self.model_name = model_name
        self.records: List[Dict[str, Any]] = []
        self.embedding_matrix = np.empty((0, 384), dtype=np.float32)
        self._load_model()
        self.index = None
        self._load_storage()

    def store_memory(self, task_description: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Store a semantically searchable memory record."""
        if not task_description.strip():
            raise ValueError("task_description is required.")

        embedding = self._embed([task_description])[0]
        record = {
            "task_description": task_description,
            "metadata": metadata,
        }
        self.records.append(record)
        self.embedding_matrix = self._append_embedding(embedding)
        self._rebuild_index()
        self._persist()

        return {
            "memory_id": len(self.records) - 1,
            "stored": True,
            "metadata": metadata,
        }

    def search_similar_tasks(
        self, query: str, limit: int = 5, *, user_id: int | None = None
    ) -> List[Dict[str, Any]]:
        """Search semantic memory for similar historical tasks or decisions."""
        if not self.records:
            return []

        query_embedding = self._embed([query])[0].reshape(1, -1)
        search_limit = len(self.records) if user_id is not None else limit
        distances, indices = self._search_index(query_embedding, search_limit)

        results: List[Dict[str, Any]] = []
        for distance, index in zip(distances[0], indices[0]):
            if index < 0 or index >= len(self.records):
                continue
            record = dict(self.records[index])
            metadata = record.get("metadata")
            if user_id is not None and (
                not isinstance(metadata, dict) or metadata.get("user_id") != user_id
            ):
                continue
            score = 1.0 / (1.0 + float(distance))
            record["similarity_score"] = round(score, 4)
            record["memory_id"] = index
            results.append(record)
            if len(results) >= limit:
                break
        return results

    def retrieve_context(self, user_id: int, limit: int = 10) -> Dict[str, Any]:
        """Retrieve recent and user-specific semantic memory context."""
        matching_records = [
            {
                **record,
                "memory_id": index,
            }
            for index, record in enumerate(self.records)
            if record.get("metadata", {}).get("user_id") == user_id
        ]
        return {
            "user_id": user_id,
            "memory_count": len(matching_records),
            "recent_memories": matching_records[-limit:],
        }

    @property
    def model(self) -> Optional[Any]:
        if not self.model_name:
            return None
        with self._model_cache_lock:
            return self._model_cache.get(self.model_name)

    @model.setter
    def model(self, value: Optional[Any]) -> None:
        if self.model_name:
            with self._model_cache_lock:
                self._model_cache[self.model_name] = value

    def _load_model(self) -> Optional[Any]:
        if not self.model_name:
            return None
        with self._model_cache_lock:
            if self.model_name in self._model_cache:
                return self._model_cache[self.model_name]
            if self.model_name in self._model_load_started:
                # A request arriving during local model warm-up uses the existing
                # deterministic embedding fallback instead of blocking on import.
                return None
            self._model_load_started.add(self.model_name)
            self._model_load_events[self.model_name] = Event()

        # Start warm-up asynchronously so instantiation never blocks for ~50 seconds on cold import
        Thread(target=self._load_model_and_publish, name="heliox-local-embedding-warmup", daemon=True).start()
        return None

    @classmethod
    def preload_model_async(cls, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Warm a local model in the background without blocking an API request."""
        with cls._model_cache_lock:
            if model_name in cls._model_cache or model_name in cls._model_load_started:
                return
            cls._model_load_started.add(model_name)
            cls._model_load_events[model_name] = Event()

        cls._logger.info("Starting one-time local-only embedding model initialization: model=%s", model_name)
        loader = cls.__new__(cls)
        loader.model_name = model_name
        loader.storage_directory = Path(
            os.getenv("HELIOX_VECTOR_MEMORY_DIR")
            or Path(__file__).resolve().parents[2] / "artifacts" / "vector_memory"
        )
        Thread(target=loader._load_model_and_publish, name="heliox-local-embedding-warmup", daemon=True).start()

    @classmethod
    def wait_for_model_load(cls, model_name: str, timeout: float | None = None) -> bool:
        """Wait for model-load completion; primarily useful to deterministic tests."""
        with cls._model_cache_lock:
            event = cls._model_load_events.get(model_name)
        return event.wait(timeout) if event is not None else model_name in cls._model_cache

    def _load_model_and_publish(self) -> Optional[Any]:
        assert self.model_name is not None
        started = perf_counter()
        try:
            model = self._load_model_uncached()
        except Exception:
            self._logger.exception("Local-only embedding model initialization failed; deterministic fallback remains active.")
            model = None
        with self._model_cache_lock:
            self._model_cache[self.model_name] = model
            event = self._model_load_events.get(self.model_name)
            if event is not None:
                event.set()
        self._logger.info(
            "Local-only embedding model initialization completed: available=%s elapsed_seconds=%.3f",
            model is not None,
            perf_counter() - started,
        )
        return model

    def _find_local_model_path(self) -> Optional[str]:
        if not self.model_name:
            return None
        clean_name = self.model_name.split("/")[-1]
        
        # 1. Local workspace / repository artifacts directory
        storage_dir = getattr(self, "storage_directory", None) or (
            Path(__file__).resolve().parents[2] / "artifacts" / "vector_memory"
        )
        artifact_paths = [
            storage_dir / clean_name,
            Path(__file__).resolve().parents[2] / "artifacts" / "vector_memory" / clean_name,
        ]
        for p in artifact_paths:
            if p.exists() and (p / "modules.json").exists():
                return str(p)

        # 2. Local Hugging Face Hub snapshot directory
        hub_snapshots = (
            Path.home()
            / ".cache"
            / "huggingface"
            / "hub"
            / f"models--sentence-transformers--{clean_name}"
            / "snapshots"
        )
        if hub_snapshots.exists():
            for snap in sorted(hub_snapshots.iterdir(), reverse=True):
                if snap.is_dir() and (snap / "modules.json").exists():
                    return str(snap)

        return None

    def _load_model_uncached(self) -> Optional[Any]:
        try:
            with redirect_stderr(io.StringIO()):
                from sentence_transformers import SentenceTransformer

                # Check if exact local snapshot directory exists first
                local_dir = self._find_local_model_path()
                if local_dir is not None:
                    return SentenceTransformer(local_dir, local_files_only=True)

                # Fallback to local cache lookup by name
                try:
                    return SentenceTransformer(f"sentence-transformers/{self.model_name}", local_files_only=True)
                except Exception:
                    return SentenceTransformer(self.model_name, local_files_only=True)
        except Exception:
            return None

    def _embed(self, texts: List[str]) -> np.ndarray:
        if self.model is not None:
            embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return embeddings.astype(np.float32)

        # Fallback deterministic embeddings when the transformer model is unavailable.
        vectors = []
        for text in texts:
            vector = np.zeros(384, dtype=np.float32)
            for index, char in enumerate(text.encode("utf-8")):
                vector[index % 384] += float(char)
            norm = np.linalg.norm(vector)
            vectors.append(vector / norm if norm else vector)
        return np.array(vectors, dtype=np.float32)

    def _append_embedding(self, embedding: np.ndarray) -> np.ndarray:
        if self.embedding_matrix.size == 0:
            return embedding.reshape(1, -1).astype(np.float32)
        return np.vstack([self.embedding_matrix, embedding.reshape(1, -1).astype(np.float32)])

    def _rebuild_index(self) -> None:
        if self.embedding_matrix.size == 0:
            self.index = None
            return

        if faiss is not None:
            dimension = self.embedding_matrix.shape[1]
            self.index = faiss.IndexFlatL2(dimension)
            self.index.add(self.embedding_matrix)
            return

        self.index = "numpy"

    def _search_index(self, query_embedding: np.ndarray, limit: int) -> tuple[np.ndarray, np.ndarray]:
        if faiss is not None and self.index is not None and hasattr(self.index, "search"):
            return self.index.search(query_embedding.astype(np.float32), limit)

        if self.embedding_matrix.size == 0:
            return np.array([[]], dtype=np.float32), np.array([[]], dtype=np.int64)

        distances = np.linalg.norm(self.embedding_matrix - query_embedding, axis=1)
        top_indices = np.argsort(distances)[:limit]
        return distances[top_indices].reshape(1, -1), top_indices.reshape(1, -1)

    def _load_storage(self) -> None:
        self.storage_directory.mkdir(parents=True, exist_ok=True)

        if self.records_path.exists():
            self.records = json.loads(self.records_path.read_text(encoding="utf-8"))

        embedding_mode = self._embedding_mode()
        try:
            stored_mode = json.loads(self.embedding_metadata_path.read_text(encoding="utf-8")).get("mode")
        except (OSError, ValueError, AttributeError):
            stored_mode = None

        if self.embeddings_path.exists() and stored_mode == embedding_mode:
            self.embedding_matrix = np.load(self.embeddings_path).astype(np.float32)
        elif self.records:
            # Rebuild derived vectors when the embedding provider changes. This
            # preserves memory records without mixing fallback and model spaces.
            descriptions = [record["task_description"] for record in self.records]
            self.embedding_matrix = self._embed(descriptions)
            self._persist()
        elif self.embeddings_path.exists() and stored_mode == embedding_mode:
            self.embedding_matrix = np.load(self.embeddings_path).astype(np.float32)

        if faiss is not None and self.index_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
            except Exception:
                self._rebuild_index()
        else:
            self._rebuild_index()

    def _persist(self) -> None:
        self.storage_directory.mkdir(parents=True, exist_ok=True)
        self.records_path.write_text(json.dumps(self.records, indent=2), encoding="utf-8")
        np.save(self.embeddings_path, self.embedding_matrix.astype(np.float32))
        self.embedding_metadata_path.write_text(
            json.dumps({"mode": self._embedding_mode()}, indent=2),
            encoding="utf-8",
        )
        if faiss is not None and self.index is not None and hasattr(self.index, "ntotal"):
            faiss.write_index(self.index, str(self.index_path))

    def _embedding_mode(self) -> str:
        return f"sentence_transformer:{self.model_name}" if self.model is not None else "deterministic_fallback"
