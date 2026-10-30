import urllib.request
import json

def search_openml(query_term):
    url = f"https://api.openml.org/api/v1/json/data/list/data_name/{query_term}/limit/10"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        datasets = data.get("data", {}).get("dataset", [])
        print(f"=== Query '{query_term}': found {len(datasets)} ===")
        for d in datasets[:5]:
            print(f"ID: {d.get('did')}, Name: {d.get('name')}, Instances: {d.get('NumberOfInstances')}, Features: {d.get('NumberOfFeatures')}, Format: {d.get('format')}")
    except Exception as e:
        print(f"Query '{query_term}' failed: {e}")

if __name__ == "__main__":
    for term in ["duration", "execution", "productivity", "workload", "time", "scheduling"]:
        search_openml(term)
