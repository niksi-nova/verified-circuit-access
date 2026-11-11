from pathlib import Path

from vca.classify.datasets import (
    build_crossing_dataset,
    build_orientation_datasets,
    orientation_group,
)


def test_orientation_group_strips_rotation_prefix():
    assert orientation_group("d5") == orientation_group("ll5") == "5"
    assert orientation_group("r0_02") == "0_02"


def test_rotated_copies_never_straddle_the_split(tmp_path, pattern):
    task = tmp_path / "orient" / "train_bjt_d"
    for label in "dulr":
        (task / label).mkdir(parents=True)
        for i in range(10):
            pattern(task / label / f"{label}{i}.png", i)

    summary = build_orientation_datasets(
        tmp_path / "orient", tmp_path / "out", val_fraction=0.3, seed=0
    )

    assert summary["tasks"]["bjt_d"]["groups"] == 10
    val_ids = {p.stem[1:] for p in (tmp_path / "out/bjt_d/val").rglob("*.png")}
    train_ids = {p.stem[1:] for p in (tmp_path / "out/bjt_d/train").rglob("*.png")}
    assert val_ids and not (val_ids & train_ids)


def test_crossing_dataset_drops_evaluation_copies(tmp_path, pattern):
    jumper, val = tmp_path / "jumper", tmp_path / "val"
    (jumper / "images" / "train").mkdir(parents=True)
    (jumper / "labels" / "train").mkdir(parents=True)
    val.mkdir()
    for i in range(5):
        pattern(jumper / "images" / "train" / f"{i}.png", i + 20)
        (jumper / "labels" / "train" / f"{i}.txt").write_text(
            f"{i % 3} 0.1 0.1 0.2 0.1 0.2 0.2 0.1 0.2\n"
        )
    (val / "eval.png").write_bytes((jumper / "images/train/2.png").read_bytes())

    manifest = build_crossing_dataset(jumper, val, tmp_path / "out")

    assert [e["image"] for e in manifest["excluded_validation_overlaps"]] == [
        "train/2.png"
    ]
    assert sum(manifest["images"].values()) == 4
    assert Path(tmp_path / "out/data.yaml").read_text().startswith("train:")
