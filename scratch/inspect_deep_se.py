import urllib.request
import pandas as pd
import io

def inspect_deep_se():
    url = "https://huggingface.co/datasets/giseldo/deep-se/resolve/main/deep-se.csv"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-10000"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        chunk = resp.read()
    print("Downloaded chunk bytes:", len(chunk))
    # parse first few lines
    lines = chunk.decode("utf-8", errors="ignore").splitlines()
    print("Header:", lines[0])
    for l in lines[1:5]:
        print("Row:", l[:120])

if __name__ == "__main__":
    inspect_deep_se()
