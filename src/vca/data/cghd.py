"""CGHD loaders.

PASCAL VOC box annotations are parsed into the shared COCO-style records.
CGHD labels are kept verbatim in ``source_label``; the canonical category
comes from the taxonomy, and labels it does not know yet map to
``unknown`` (id 0) and are reported so they can be added deliberately.

LTspice ``.asc`` netlist conversion is an M2 task.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from vca.schemas.annotation import AnnotationRecord, BoundingBox, ImageRecord
from vca.schemas.taxonomy import TAXONOMY

DATASET_ID = "CGHD"


class CGHDFormatError(ValueError):
    """Raised when an annotation file does not have the expected structure."""


@dataclass
class VOCAnnotation:
    image: ImageRecord
    annotations: list[AnnotationRecord]
    unmapped_labels: set[str] = field(default_factory=set)
    # Objects dropped because they cannot become a valid box, with the reason.
    skipped: list[str] = field(default_factory=list)


def _text(node: ET.Element, tag: str, path: Path) -> str:
    child = node.find(tag)
    if child is None or child.text is None or not child.text.strip():
        raise CGHDFormatError(f"{path}: missing <{tag}>")
    return child.text.strip()


def _number(node: ET.Element, tag: str, path: Path) -> float:
    value = _text(node, tag, path)
    try:
        return float(value)
    except ValueError as exc:
        raise CGHDFormatError(f"{path}: <{tag}> is not a number: {value!r}") from exc


def load_pascal_voc(
    path: Path,
    *,
    image_id: int = 1,
    first_annotation_id: int = 1,
) -> VOCAnnotation:
    """Parse one PASCAL VOC XML file into COCO-style records."""
    path = Path(path)
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise CGHDFormatError(f"{path}: invalid XML: {exc}") from exc

    size = root.find("size")
    if size is None:
        raise CGHDFormatError(f"{path}: missing <size>")
    image = ImageRecord(
        id=image_id,
        file_name=_text(root, "filename", path),
        width=int(_number(size, "width", path)),
        height=int(_number(size, "height", path)),
    )

    annotations: list[AnnotationRecord] = []
    unmapped: set[str] = set()
    skipped: list[str] = []
    for index, obj in enumerate(root.findall("object")):
        label = _text(obj, "name", path)
        box = obj.find("bndbox")
        if box is None:
            raise CGHDFormatError(f"{path}: object {label!r} has no <bndbox>")
        xmin, ymin = _number(box, "xmin", path), _number(box, "ymin", path)
        xmax, ymax = _number(box, "xmax", path), _number(box, "ymax", path)
        if xmax <= xmin or ymax <= ymin:
            skipped.append(f"object {index} ({label!r}): zero-area box")
            continue

        _, category_id = TAXONOMY.get_canonical(DATASET_ID, label)
        if category_id == 0:
            unmapped.add(label)

        # CGHD puts <rotation> inside <bndbox>; accept it on <object> too.
        rotation = box.find("rotation")
        if rotation is None:
            rotation = obj.find("rotation")
        orientation = None
        if rotation is not None and rotation.text and rotation.text.strip():
            orientation = float(rotation.text) % 360.0

        annotations.append(
            AnnotationRecord(
                id=first_annotation_id + len(annotations),
                image_id=image_id,
                category_id=category_id,
                bbox=BoundingBox(
                    x=xmin, y=ymin, width=xmax - xmin, height=ymax - ymin
                ),
                orientation=orientation,
                source_label=label,
                dataset_id=DATASET_ID,
            )
        )

    return VOCAnnotation(
        image=image,
        annotations=annotations,
        unmapped_labels=unmapped,
        skipped=skipped,
    )


def load_ltspice_asc(path: Path):
    """LTspice schematic to netlist conversion is deferred to M2."""
    raise NotImplementedError(
        "CGHD LTspice (.asc) netlist conversion is part of M2."
    )
