import urllib.request
import json

def check_hf():
    # Check dataset files via Hugging Face API
    url = "https://huggingface.co/api/datasets/giseldo/deep-se"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        print("HF deep-se tags:", data.get("tags"))
        print("HF deep-se siblings:", [s.get("rfilename") for s in data.get("siblings", [])[:10]])
    except Exception as e:
        print("Error checking HF:", e)

if __name__ == "__main__":
    check_hf()
