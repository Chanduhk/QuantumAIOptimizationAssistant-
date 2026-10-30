import sys
import time

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

log("Starting vector memory check...")

log("Step 1: Testing deterministic fallback...")
from backend.app.memory.benchmark_evaluator import VectorMemoryBenchmarkEvaluator
fb_metrics = VectorMemoryBenchmarkEvaluator.evaluate_retrieval(force_fallback=True)
log(f"Fallback metrics complete: mode={fb_metrics.embedding_mode}, dim={fb_metrics.dimension}, Recall@1={fb_metrics.recall_at_1}, MRR={fb_metrics.mrr}, latency={fb_metrics.mean_latency_ms:.2f}ms")

log("Step 2: Checking SentenceTransformer import...")
t0 = time.time()
try:
    from sentence_transformers import SentenceTransformer
    log(f"SentenceTransformer imported in {time.time()-t0:.2f}s")
except Exception as e:
    log(f"Failed to import SentenceTransformer: {e}")

log("Step 3: Checking if all-MiniLM-L6-v2 is cached locally...")
try:
    st = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
    log(f"SentenceTransformer loaded successfully from local files! Model: {type(st)}")
except Exception as e:
    log(f"SentenceTransformer not cached locally with local_files_only=True: {type(e).__name__}: {e}")

log("Finished vector memory check.")
