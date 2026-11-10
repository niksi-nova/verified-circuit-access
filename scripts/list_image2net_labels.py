
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = (
    "https://api.github.com/repos/LAD021/ci2n_datasets/"
    "git/trees/main?recursive=1"
)
RAW_BASE = (
    "https://raw.githubusercontent.com/LAD021/ci2n_datasets/main/"
)

def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "VCA-taxonomy-label-audit"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

tree = fetch_json(API_URL)["tree"]

json_paths = [
    item["path"]
    for item in tree
    if item["type"] == "blob"
    and item["path"].startswith("device_identification/")
    and item["path"].endswith(".json")
]

print(f"Found {len(json_paths)} annotation JSON files.")

def extract_labels(path):
    data = fetch_json(RAW_BASE + path)
    return {
        shape["label"]
        for shape in data.get("shapes", [])
        if isinstance(shape.get("label"), str)
    }

labels = set()
errors = []

with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {
        executor.submit(extract_labels, path): path
        for path in json_paths
    }

    for future in as_completed(futures):
        path = futures[future]
        try:
            labels.update(future.result())
        except Exception as exc:
            errors.append((path, str(exc)))

print(f"\nUnique labels: {len(labels)}")
for label in sorted(labels):
    print(label)

if errors:
    print(f"\nFailed files: {len(errors)}")
    for path, error in errors:
        print(path, error)

