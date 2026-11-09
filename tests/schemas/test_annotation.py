import pytest
from pydantic import ValidationError

from vca.schemas.annotation import (
    AnnotationRecord,
    BoundingBox,
    CategoryRecord,
    COCODataset,
    ImageRecord,
)


@pytest.fixture
def valid_annotation():
    return AnnotationRecord(
        id=1,
        image_id=1,
        category_id=0,
        bbox=BoundingBox(x=10.0, y=20.0, width=30.0, height=40.0),
        source_label="resistor",
        dataset_id="test_dataset",
    )


def test_valid_annotation(valid_annotation):
    assert valid_annotation.id == 1
    assert valid_annotation.category_id == 0
    assert valid_annotation.orientation is None


def test_category_id_zero_is_valid(valid_annotation):
    assert valid_annotation.category_id == 0


@pytest.mark.parametrize("orientation", [0.0, 90.0, 180.0, 359.999])
def test_valid_orientation(orientation, valid_annotation):
    valid_annotation.orientation = orientation
    assert valid_annotation.orientation == orientation


@pytest.mark.parametrize("orientation", [-1.0, 360.0])
def test_invalid_orientation(orientation):
    with pytest.raises(ValidationError):
        AnnotationRecord(
            id=1,
            image_id=1,
            category_id=1,
            bbox=BoundingBox(x=0, y=0, width=10, height=10),
            orientation=orientation,
            source_label="resistor",
            dataset_id="test_dataset",
        )


@pytest.mark.parametrize("field", ["id", "image_id"])
def test_annotation_ids_must_be_positive(field):
    data = {
        "id": 1,
        "image_id": 1,
        "category_id": 0,
        "bbox": {"x": 0, "y": 0, "width": 10, "height": 10},
        "source_label": "resistor",
        "dataset_id": "test_dataset",
    }
    data[field] = 0

    with pytest.raises(ValidationError):
        AnnotationRecord(**data)


def test_negative_category_id_is_invalid():
    with pytest.raises(ValidationError):
        CategoryRecord(id=-1, name="resistor")


def test_image_dimensions_must_be_positive():
    with pytest.raises(ValidationError):
        ImageRecord(id=1, file_name="circuit.png", width=0, height=100)


def test_coco_dataset_nested_models():
    dataset = COCODataset(
        images=[ImageRecord(id=1, file_name="circuit.png", width=100, height=100)],
        annotations=[
            AnnotationRecord(
                id=1,
                image_id=1,
                category_id=0,
                bbox=BoundingBox(x=0, y=0, width=10, height=10),
                source_label="unknown",
                dataset_id="test_dataset",
            )
        ],
        categories=[CategoryRecord(id=0, name="unknown")],
    )

    assert len(dataset.images) == 1
    assert len(dataset.annotations) == 1
    assert len(dataset.categories) == 1


def test_segmentation_default_is_independent():
    first = AnnotationRecord(
        id=1,
        image_id=1,
        category_id=0,
        bbox=BoundingBox(x=0, y=0, width=10, height=10),
        source_label="resistor",
        dataset_id="test_dataset",
    )
    second = AnnotationRecord(
        id=2,
        image_id=1,
        category_id=0,
        bbox=BoundingBox(x=0, y=0, width=10, height=10),
        source_label="capacitor",
        dataset_id="test_dataset",
    )

    first.segmentation.append([1.0, 2.0])

    assert second.segmentation == []

def test_coco_dataset_json_round_trip():
    dataset = COCODataset(
        images=[
            ImageRecord(
                id=1,
                file_name="circuit.png",
                width=640,
                height=480,
            )
        ],
        annotations=[
            AnnotationRecord(
                id=1,
                image_id=1,
                category_id=0,
                bbox=BoundingBox(x=10, y=20, width=30, height=40),
                segmentation=[[10.0, 20.0, 40.0, 20.0]],
                orientation=90.0,
                source_label="resistor",
                dataset_id="test_dataset",
            )
        ],
        categories=[CategoryRecord(id=0, name="unknown")],
    )

    json_data = dataset.model_dump_json()
    restored = COCODataset.model_validate_json(json_data)

    assert restored == dataset