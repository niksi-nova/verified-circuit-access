from pathlib import Path

import pytest

from vca.data.cghd import CGHDFormatError, load_ltspice_asc, load_pascal_voc

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_pascal_voc_boxes_become_coco_records():
    result = load_pascal_voc(
        FIXTURES_DIR / "pascal_voc_sample.xml", image_id=7, first_annotation_id=3
    )

    assert result.image.file_name == "circuit_sample.png"
    assert (result.image.width, result.image.height) == (100, 100)
    assert [a.source_label for a in result.annotations] == ["resistor", "capacitor"]
    first = result.annotations[0]
    assert (first.id, first.image_id, first.dataset_id) == (3, 7, "CGHD")
    assert (first.bbox.x, first.bbox.y, first.bbox.width, first.bbox.height) == (
        10,
        20,
        30,
        10,
    )


def test_labels_without_a_mapping_are_reported():
    result = load_pascal_voc(FIXTURES_DIR / "pascal_voc_sample.xml")

    assert result.unmapped_labels == {"resistor", "capacitor"}
    assert all(a.category_id == 0 for a in result.annotations)


@pytest.mark.parametrize(
    ("anchor", "inserted"),
    [
        # CGHD's own layout: rotation inside the box.
        ("<ymax>30</ymax>", "<ymax>30</ymax><rotation>450</rotation>"),
        ("<name>resistor</name>", "<name>resistor</name><rotation>450</rotation>"),
    ],
)
def test_rotation_is_read_when_present(tmp_path, anchor, inserted):
    xml = (FIXTURES_DIR / "pascal_voc_sample.xml").read_text()
    path = tmp_path / "rotated.xml"
    path.write_text(xml.replace(anchor, inserted, 1))

    assert load_pascal_voc(path).annotations[0].orientation == 90.0


def test_zero_area_box_is_skipped_and_reported(tmp_path):
    xml = (FIXTURES_DIR / "pascal_voc_sample.xml").read_text()
    path = tmp_path / "degenerate.xml"
    path.write_text(xml.replace("<xmax>40</xmax>", "<xmax>10</xmax>", 1))

    result = load_pascal_voc(path, first_annotation_id=5)

    assert [a.source_label for a in result.annotations] == ["capacitor"]
    assert result.annotations[0].id == 5
    assert result.skipped == ["object 0 ('resistor'): zero-area box"]


@pytest.mark.parametrize(
    "xml",
    [
        "<annotation><filename>a.png</filename></annotation>",
        "<annotation><filename>a.png</filename><size><width>10</width>"
        "<height>10</height></size><object><name>r</name></object></annotation>",
        "not xml",
    ],
)
def test_malformed_files_raise(tmp_path, xml):
    path = tmp_path / "bad.xml"
    path.write_text(xml)

    with pytest.raises(CGHDFormatError):
        load_pascal_voc(path)


def test_ltspice_is_deferred_to_m2():
    with pytest.raises(NotImplementedError):
        load_ltspice_asc(FIXTURES_DIR / "ltspice_sample.asc")
