import urllib.request
import json
import io
import pandas as pd
from backend.app.core.resilient_http import ResilientHttpClient

def check_deep_se():
    print("Checking HuggingFace deep-se dataset...")
    url = "https://huggingface.co/api/datasets/giseldo/deep-se"
    client = ResilientHttpClient(default_timeout=15.0, max_retries=2)
    try:
        data_bytes = client.execute_request(url)
        meta = json.loads(data_bytes.decode("utf-8"))
        print("Dataset ID:", meta.get("id"))
        print("Description / tags:", meta.get("tags"))
        print("Siblings:", [s.get("rfilename") for s in meta.get("siblings", [])[:10]])
    except Exception as e:
        print("Failed to fetch HF metadata:", e)

    # Sample the CSV
    csv_url = "https://huggingface.co/datasets/giseldo/deep-se/resolve/main/deep-se.csv"
    req = urllib.request.Request(csv_url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-4096"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            chunk = resp.read()
        print("Sample chunk received (bytes):", len(chunk))
        sample_text = chunk.decode("utf-8", errors="ignore")
        lines = sample_text.splitlines()
        print("Header:", lines[0] if lines else "None")
        if len(lines) > 1:
            print("Row 1:", lines[1])
    except Exception as e:
        print("Failed to sample deep-se CSV:", e)

if __name__ == "__main__":
    check_deep_se()
