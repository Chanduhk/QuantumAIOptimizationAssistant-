import urllib.request
import json

def query_openml():
    url = "https://api.openml.org/api/v1/json/data/list/tag/productivity/limit/5"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        print("Productivity tag datasets:", len(data.get("data", {}).get("dataset", [])))
        for d in data.get("data", {}).get("dataset", []):
            print(" -", d.get("did"), d.get("name"), d.get("format"), d.get("NumberOfInstances"))
    except Exception as e:
        print("Error tag productivity:", e)

    url2 = "https://api.openml.org/api/v1/json/data/list/data_name/garments-worker-productivity/limit/5"
    req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req2, timeout=10) as resp2:
            data2 = json.loads(resp2.read().decode())
        for d in data2.get("data", {}).get("dataset", []):
            print("garments did:", d.get("did"), d.get("name"), d.get("NumberOfInstances"))
    except Exception as e:
        print("Error search garments:", e)

if __name__ == "__main__":
    query_openml()
