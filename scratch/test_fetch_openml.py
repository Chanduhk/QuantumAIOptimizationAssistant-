import urllib.request
import json
import io
import pandas as pd
import hashlib

def test_openml_desharnais():
    # OpenML API for dataset 1117
    url = "https://api.openml.org/api/v1/json/data/1117"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        meta = json.loads(resp.read().decode())
    data_desc = meta["data_set_description"]
    file_id = data_desc["file_id"]
    name = data_desc["name"]
    print(f"OpenML 1117 name: {name}, file_id: {file_id}, format: {data_desc.get('format')}")

    # Download ARFF file
    arff_url = f"https://api.openml.org/data/v1/download/{file_id}/{name}.arff"
    req2 = urllib.request.Request(arff_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req2, timeout=15) as resp2:
        arff_bytes = resp2.read()
    print(f"Downloaded {len(arff_bytes)} bytes. SHA256: {hashlib.sha256(arff_bytes).hexdigest()[:16]}")
    lines = arff_bytes.decode('utf-8', errors='ignore').splitlines()
    data_idx = -1
    for i, line in enumerate(lines):
        if line.strip().lower() == '@data':
            data_idx = i + 1
            break
    print(f"@data found at line {data_idx}. Total lines: {len(lines)}")
    if data_idx > 0:
        attr_lines = [l for l in lines[:data_idx] if l.strip().lower().startswith('@attribute')]
        print(f"Attributes count: {len(attr_lines)}")
        for a in attr_lines[:5]:
            print("  ", a)
        data_rows = [l.split(',') for l in lines[data_idx:] if l.strip() and not l.strip().startswith('%')]
        print(f"Data rows count: {len(data_rows)}")
        print("Sample row:", data_rows[0])

if __name__ == "__main__":
    try:
        test_openml_desharnais()
    except Exception as e:
        print("Error:", type(e), e)
