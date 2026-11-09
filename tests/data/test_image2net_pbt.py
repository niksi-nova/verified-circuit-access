
"""Property-based tests for Image2Net annotation loading."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from vca.data.image2net import load_labelme_json, load_yolo_obb
from vca.schemas.taxonomy import TAXONOMY


@st.composite
def unknown_label_annotations(draw):
    """Generate Labelme shapes with labels absent from the taxonomy."""
    count = draw(st.integers(min_value=1, max_value=20))
    shapes = []

    for _ in range(count):
        suffix = draw(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
                min_size=1,
                max_size=12,
            )
        )
        label = f"pbt_unknown_{suffix}"

        assume(
            TAXONOMY.get_canonical("Image2Net", label) == ("unknown", 0)
        )

        x1 = draw(st.floats(
            min_value=0,
            max_value=100,
            allow_nan=False,
            allow_infinity=False,
        ))
        y1 = draw(st.floats(
            min_value=0,
            max_value=100,
            allow_nan=False,
            allow_infinity=False,
        ))
        x2 = draw(st.floats(
            min_value=101,
            max_value=200,
            allow_nan=False,
            allow_infinity=False,
        ))
        y2 = draw(st.floats(
            min_value=101,
            max_value=200,
            allow_nan=False,
            allow_infinity=False,
        ))

        shapes.append({
            "label": label,
            "points": [[x1, y1], [x2, y2]],
        })

    return shapes


# Feature: m1-data-audit-baseline, Property 4: Unknown labels preserved
@given(shapes=unknown_label_annotations())
@settings(max_examples=100)
def test_unknown_source_labels_are_preserved(shapes: list[dict]) -> None:
    annotation_data = {
        "shapes": shapes,
        "imageWidth": 300,
        "imageHeight": 300,
    }

    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "unknown_annotations.json"
        path.write_text(json.dumps(annotation_data), encoding="utf-8")

        annotations = load_labelme_json(path)

    assert len(annotations) == len(shapes)

    for source_shape, annotation in zip(shapes, annotations, strict=True):
        assert annotation.source_label == source_shape["label"]
        assert annotation.category_id == 0
        assert annotation.dataset_id == "Image2Net"


@st.composite
def valid_yolo_obb_rows(draw):
    """Generate valid YOLO OBB rows with normalized coordinates."""
    class_id = draw(st.integers(min_value=0, max_value=20))

    coordinates = draw(
        st.lists(
            st.floats(
                min_value=0.0,
                max_value=1.0,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=8,
            max_size=8,
        )
    )

    return [class_id, *coordinates]


# Feature: m1-data-audit-baseline, Property 5: YOLO OBB coordinate validity
@given(rows=st.lists(valid_yolo_obb_rows(), min_size=0, max_size=20))
@settings(max_examples=100)
def test_yolo_obb_coordinates_produce_valid_annotations(rows: list) -> None:
    image_width = 640
    image_height = 480

    content = "\n".join(
        " ".join(str(value) for value in row)
        for row in rows
    )

    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "sample.txt"
        path.write_text(content, encoding="utf-8")

        annotations = load_yolo_obb(
            path,
            image_width=image_width,
            image_height=image_height,
        )

    assert len(annotations) == len(rows)

    for annotation in annotations:
        bbox = annotation.bbox

        assert 0 <= bbox.x <= image_width
        assert 0 <= bbox.y <= image_height
        assert 0 <= bbox.width <= image_width
        assert 0 <= bbox.height <= image_height

        assert bbox.x + bbox.width <= image_width
        assert bbox.y + bbox.height <= image_height
