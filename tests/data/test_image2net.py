from pathlib import Path

import pytest

from vca.data.image2net import (
    load_labelme_json,
    load_validation_netlist,
    load_yolo_obb,
)
from vca.schemas.netlist import Netlist

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "labelme_sample.json"
)

VALIDATION_NETLIST_PATH = (
    Path(__file__).parent / "fixtures" / "validation_netlist_sample.json"
)

YOLO_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "yolo_obb_sample.txt"
)


def test_load_labelme_json_returns_four_annotations():
    records = load_labelme_json(FIXTURE_PATH)
    assert len(records) == 4


def test_load_labelme_json_preserves_source_labels():
    records = load_labelme_json(FIXTURE_PATH)
    labels = [record.source_label for record in records]

    assert labels == ["resistor", "capacitor", "diode", "npn"]


def test_load_labelme_json_converts_bbox():
    records = load_labelme_json(FIXTURE_PATH)
    bbox = records[0].bbox

    assert bbox.x == 20
    assert bbox.y == 30
    assert bbox.width == 60
    assert bbox.height == 20


def test_load_labelme_json_assigns_annotation_ids():
    records = load_labelme_json(FIXTURE_PATH)
    assert [record.id for record in records] == [1, 2, 3, 4]


def test_load_labelme_json_assigns_dataset_id():
    records = load_labelme_json(FIXTURE_PATH)
    assert all(record.dataset_id == "Image2Net" for record in records)


def test_load_labelme_json_missing_shapes(tmp_path):
    path = tmp_path / "missing_shapes.json"
    path.write_text(
        '{"imageWidth": 100, "imageHeight": 100}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing field 'shapes'"):
        load_labelme_json(path)


def test_load_labelme_json_invalid_json(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid JSON"):
        load_labelme_json(path)


def test_load_labelme_json_shapes_must_be_list(tmp_path):
    path = tmp_path / "bad_shapes.json"
    path.write_text(
        '{"shapes": {}, "imageWidth": 100, "imageHeight": 100}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="'shapes' must be a list"):
        load_labelme_json(path)


def test_load_labelme_json_preserves_unknown_label(tmp_path):
    path = tmp_path / "unknown_label.json"
    path.write_text(
        """
        {
            "imageWidth": 100,
            "imageHeight": 100,
            "shapes": [
                {
                    "label": "unknown_component_xyz",
                    "points": [[10, 20], [30, 40]]
                }
            ]
        }
        """,
        encoding="utf-8",
    )

    records = load_labelme_json(path)

    assert len(records) == 1
    assert records[0].source_label == "unknown_component_xyz"
    assert records[0].category_id == 0


def test_load_labelme_json_rejects_non_object_shape(tmp_path):
    path = tmp_path / "bad_shape.json"
    path.write_text(
        '{"imageWidth": 100, "imageHeight": 100, "shapes": [null]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="shape 1 must be an object"):
        load_labelme_json(path)


def test_load_labelme_json_empty_file_returns_empty_list(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("", encoding="utf-8")

    assert load_labelme_json(path) == []


def test_load_yolo_obb_returns_one_annotation_per_row():
    records = load_yolo_obb(YOLO_FIXTURE_PATH, 100, 100)
    assert len(records) == 4


def test_load_yolo_obb_converts_polygon_to_bbox():
    records = load_yolo_obb(YOLO_FIXTURE_PATH, 100, 100)
    bbox = records[0].bbox

    assert bbox.x == pytest.approx(10)
    assert bbox.y == pytest.approx(10)
    assert bbox.width == pytest.approx(10)
    assert bbox.height == pytest.approx(10)


def test_load_yolo_obb_preserves_class_id():
    records = load_yolo_obb(YOLO_FIXTURE_PATH, 100, 100)

    assert records[0].source_label == "class_0"
    assert records[2].source_label == "class_1"
    assert all(record.category_id == 0 for record in records)


def test_load_yolo_obb_empty_file_returns_empty_list(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")

    assert load_yolo_obb(path, 100, 100) == []


def test_load_yolo_obb_rejects_out_of_range_coordinates(tmp_path):
    path = tmp_path / "bad_coordinates.txt"
    path.write_text(
        "0 1.1 0.1 0.2 0.1 0.2 0.2 0.1 0.2",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="outside"):
        load_yolo_obb(path, 100, 100)


def test_load_yolo_obb_rejects_malformed_row(tmp_path):
    path = tmp_path / "malformed.txt"
    path.write_text("0 0.1 0.2 0.3", encoding="utf-8")

    with pytest.raises(ValueError, match="9 values"):
        load_yolo_obb(path, 100, 100)


def test_load_validation_netlist_returns_two_circuits():
    result = load_validation_netlist(VALIDATION_NETLIST_PATH)
    assert len(result) == 2


def test_validation_netlist_contains_components_and_nets():
    result = load_validation_netlist(VALIDATION_NETLIST_PATH)

    first = result[0]
    assert len(first.components) == 3
    assert {component.id for component in first.components} == {
        "C1", "C2", "C3"
    }
    assert {net.name for net in first.nets} == {
        "net1", "net2", "net3"
    }


def test_validation_netlist_returns_schema_objects():
    result = load_validation_netlist(VALIDATION_NETLIST_PATH)

    assert all(isinstance(netlist, Netlist) for netlist in result)


def test_validation_netlist_empty_file_returns_empty_list(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text("", encoding="utf-8")

    assert load_validation_netlist(path) == []


def test_validation_netlist_missing_field_raises_value_error(tmp_path):
    path = tmp_path / "malformed.json"
    path.write_text('[{"wrong_field": []}]', encoding="utf-8")

    with pytest.raises(ValueError, match="ckt_netlist"):
        load_validation_netlist(path)


def test_validation_netlist_accepts_image2net_object_format(tmp_path):
    path = tmp_path / "image2net.json"
    path.write_text(
        """
        {
            "ckt_netlist": [
                {
                    "component_type": "Res",
                    "port_connection": {
                        "Pos": "VDD",
                        "Neg": "net1"
                    }
                }
            ],
            "ckt_type": "TestCircuit"
        }
        """,
        encoding="utf-8",
    )

    result = load_validation_netlist(path)

    assert len(result) == 1
    assert len(result[0].components) == 1
    assert {net.name for net in result[0].nets} == {"VDD", "net1"}
    assert all(len(net.endpoints) == 1 for net in result[0].nets)