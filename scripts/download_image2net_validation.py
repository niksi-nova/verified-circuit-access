
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

COMMIT = "2ffd41b2255726eb1be215fa7ba1d9808c80c808"
REPOSITORY = "https://raw.githubusercontent.com/LAD021/ci2n_datasets"

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "image2net"

TREE_FILE = Path("/tmp/image2net_tree.json")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "verified-circuit-access"},
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        destination.write_bytes(response.read())


def main() -> None:
    if not TREE_FILE.exists():
        raise FileNotFoundError(
            f"Repository tree not found: {TREE_FILE}"
        )

    tree = json.loads(TREE_FILE.read_text(encoding="utf-8"))
    paths = {entry["path"] for entry in tree["tree"]}

    golden_ids = {
        Path(path).stem
        for path in paths
        if path.startswith("validation/golden/")
        and path.endswith(".json")
    }
    image_ids = {
        Path(path).stem
        for path in paths
        if path.startswith("validation/images/")
        and path.endswith(".png")
    }

    if golden_ids != image_ids:
        raise ValueError("Image and golden-netlist IDs do not match")

    pair_ids = sorted(golden_ids)

    print(f"Found {len(pair_ids)} validation pairs")
    print(f"Pinned commit: {COMMIT}")

    manifest = []

    for index, pair_id in enumerate(pair_ids, start=1):
        files = {
            "image": (
                f"validation/images/{pair_id}.png",
                OUTPUT / "images" / f"{pair_id}.png",
            ),
            "golden": (
                f"validation/golden/{pair_id}.json",
                OUTPUT / "golden" / f"{pair_id}.json",
            ),
        }

        for file_type, (relative_path, destination) in files.items():
            url = f"{REPOSITORY}/{COMMIT}/{relative_path}"

            if not destination.exists():
                download(url, destination)

            manifest.append({
                "id": pair_id,
                "type": file_type,
                "path": str(destination.relative_to(ROOT)),
                "sha256": sha256_file(destination),
                "source_commit": COMMIT,
            })

        print(f"[{index}/{len(pair_ids)}] Verified pair {pair_id}")

    manifest_path = OUTPUT / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"\nDownloaded/verified {len(pair_ids)} pairs")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
