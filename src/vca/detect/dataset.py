"""Build the YOLO component-detection dataset from Image2Net (+ CGHD).

Layout written to ``out_dir``::

    images/{train,val}/<name>     labels/{train,val}/<name>.txt
    data.yaml                     manifest.json

- Image2Net detection images that duplicate an Image2Net *validation*
  circuit (exact or near copy) are dropped, so the netlist evaluation
  set never leaks into training.
- The rest is split train/val by near-duplicate group with a fixed seed.
  The val split is Image2Net only: it is the number we report.
- CGHD (optional) goes to train only. Its boxes are mapped with
  ``classes.from_cghd``; unmapped symbols are painted out with the
  surrounding paper colour, and large photos are downscaled.
"""

from __future__ import annotations

import json
import random
import shutil
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from vca.data.cghd import load_pascal_voc
from vca.data.dedup import find_overlaps, group_near_duplicates
from vca.detect.classes import (
    CLASS_INDEX,
    DETECTOR_CLASSES,
    MASK,
    from_cghd,
    from_image2net,
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def yolo_line(
    cls: int, box: tuple[float, float, float, float], w: int, h: int
) -> str | None:
    """YOLO row for an (x1, y1, x2, y2) pixel box, clipped; None if empty."""
    x1, y1, x2, y2 = box
    x1, x2 = sorted((max(0.0, min(w, x1)), max(0.0, min(w, x2))))
    y1, y2 = sorted((max(0.0, min(h, y1)), max(0.0, min(h, y2))))
    if x2 - x1 < 1 or y2 - y1 < 1:
        return None
    return (
        f"{cls} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} "
        f"{(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}"
    )


def split_groups(groups: list, val_fraction: float, seed: int) -> list[str]:
    """'train'/'val' per item so that items sharing a group share a split."""
    unique = sorted(set(groups), key=str)
    rng = random.Random(seed)
    rng.shuffle(unique)
    n_val = round(len(unique) * val_fraction)
    val = set(unique[:n_val])
    return ["val" if g in val else "train" for g in groups]


def _image2net_rows(json_path: Path, image_path: Path) -> tuple[list[str], Counter]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    with Image.open(image_path) as image:
        w, h = image.size
    rows, counts = [], Counter()
    for shape in data["shapes"]:
        if shape.get("shape_type") != "rectangle":
            continue
        name = from_image2net(shape["label"])
        (ax, ay), (bx, by) = shape["points"]
        row = yolo_line(CLASS_INDEX[name], (ax, ay, bx, by), w, h)
        if row:
            rows.append(row)
            counts[name] += 1
    return rows, counts


def _border_colour(pixels: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> tuple:
    h, w = pixels.shape[:2]
    ring = []
    for ys, xs in (
        (slice(max(0, y1 - 3), y1), slice(x1, x2)),
        (slice(y2, min(h, y2 + 3)), slice(x1, x2)),
        (slice(y1, y2), slice(max(0, x1 - 3), x1)),
        (slice(y1, y2), slice(x2, min(w, x2 + 3))),
    ):
        part = pixels[ys, xs].reshape(-1, 3)
        if part.size:
            ring.append(part)
    if not ring:
        return (255, 255, 255)
    return tuple(int(v) for v in np.median(np.concatenate(ring), axis=0))


def _cghd_image(xml_path: Path) -> Path | None:
    images = xml_path.parent.parent / "images"
    for candidate in images.glob(xml_path.stem + ".*"):
        if candidate.suffix.lower() in IMAGE_SUFFIXES:
            return candidate
    return None


def _write_cghd(
    xml_path: Path, out_image: Path, out_label: Path, max_side: int
) -> tuple[Counter, int, str | None]:
    """Write one CGHD sample; returns (class counts, masked boxes, skip reason)."""
    record = load_pascal_voc(xml_path)
    image_path = _cghd_image(xml_path)
    if image_path is None:
        return Counter(), 0, "image file missing"

    # Pick the pixel orientation the boxes were drawn on: the stored one or
    # the EXIF-rotated one. Prefer an exact match with the annotated size;
    # some files carry a placeholder size (1000x1000), so otherwise take the
    # orientation that contains every box.
    extent = (
        max((a.bbox.x + a.bbox.width for a in record.annotations), default=0),
        max((a.bbox.y + a.bbox.height for a in record.annotations), default=0),
    )
    expected = (record.image.width, record.image.height)
    with Image.open(image_path) as raw:
        options = [raw, ImageOps.exif_transpose(raw)]
        chosen = next((o for o in options if o.size == expected), None)
        if chosen is None:
            chosen = next(
                (
                    o
                    for o in options
                    if extent[0] <= o.size[0] + 1 and extent[1] <= o.size[1] + 1
                ),
                None,
            )
        if chosen is None:
            return Counter(), 0, f"boxes {extent} exceed image {raw.size}"
        image = chosen.convert("RGB")

    w, h = image.size
    pixels = np.array(image)
    rows, counts, masked = [], Counter(), 0
    for ann in record.annotations:
        b = ann.bbox
        x1, y1 = int(b.x), int(b.y)
        x2, y2 = int(np.ceil(b.x + b.width)), int(np.ceil(b.y + b.height))
        target = from_cghd(ann.source_label)
        if target == MASK:
            pixels[max(0, y1) : y2, max(0, x1) : x2] = _border_colour(
                pixels, max(0, x1), max(0, y1), min(w, x2), min(h, y2)
            )
            masked += 1
        elif target is not None:
            row = yolo_line(
                CLASS_INDEX[target], (b.x, b.y, b.x + b.width, b.y + b.height), w, h
            )
            if row:
                rows.append(row)
                counts[target] += 1

    image = Image.fromarray(pixels)
    scale = max_side / max(w, h)
    if scale < 1:
        image = image.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    image.save(out_image, quality=92)
    out_label.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    return counts, masked, None


def build_detector_dataset(
    image2net_dir: Path,
    validation_images_dir: Path,
    out_dir: Path,
    *,
    cghd_dir: Path | None = None,
    val_fraction: float = 0.15,
    seed: int = 42,
    cghd_max_side: int = 1280,
    dedup_distance: int = 10,
) -> dict:
    image2net_dir, out_dir = Path(image2net_dir), Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for split in ("train", "val"):
        (out_dir / "images" / split).mkdir(parents=True)
        (out_dir / "labels" / split).mkdir(parents=True)

    images = sorted(
        p
        for p in image2net_dir.iterdir()
        if p.suffix.lower() in IMAGE_SUFFIXES and p.with_suffix(".json").exists()
    )
    overlaps = find_overlaps(
        images, sorted(Path(validation_images_dir).glob("*.png")), dedup_distance
    )
    kept = [p for p in images if p not in overlaps]
    splits = split_groups(
        group_near_duplicates(kept, dedup_distance), val_fraction, seed
    )

    counts = {"train": Counter(), "val": Counter()}
    n_images = Counter()
    for image_path, split in zip(kept, splits, strict=True):
        rows, c = _image2net_rows(image_path.with_suffix(".json"), image_path)
        name = f"i2n_{image_path.stem}"
        shutil.copy2(
            image_path, out_dir / "images" / split / f"{name}{image_path.suffix}"
        )
        (out_dir / "labels" / split / f"{name}.txt").write_text(
            "\n".join(rows) + ("\n" if rows else ""), encoding="utf-8"
        )
        counts[split].update(c)
        n_images[f"image2net_{split}"] += 1

    cghd_info: dict = {"used": False}
    if cghd_dir is not None:
        masked_total, skipped = 0, []
        for xml_path in sorted(Path(cghd_dir).glob("drafter_*/annotations/*.xml")):
            name = f"cghd_{xml_path.parent.parent.name}_{xml_path.stem}"
            c, masked, reason = _write_cghd(
                xml_path,
                out_dir / "images" / "train" / f"{name}.jpg",
                out_dir / "labels" / "train" / f"{name}.txt",
                cghd_max_side,
            )
            if reason:
                skipped.append(
                    f"{xml_path.parent.parent.name}/{xml_path.name}: {reason}"
                )
                continue
            counts["train"].update(c)
            masked_total += masked
            n_images["cghd_train"] += 1
        cghd_info = {
            "used": True,
            "masked_boxes": masked_total,
            "skipped": skipped,
            "max_side": cghd_max_side,
        }

    (out_dir / "data.yaml").write_text(
        # No `path:` key: Ultralytics then resolves paths from this file's folder.
        "train: images/train\nval: images/val\nnames:\n"
        + "".join(f"  {i}: {n}\n" for i, n in enumerate(DETECTOR_CLASSES)),
        encoding="utf-8",
    )
    manifest = {
        "seed": seed,
        "val_fraction": val_fraction,
        "dedup_distance": dedup_distance,
        "images": dict(n_images),
        "boxes": {s: dict(sorted(c.items())) for s, c in counts.items()},
        "excluded_validation_overlaps": [
            {"image": p.name, "validation_image": ref.name, "distance": d}
            for p, (ref, d) in sorted(overlaps.items())
        ],
        "cghd": cghd_info,
        "classes": list(DETECTOR_CLASSES),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest
