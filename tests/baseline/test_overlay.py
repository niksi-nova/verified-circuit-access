"""Tests for evaluation overlay rendering."""

from pathlib import Path

from PIL import Image

from vca.baseline.overlay import render_overlay
from vca.schemas.annotation import AnnotationRecord, BoundingBox


def test_render_overlay_creates_valid_png(tmp_path: Path):
    image_path = tmp_path / "input.png"
    output_path = tmp_path / "overlay.png"

    Image.new("RGB", (100, 100), "white").save(image_path)

    ground_truth = [
        AnnotationRecord(
            id=1,
            image_id=1,
            category_id=1,
            bbox=BoundingBox(x=10, y=10, width=30, height=30),
            source_label="resistor",
            dataset_id="Image2Net",
        )
    ]

    predictions = [
        AnnotationRecord(
            id=2,
            image_id=1,
            category_id=1,
            bbox=BoundingBox(x=50, y=50, width=20, height=20),
            source_label="resistor",
            dataset_id="Image2Net",
        )
    ]

    result_path = render_overlay(
        image_path,
        ground_truth,
        predictions,
        output_path,
    )

    assert result_path == output_path
    assert output_path.exists()

    with Image.open(output_path) as rendered:
        assert rendered.format == "PNG"
        assert rendered.size == (100, 100)