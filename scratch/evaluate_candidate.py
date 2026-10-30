import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

# Use threading backend for joblib to avoid Windows multiprocessing spawn hang
with joblib.parallel_backend("threading"):
    artifact_path = Path("data/model_artifacts/productivity_benchmark_candidate_uci-garment-productivity.joblib")
    data = joblib.load(artifact_path)
    print("Keys in artifact:", list(data.keys()))
    metadata = data.get("metadata", {})
    print("Metadata:")
    print(json.dumps(metadata, indent=2))
