"""Build the M2 training datasets under data/m2/ and zip them for Kaggle/Colab.

    data/m2/detector_i2n/        YOLO detect, Image2Net only
    data/m2/detector_i2n_cghd/   YOLO detect, Image2Net + CGHD (train only)
    data/m2/orientation/         ImageFolder per orientation/mirroring task
    data/m2/crossing/            YOLO-OBB hops / dot junctions / T-junctions
    data/m2_kaggle.zip           GPU datasets (both detectors, crossing) plus a
                                 snapshot of src/ and its commit, for upload

Run after `make data` and `make data-train`. `--zip-only` re-packages
existing datasets (e.g. after committing code changes).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vca.classify.datasets import (  # noqa: E402
    build_crossing_dataset,
    build_orientation_datasets,
)
from vca.detect.dataset import build_detector_dataset  # noqa: E402

DATA = ROOT / "data"
I2N = DATA / "image2net"
OUT = DATA / "m2"


KAGGLE_DATASETS = ("detector_i2n", "detector_i2n_cghd", "crossing")


def code_version() -> str:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True, cwd=ROOT
        ).stdout.strip()

    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain", "--", "src", "pyproject.toml"))
    return commit + ("-dirty" if dirty else "")


def build_kaggle_zip(archive: Path) -> str:
    version = code_version()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as zf:
        for name in KAGGLE_DATASETS:
            for path in sorted((OUT / name).rglob("*")):
                if path.is_file():
                    zf.write(path, Path("datasets") / path.relative_to(OUT))
        for path in sorted((ROOT / "src" / "vca").rglob("*.py")):
            zf.write(path, Path("code") / path.relative_to(ROOT))
        zf.write(ROOT / "pyproject.toml", "code/pyproject.toml")
        zf.writestr("code/CODE_COMMIT", version + "\n")
    return version


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--no-zip", action="store_true")
    parser.add_argument("--zip-only", action="store_true")
    args = parser.parse_args()
    if args.zip_only:
        return package()
    common = {"val_fraction": args.val_fraction, "seed": args.seed}
    validation = I2N / "images"

    summary = {}
    print("detector (Image2Net only)", flush=True)
    summary["detector_i2n"] = build_detector_dataset(
        I2N / "train" / "device_identification",
        validation,
        OUT / "detector_i2n",
        **common,
    )
    print("detector (Image2Net + CGHD)", flush=True)
    summary["detector_i2n_cghd"] = build_detector_dataset(
        I2N / "train" / "device_identification",
        validation,
        OUT / "detector_i2n_cghd",
        cghd_dir=DATA / "cghd",
        **common,
    )
    print("orientation", flush=True)
    summary["orientation"] = build_orientation_datasets(
        I2N / "train" / "device_orientation", OUT / "orientation", **common
    )
    print("crossing", flush=True)
    summary["crossing"] = build_crossing_dataset(
        I2N / "train" / "jumper_identification", validation, OUT / "crossing", **common
    )

    for name, manifest in summary.items():
        brief = {k: v for k, v in manifest.items() if k in ("images", "instances")}
        if "excluded_validation_overlaps" in manifest:
            brief["excluded"] = len(manifest["excluded_validation_overlaps"])
        if name == "orientation":
            brief = {t: v["counts"] for t, v in manifest["tasks"].items()}
        print(name, json.dumps(brief))

    return 0 if args.no_zip else package()


def package() -> int:
    archive = DATA / "m2_kaggle.zip"
    print(f"zipping -> {archive.relative_to(ROOT)}", flush=True)
    version = build_kaggle_zip(archive)
    print(f"  {archive.stat().st_size / 1e6:,.0f} MB, code {version}")
    if version.endswith("-dirty"):
        print("  note: src/ has uncommitted changes; commit and rerun --zip-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
