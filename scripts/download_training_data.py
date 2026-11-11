"""Download the M2 training data into the git-ignored ``data/`` directory.

- Image2Net (github.com/LAD021/ci2n_datasets, Apache-2.0), pinned commit:
  ``device_identification/`` (Labelme boxes), ``device_orientation/``
  (class-per-folder crops), ``jumper_identification/`` (YOLO-OBB crossings)
  -> ``data/image2net/train/``. The validation pairs are handled by
  ``download_image2net_validation.py`` and are not touched here.
- CGHD (Zenodo record 15333233, version 15, CC BY 4.0), the single
  ``cghd-zenodo-15.zip`` (4.9 GB), MD5-checked -> ``data/cghd/``.

Archives are kept under ``data/_downloads/`` so a rerun skips the download.
Usage: python scripts/download_training_data.py [image2net] [cghd]
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ARCHIVES = DATA / "_downloads"
USER_AGENT = "verified-circuit-access-data-script"

IMAGE2NET_COMMIT = "2ffd41b2255726eb1be215fa7ba1d9808c80c808"
IMAGE2NET_ZIP = (
    "https://codeload.github.com/LAD021/ci2n_datasets/zip/" + IMAGE2NET_COMMIT
)
IMAGE2NET_FOLDERS = (
    "device_identification",
    "device_orientation",
    "jumper_identification",
)

CGHD_RECORD = "15333233"
CGHD_FILE = "cghd-zenodo-15.zip"
CGHD_URL = f"https://zenodo.org/records/{CGHD_RECORD}/files/{CGHD_FILE}?download=1"
CGHD_MD5 = "26f6e8d48fa8174e23ff5c072ca07c7f"
CGHD_SIZE = 4_874_782_260


def download(url: str, destination: Path) -> Path:
    if destination.exists():
        print(f"  using existing {destination.relative_to(ROOT)}")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open(
        "wb"
    ) as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        next_report = 0.0
        while chunk := response.read(4 * 1024 * 1024):
            out.write(chunk)
            done += len(chunk)
            if total and done / total >= next_report:
                print(f"  {done / 1e6:,.0f} / {total / 1e6:,.0f} MB", flush=True)
                next_report += 0.1
    partial.replace(destination)
    return destination


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    target: Path,
    name: str | None = None,
) -> None:
    """Extract one member (optionally renamed), refusing paths outside target."""
    name = member.filename if name is None else name
    destination = (target / name).resolve()
    if not destination.is_relative_to(target.resolve()):
        raise RuntimeError(f"Unsafe path in archive: {member.filename}")
    if member.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(member) as src, destination.open("wb") as dst:
        shutil.copyfileobj(src, dst)


def write_manifest(target: Path, info: dict) -> None:
    files = [p for p in target.rglob("*") if p.is_file() and p.name != "manifest.json"]
    info |= {
        "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "file_count": len(files),
        "total_bytes": sum(p.stat().st_size for p in files),
    }
    (target / "manifest.json").write_text(json.dumps(info, indent=2), encoding="utf-8")


def image2net() -> None:
    print("Image2Net training sets")
    archive_path = download(IMAGE2NET_ZIP, ARCHIVES / f"ci2n_{IMAGE2NET_COMMIT}.zip")
    target = DATA / "image2net" / "train"
    if target.exists():
        shutil.rmtree(target)
    counts: dict[str, int] = {}
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            # Archive entries look like "ci2n_datasets-<commit>/<folder>/...".
            parts = member.filename.split("/", 1)
            if len(parts) < 2 or parts[1].split("/", 1)[0] not in IMAGE2NET_FOLDERS:
                continue
            safe_extract(archive, member, target, name=parts[1])
            if not member.is_dir():
                folder = parts[1].split("/", 1)[0]
                counts[folder] = counts.get(folder, 0) + 1
    print(f"  extracted {counts}")
    write_manifest(
        target,
        {
            "source": "https://github.com/LAD021/ci2n_datasets",
            "source_commit": IMAGE2NET_COMMIT,
            "license": "Apache-2.0",
            "folders": counts,
        },
    )


def cghd() -> None:
    print("CGHD")
    archive_path = download(CGHD_URL, ARCHIVES / CGHD_FILE)
    size = archive_path.stat().st_size
    if size != CGHD_SIZE:
        raise RuntimeError(f"CGHD size {size} != expected {CGHD_SIZE}")
    print("  checking MD5 ...", flush=True)
    checksum = md5_file(archive_path)
    if checksum != CGHD_MD5:
        raise RuntimeError(f"CGHD MD5 {checksum} != expected {CGHD_MD5}")
    target = DATA / "cghd"
    if target.exists():
        shutil.rmtree(target)
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        for index, member in enumerate(members, start=1):
            safe_extract(archive, member, target)
            if index % 20000 == 0:
                print(f"  extracted {index:,} / {len(members):,}", flush=True)
    write_manifest(
        target,
        {
            "source": f"https://zenodo.org/records/{CGHD_RECORD}",
            "version": "15",
            "license": "CC-BY-4.0",
            "archive": CGHD_FILE,
            "archive_md5": CGHD_MD5,
        },
    )
    print("  done")


def main(argv: list[str]) -> int:
    wanted = set(argv) or {"image2net", "cghd"}
    unknown = wanted - {"image2net", "cghd"}
    if unknown:
        print(f"Unknown dataset(s): {sorted(unknown)}", file=sys.stderr)
        return 2
    if "image2net" in wanted:
        image2net()
    if "cghd" in wanted:
        cghd()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
