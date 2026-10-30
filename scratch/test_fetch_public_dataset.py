import urllib.request
import zipfile
import io
import json
import pandas as pd
import hashlib

def test_uci_garment():
    url = "https://archive.ics.uci.edu/static/public/597/productivity+prediction+of+garment+employees.zip"
    print(f"Fetching UCI dataset from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    print(f"Downloaded {len(data)} bytes. SHA256: {hashlib.sha256(data).hexdigest()[:16]}")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        print("Zip contents:", zf.namelist())
        csv_name = [n for n in zf.namelist() if n.endswith('.csv')][0]
        with zf.open(csv_name) as f:
            df = pd.read_csv(f)
    print("DataFrame shape:", df.shape)
    print("Columns:", list(df.columns))
    print("Sample:\n", df.head(2))
    print("Target actual_productivity describe:\n", df['actual_productivity'].describe())

if __name__ == "__main__":
    try:
        test_uci_garment()
    except Exception as e:
        print("Error:", type(e), e)
