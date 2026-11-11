import json
from pathlib import Path

import numpy as np
from PIL import Image

from vca.detect.classes import CLASS_INDEX
from vca.detect.dataset import build_detector_dataset, split_groups, yolo_line


def labelme(image: Path, shapes: list[tuple[str, list[list[float]]]]) -> None:
    w, h = Image.open(image).size
    image.with_suffix(".json").write_text(
        json.dumps(
            {
                "shapes": [
                    {"label": label, "points": pts, "shape_type": "rectangle"}
                    for label, pts in shapes
                ],
                "imageWidth": w,
                "imageHeight": h,
            }
        )
    )


def test_yolo_line_normalises_and_clips():
    assert yolo_line(3, (10, 20, 30, 60), 100, 100) == (
        "3 0.200000 0.400000 0.200000 0.400000"
    )
    assert yolo_line(0, (-10, 0, 50, 50), 100, 100).startswith("0 0.250000")
    assert yolo_line(0, (5, 5, 5.5, 50), 100, 100) is None


def test_split_keeps_groups_together_and_is_deterministic():
    groups = [0, 0, 1, 2, 2, 2, 3, 4, 5, 6]
    first = split_groups(groups, 0.3, seed=1)
    assert first == split_groups(groups, 0.3, seed=1)
    for g in set(groups):
        assert len({s for s, gg in zip(first, groups, strict=True) if gg == g}) == 1


def test_validation_copies_are_excluded(tmp_path, pattern):
    det, val = tmp_path / "det", tmp_path / "val"
    det.mkdir()
    val.mkdir()
    for i in range(6):
        labelme(
            pattern(det / f"{i}.png", i + 10), [("resistor2", [[10, 10], [40, 30]])]
        )
    (val / "v.png").write_bytes((det / "3.png").read_bytes())

    manifest = build_detector_dataset(det, val, tmp_path / "out", val_fraction=0.4)

    assert [e["image"] for e in manifest["excluded_validation_overlaps"]] == ["3.png"]
    written = sorted((tmp_path / "out" / "labels").glob("*/*.txt"))
    assert len(written) == 5
    assert all(t.read_text().startswith(f"{CLASS_INDEX['resistor']} ") for t in written)
    assert "names:\n  0: nmos" in (tmp_path / "out" / "data.yaml").read_text()


def test_cghd_unmapped_symbols_are_painted_out(tmp_path, pattern):
    det, val = tmp_path / "det", tmp_path / "val"
    det.mkdir()
    val.mkdir()
    drafter = tmp_path / "cghd" / "drafter_1"
    (drafter / "images").mkdir(parents=True)
    (drafter / "annotations").mkdir()
    pixels = np.full((100, 200, 3), 230, dtype=np.uint8)
    pixels[20:40, 20:60] = 0  # a "transistor.bjt" (masked)
    pixels[60:80, 100:150] = 0  # a "resistor" (kept)
    Image.fromarray(pixels).save(drafter / "images" / "C1_D1_P1.png")
    objects = "".join(
        f"<object><name>{name}</name><bndbox><xmin>{x1}</xmin><ymin>{y1}</ymin>"
        f"<xmax>{x2}</xmax><ymax>{y2}</ymax></bndbox></object>"
        for name, x1, y1, x2, y2 in (
            ("transistor.bjt", 20, 20, 60, 40),
            ("resistor", 100, 60, 150, 80),
        )
    )
    (drafter / "annotations" / "C1_D1_P1.xml").write_text(
        "<annotation><filename>C1_D1_P1.png</filename><size><width>200</width>"
        f"<height>100</height></size>{objects}</annotation>"
    )

    manifest = build_detector_dataset(
        det, val, tmp_path / "out", cghd_dir=tmp_path / "cghd"
    )

    assert manifest["cghd"]["masked_boxes"] == 1
    out_image = np.asarray(
        Image.open(tmp_path / "out/images/train/cghd_drafter_1_C1_D1_P1.jpg")
    )
    assert out_image[25:35, 25:55].mean() > 200  # painted with paper colour
    assert out_image[65:75, 105:145].mean() < 50  # kept symbol untouched
    label = (tmp_path / "out/labels/train/cghd_drafter_1_C1_D1_P1.txt").read_text()
    assert label.split()[0] == str(CLASS_INDEX["resistor"])
