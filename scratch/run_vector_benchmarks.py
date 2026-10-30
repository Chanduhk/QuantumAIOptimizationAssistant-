import json
from backend.app.memory.benchmark_evaluator import VectorMemoryBenchmarkEvaluator

def run():
    print("Evaluating Vector Memory System...")
    # 1. Standard mode (attempts SentenceTransformer if cached, else fallback)
    metrics_standard = VectorMemoryBenchmarkEvaluator.evaluate_retrieval(force_fallback=False)
    print("\n--- Standard System Mode ---")
    print(json.dumps(metrics_standard.to_dict(), indent=2))

    # 2. Forced Deterministic Fallback Mode
    metrics_fallback = VectorMemoryBenchmarkEvaluator.evaluate_retrieval(force_fallback=True)
    print("\n--- Forced Deterministic Fallback Mode ---")
    print(json.dumps(metrics_fallback.to_dict(), indent=2))

    results = {
        "standard_mode": metrics_standard.to_dict(),
        "fallback_mode": metrics_fallback.to_dict(),
    }
    with open("scratch/vector_memory_benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved vector memory benchmark results to scratch/vector_memory_benchmark_results.json")

if __name__ == "__main__":
    run()
