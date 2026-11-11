"""Datasets for the orientation/mirroring classifiers and the crossing model.

Orientation (Image2Net ``device_orientation/``): each ``train_<task>``
folder holds one class per sub-folder (``d/l/r/u`` rotations, or ``0/1``
for not-mirrored/mirrored). The four rotations of a crop are copies of one
drawing (``d5``, ``u5``, ``l5``, ``r5``), so the split is made by that
shared id; otherwise every val image would have rotated twins in train.
Output: ``<out>/<task>/{train,val}/<class>/`` (ImageFolder layout).

Crossings (Image2Net ``jumper_identification/``): YOLO-OBB labels with
three classes, checked by eye on sample crops:
0 = hop (wires cross, not connected), 1 = dot junction (connected),
2 = T-junction (connected). Plain crossings without a dot are not labelled.
Images duplicating netlist-evaluation circuits are dropped and the rest
re-split by near-duplicate group.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from pathlib import Path

from vca.data.dedup import find_overlaps, group_near_duplicates
from vca.detect.dataset import IMAGE_SUFFIXES, split_groups

CROSSING_CLASSES = ("hop", "dot_junction", "t_junction")

_ORIENTATION_PREFIX = re.compile(r"^[dulr]+")


def orientation_group(stem: str) -> str:
    """Shared id of a crop across its rotated/mirrored copies."""
    return _ORIENTATION_PREFIX.sub("", stem)


def build_orientation_datasets(
    orientation_dir: Path, out_dir: Path, *, val_fraction: float = 0.15, seed: int = 42
) -> dict:
    orientation_dir, out_dir = Path(orientation_dir), Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    summary: dict = {"seed": seed, "val_fraction": val_fraction, "tasks": {}}
    for task_dir in sorted(p for p in orientation_dir.iterdir() if p.is_dir()):
        task = task_dir.name.removeprefix("train_")
        files = sorted(
            p for p in task_dir.glob("*/*") if p.suffix.lower() in IMAGE_SUFFIXES
        )
        groups = [orientation_group(p.stem) for p in files]
        splits = split_groups(groups, val_fraction, seed)
        counts = {"train": Counter(), "val": Counter()}
        for path, split in zip(files, splits, strict=True):
            label = path.parent.name
            target = out_dir / task / split / label / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            counts[split][label] += 1
        summary["tasks"][task] = {
            "classes": sorted({p.parent.name for p in files}),
            "groups": len(set(groups)),
            "counts": {s: dict(sorted(c.items())) for s, c in counts.items()},
        }
    (out_dir / "manifest.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def build_crossing_dataset(
    jumper_dir: Path,
    validation_images_dir: Path,
    out_dir: Path,
    *,
    val_fraction: float = 0.15,
    seed: int = 42,
    dedup_distance: int = 10,
) -> dict:
    jumper_dir, out_dir = Path(jumper_dir), Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)

    pairs: list[tuple[Path, Path]] = []
    for image in sorted((jumper_dir / "images").glob("*/*")):
        if image.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        label = jumper_dir / "labels" / image.parent.name / f"{image.stem}.txt"
        if label.exists():
            pairs.append((image, label))

    overlaps = find_overlaps(
        [i for i, _ in pairs],
        sorted(Path(validation_images_dir).glob("*.png")),
        dedup_distance,
    )
    kept = [(i, lab) for i, lab in pairs if i not in overlaps]
    groups = group_near_duplicates([i for i, _ in kept], dedup_distance)
    splits = split_groups(groups, val_fraction, seed)

    counts = {"train": Counter(), "val": Counter()}
    for (image, label), split in zip(kept, splits, strict=True):
        name = f"{image.parent.name}_{image.stem}"
        for kind, src, suffix in (
            ("images", image, image.suffix),
            ("labels", label, ".txt"),
        ):
            target = out_dir / kind / split / f"{name}{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        for line in label.read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[split][CROSSING_CLASSES[int(line.split()[0])]] += 1

    (out_dir / "data.yaml").write_text(
        # No `path:` key: Ultralytics then resolves paths from this file's folder.
        "train: images/train\nval: images/val\nnames:\n"
        + "".join(f"  {i}: {n}\n" for i, n in enumerate(CROSSING_CLASSES)),
        encoding="utf-8",
    )
    manifest = {
        "seed": seed,
        "val_fraction": val_fraction,
        "images": {s: splits.count(s) for s in ("train", "val")},
        "instances": {s: dict(sorted(c.items())) for s, c in counts.items()},
        "excluded_validation_overlaps": [
            {
                "image": f"{p.parent.name}/{p.name}",
                "validation_image": r.name,
                "distance": d,
            }
            for p, (r, d) in sorted(overlaps.items())
        ],
        "classes": list(CROSSING_CLASSES),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest
