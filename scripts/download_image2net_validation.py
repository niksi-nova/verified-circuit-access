"""Download Image2Net's 104 verified validation pairs from the official repo.

Source: https://github.com/LAD021/ci2n_datasets (Apache-2.0), pinned to one
commit so every run sees identical files. Images and golden netlists land in
the git-ignored ``data/image2net/`` directory together with a SHA-256
manifest. Nothing is redistributed.
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

COMMIT = "2ffd41b2255726eb1be215fa7ba1d9808c80c808"
TREE_URL = (
    "https://api.github.com/repos/LAD021/ci2n_datasets/git/trees/"
    f"{COMMIT}?recursive=1"
)
RAW_BASE = f"https://raw.githubusercontent.com/LAD021/ci2n_datasets/{COMMIT}"
USER_AGENT = "verified-circuit-access-data-script"

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "image2net"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def main() -> int:
    tree = json.loads(fetch(TREE_URL))
    if tree.get("truncated"):
        print("GitHub tree listing was truncated; aborting.", file=sys.stderr)
        return 1

    paths = {entry["path"] for entry in tree["tree"] if entry["type"] == "blob"}
    golden = {
        Path(p).stem: p
        for p in paths
        if p.startswith("validation/golden/") and p.endswith(".json")
    }
    images = {
        Path(p).stem: p
        for p in paths
        if p.startswith("validation/images/")
        and Path(p).suffix.lower() in {".png", ".jpg", ".jpeg"}
    }

    if set(golden) != set(images):
        only_golden = sorted(set(golden) - set(images))
        only_images = sorted(set(images) - set(golden))
        print(
            f"Image/golden IDs differ. Golden only: {only_golden}; "
            f"images only: {only_images}",
            file=sys.stderr,
        )
        return 1

    pair_ids = sorted(golden)
    print(f"Found {len(pair_ids)} validation pairs at commit {COMMIT}")

    manifest = []
    for index, pair_id in enumerate(pair_ids, start=1):
        image_rel = images[pair_id]
        files = {
            "image": (image_rel, OUTPUT / "images" / Path(image_rel).name),
            "golden": (golden[pair_id], OUTPUT / "golden" / f"{pair_id}.json"),
        }
        for file_type, (relative_path, destination) in files.items():
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(fetch(f"{RAW_BASE}/{relative_path}"))
            manifest.append(
                {
                    "id": pair_id,
                    "type": file_type,
                    "path": destination.relative_to(ROOT).as_posix(),
                    "sha256": sha256_file(destination),
                    "source_commit": COMMIT,
                }
            )
        print(f"[{index}/{len(pair_ids)}] {pair_id}")

    manifest_path = OUTPUT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
