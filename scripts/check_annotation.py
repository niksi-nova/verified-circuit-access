"""Validate a private Labelme rectangle file and its matching golden netlist."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from pydantic import BaseModel, Field

from vca.schemas.annotation import AnnotationRecord, BoundingBox, ImageRecord
from vca.schemas.netlist import Netlist
from vca.schemas.ports import CATEGORY_TERMINALS, OPTIONAL_TERMINALS
from vca.schemas.taxonomy import TAXONOMY

CONTEXT = {"ground", "vdd", "port", "antenna", "cross-line-curved"}
LABEL_IDS = {}
for entry in TAXONOMY.entries:
    if entry.canonical_name in CONTEXT or entry.canonical_name in CATEGORY_TERMINALS:
        LABEL_IDS.setdefault(entry.canonical_name, entry.canonical_id)


class Shape(BaseModel):
    label: str
    group_id: int | None = Field(default=None, ge=1)
    shape_type: str
    points: list[tuple[float, float]]


class Labelme(BaseModel):
    imagePath: str
    imageWidth: int
    imageHeight: int
    shapes: list[Shape]


def validate_pair(
    labelme_path: Path, netlist_path: Path
) -> tuple[ImageRecord, Netlist]:
    labels = Labelme.model_validate_json(labelme_path.read_text(encoding="utf-8"))
    image = ImageRecord(
        id=1,
        file_name=Path(labels.imagePath).name,
        width=labels.imageWidth,
        height=labels.imageHeight,
    )
    graph = Netlist.model_validate_json(netlist_path.read_text(encoding="utf-8"))
    boxes = {}
    for index, shape in enumerate(labels.shapes, 1):
        if shape.label not in LABEL_IDS:
            raise ValueError(f"Shape {index} has unknown category {shape.label!r}.")
        if shape.shape_type != "rectangle" or len(shape.points) != 2:
            raise ValueError(f"Shape {index} must be a two-corner rectangle.")
        (xa, ya), (xb, yb) = shape.points
        x1, x2 = sorted((xa, xb))
        y1, y2 = sorted((ya, yb))
        if not all(map(math.isfinite, (xa, ya, xb, yb))) or not (
            0 <= x1 < x2 <= image.width and 0 <= y1 < y2 <= image.height
        ):
            raise ValueError(f"Shape {index} must have positive area inside the image.")
        annotation = AnnotationRecord(
            id=index,
            image_id=image.id,
            category_id=LABEL_IDS[shape.label],
            bbox=BoundingBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1),
            source_label=shape.label,
            dataset_id="curriculum",
        )
        if shape.label in CONTEXT:
            if shape.group_id is not None:
                raise ValueError(f"Context shape {index} must have no group ID.")
            continue
        if shape.group_id is None:
            raise ValueError(f"Shape {index} needs a component group ID.")
        part = f"C{shape.group_id}"
        if part in boxes:
            raise ValueError(f"Multiple rectangles use {part}.")
        boxes[part] = annotation

    parts = {component.id: component for component in graph.components}
    if not parts or boxes.keys() != parts.keys():
        raise ValueError(
            "Electrical rectangles and netlist components must have matching IDs. "
            f"Only in Labelme: {sorted(boxes.keys() - parts.keys())}. "
            f"Only in netlist: {sorted(parts.keys() - boxes.keys())}."
        )
    for part_id, component in parts.items():
        category = component.canonical_category
        if (
            category != boxes[part_id].source_label
            or category not in CATEGORY_TERMINALS
        ):
            raise ValueError(f"{part_id} has an unsupported or mismatched category.")
        expected = set(CATEGORY_TERMINALS[category])
        actual = {terminal.name for terminal in component.terminals}
        if (
            not expected - OPTIONAL_TERMINALS.get(category, frozenset())
            <= actual
            <= expected
        ):
            raise ValueError(
                f"{part_id} has invalid terminal names. "
                f"Use {', '.join(sorted(expected))}."
            )
        if component.bbox is not None and component.bbox != boxes[part_id].bbox:
            raise ValueError(
                f"{part_id} netlist box differs from the Labelme rectangle."
            )
    return image, graph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labelme", type=Path)
    parser.add_argument("netlist", type=Path)
    args = parser.parse_args()
    try:
        _, graph = validate_pair(args.labelme, args.netlist)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Annotation error: {error}\n")
    print(
        f"Valid annotation: {len(graph.components)} components, {len(graph.nets)} nets."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
