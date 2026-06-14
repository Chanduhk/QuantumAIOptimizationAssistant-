from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import faiss  # type: ignore
except ImportError:  # pragma: no cover - runtime fallback
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - runtime fallback
    SentenceTransformer = None  # type: ignore


class VectorMemorySystem:
    """Semantic task memory using embeddings with FAISS-backed retrieval when available."""

    def __init__(
        self,
        storage_directory: Optional[str] = None,
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        self.storage_directory = Path(
            storage_directory
            or Path(__file__).resolve().parents[2] / "artifacts" / "vector_memory"
        )
        self.records_path = self.storage_directory / "memory_records.json"
        self.embeddings_path = self.storage_directory / "memory_embeddings.npy"
        self.index_path = self.storage_directory / "memory_faiss.index"
        self.model_name = model_name
        self.records: List[Dict[str, Any]] = []
        self.embedding_matrix = np.empty((0, 384), dtype=np.float32)
        self.model = self._load_model()
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

    def search_similar_tasks(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search semantic memory for similar historical tasks or decisions."""
        if not self.records:
            return []

        query_embedding = self._embed([query])[0].reshape(1, -1)
        distances, indices = self._search_index(query_embedding, limit)

        results: List[Dict[str, Any]] = []
        for distance, index in zip(distances[0], indices[0]):
            if index < 0 or index >= len(self.records):
                continue
            record = dict(self.records[index])
            score = 1.0 / (1.0 + float(distance))
            record["similarity_score"] = round(score, 4)
            record["memory_id"] = index
            results.append(record)
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

    def _load_model(self) -> Optional[Any]:
        if SentenceTransformer is None:
            return None
        try:
            return SentenceTransformer(self.model_name)
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

        if self.embeddings_path.exists():
            self.embedding_matrix = np.load(self.embeddings_path).astype(np.float32)

        if self.embedding_matrix.size == 0 and self.records:
            descriptions = [record["task_description"] for record in self.records]
            self.embedding_matrix = self._embed(descriptions)

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
        if faiss is not None and self.index is not None and hasattr(self.index, "ntotal"):
            faiss.write_index(self.index, str(self.index_path))
