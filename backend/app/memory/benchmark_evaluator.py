from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.app.memory.vector_memory import VectorMemorySystem

logger = logging.getLogger(__name__)

# Standard semantic benchmark corpus and query test suite
BENCHMARK_TASK_CORPUS = [
    {"task_id": "M1", "task_description": "Implement JWT authentication token validation middleware", "category": "security"},
    {"task_id": "M2", "task_description": "Optimize SQLite database indexing and connection pool sizing", "category": "database"},
    {"task_id": "M3", "task_description": "Design executive presentation slide deck for quarterly business review", "category": "planning"},
    {"task_id": "M4", "task_description": "Formulate QUBO quadratic assignment problem for task scheduling", "category": "quantum"},
    {"task_id": "M5", "task_description": "Refactor React frontend navigation bar and mobile drawer layout", "category": "frontend"},
    {"task_id": "M6", "task_description": "Fix user session cookie expiration and CSRF security header", "category": "security"},
    {"task_id": "M7", "task_description": "Tune QAOA variational circuit parameters gamma and beta on simulator", "category": "quantum"},
    {"task_id": "M8", "task_description": "Write automated end-to-end Playwright tests for user login flow", "category": "testing"},
    {"task_id": "M9", "task_description": "Analyze team sprint velocity and project burn-down charts", "category": "planning"},
    {"task_id": "M10", "task_description": "Benchmark classical branch-and-bound solver against exact QUBO enumeration", "category": "quantum"},
]

BENCHMARK_QUERIES = [
    {
        "query": "How do I secure user login and auth tokens?",
        "relevant_task_ids": ["M1", "M6", "M8"],
        "primary_relevant_id": "M1",
    },
    {
        "query": "Speed up SQL query latency and database performance",
        "relevant_task_ids": ["M2"],
        "primary_relevant_id": "M2",
    },
    {
        "query": "Prepare leadership roadmap slides for stakeholder meeting",
        "relevant_task_ids": ["M3", "M9"],
        "primary_relevant_id": "M3",
    },
    {
        "query": "Construct Hamiltonian spin matrix for quantum optimization",
        "relevant_task_ids": ["M4", "M7", "M10"],
        "primary_relevant_id": "M4",
    },
    {
        "query": "Responsive mobile layout improvements for web interface",
        "relevant_task_ids": ["M5"],
        "primary_relevant_id": "M5",
    },
]


@dataclass
class VectorRetrievalMetrics:
    """Retrieval evaluation metrics for semantic memory."""

    embedding_mode: str
    dimension: int
    corpus_size: int
    query_count: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float  # Mean Reciprocal Rank
    mean_latency_ms: float
    is_fallback: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "embedding_mode": self.embedding_mode,
            "dimension": self.dimension,
            "corpus_size": self.corpus_size,
            "query_count": self.query_count,
            "recall_at_1": round(self.recall_at_1, 4),
            "recall_at_3": round(self.recall_at_3, 4),
            "recall_at_5": round(self.recall_at_5, 4),
            "mrr": round(self.mrr, 4),
            "mean_latency_ms": round(self.mean_latency_ms, 2),
            "is_fallback": self.is_fallback,
            "notes": self.notes,
        }


class VectorMemoryBenchmarkEvaluator:
    """Evaluates semantic task retrieval quality, measuring Recall@K, MRR, and latency."""

    @staticmethod
    def evaluate_retrieval(
        storage_dir: Optional[Path] = None,
        force_fallback: bool = False,
    ) -> VectorRetrievalMetrics:
        """Populate isolated vector memory and evaluate retrieval metrics against ground truth queries."""
        import tempfile
        import shutil

        temp_dir = Path(tempfile.mkdtemp(prefix="heliox_vec_bench_"))
        try:
            # Instantiate VectorMemorySystem
            model_name = None if force_fallback else "all-MiniLM-L6-v2"
            vmem = VectorMemorySystem(storage_directory=str(temp_dir), model_name=model_name)

            # Check actual mode
            mode = vmem._embedding_mode()
            is_fallback = "fallback" in mode or vmem.model is None

            # Index benchmark corpus
            for item in BENCHMARK_TASK_CORPUS:
                vmem.store_memory(
                    task_description=item["task_description"],
                    metadata={"task_id": item["task_id"], "category": item["category"]},
                )

            # Run queries and record metrics
            recalls_at_1 = []
            recalls_at_3 = []
            recalls_at_5 = []
            reciprocal_ranks = []
            latencies_ms = []

            for q_item in BENCHMARK_QUERIES:
                query = q_item["query"]
                relevant_ids = set(q_item["relevant_task_ids"])
                primary_id = q_item["primary_relevant_id"]

                t0 = time.perf_counter()
                results = vmem.search_similar_tasks(query, limit=5)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                latencies_ms.append(elapsed_ms)

                retrieved_ids = [
                    res.get("metadata", {}).get("task_id")
                    for res in results
                ]

                # Recall@1: is at least one relevant task in top 1?
                recalls_at_1.append(1.0 if retrieved_ids[:1] and retrieved_ids[0] in relevant_ids else 0.0)
                # Recall@3: is at least one relevant task in top 3?
                recalls_at_3.append(1.0 if any(r in relevant_ids for r in retrieved_ids[:3]) else 0.0)
                # Recall@5: is at least one relevant task in top 5?
                recalls_at_5.append(1.0 if any(r in relevant_ids for r in retrieved_ids[:5]) else 0.0)

                # MRR: rank of first relevant result
                rr = 0.0
                for rank, r_id in enumerate(retrieved_ids, start=1):
                    if r_id in relevant_ids:
                        rr = 1.0 / rank
                        break
                reciprocal_ranks.append(rr)

            notes = (
                "Deterministic character hash projection fallback active. Fast and local-only; "
                "relies on character frequency overlap rather than deep semantic embeddings."
                if is_fallback
                else "Pretrained SentenceTransformer (all-MiniLM-L6-v2) active. High semantic comprehension across paraphrased intent."
            )

            dimension = int(vmem.embedding_matrix.shape[1]) if vmem.embedding_matrix.size > 0 else 384

            return VectorRetrievalMetrics(
                embedding_mode=mode,
                dimension=dimension,
                corpus_size=len(BENCHMARK_TASK_CORPUS),
                query_count=len(BENCHMARK_QUERIES),
                recall_at_1=float(np.mean(recalls_at_1)),
                recall_at_3=float(np.mean(recalls_at_3)),
                recall_at_5=float(np.mean(recalls_at_5)),
                mrr=float(np.mean(reciprocal_ranks)),
                mean_latency_ms=float(np.mean(latencies_ms)),
                is_fallback=is_fallback,
                notes=notes,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
