"""Run the pinned CPU pipeline and existing metrics on private annotated figures."""

from __future__ import annotations

import argparse
import json
import os
import random
from datetime import UTC, datetime
from pathlib import Path

from check_annotation import validate_pair
from eval_pipeline import mean, score_netlists
from PIL import Image

from vca.api.engine import Engine
from vca.training import code_commit

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def evaluate(folder: Path, seed: int, timeout: float) -> Path | None:
    labels = sorted((folder / "labelme").glob("*.json"))
    truths = {path.stem: path for path in (folder / "netlists").glob("*.json")}
    if not labels and not truths:
        print("no annotated figures found")
        return None
    if {path.stem for path in labels} != truths.keys():
        raise ValueError(
            "Labelme and netlist folders must contain the same figure IDs."
        )

    pairs = []
    for annotation in labels:
        image, truth = validate_pair(annotation, truths[annotation.stem])
        image_path = folder / "images" / image.file_name
        if image_path.stem != annotation.stem or image_path.suffix.lower() not in {
            ".png",
            ".jpg",
            ".jpeg",
        }:
            raise ValueError(f"{annotation.stem}: use a matching PNG or JPEG filename.")
        with Image.open(image_path) as source:
            if source.size != (image.width, image.height):
                raise ValueError(
                    f"{annotation.stem}: Labelme and image dimensions differ."
                )
            source.verify()
        pairs.append((image_path, truth))

    os.environ["YOLO_OFFLINE"] = "true"
    os.environ["YOLO_AUTOINSTALL"] = "false"
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    engine = Engine(ROOT)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    out = ROOT / "results" / "m2" / "curriculum" / stamp
    predictions = out / "predictions"
    predictions.mkdir(parents=True, exist_ok=False)
    config = json.loads((engine.pipeline_run_dir / "config.json").read_text())
    write_json(
        out / "config.json",
        {
            "pipeline_run": engine.pipeline_run,
            "weights": config["weights"],
            "conf": config["conf"],
            "imgsz": config["imgsz"],
            "detect_plain_crossings": config["detect_plain_crossings"],
            "device": "cpu",
            "seed": seed,
            "code_commit": code_commit(),
            "ged_timeout_s": timeout,
            "figures": [path.stem for path, _ in pairs],
        },
    )
    scores = []
    for path, truth in pairs:
        with Image.open(path) as image:
            predicted = engine.pipeline(image).netlist
        score = score_netlists(path.stem, predicted, truth, timeout)
        write_json(
            predictions / f"{path.stem}.json",
            {
                "netlist": predicted.model_dump(mode="json"),
                "score": score,
            },
        )
        scores.append(score)
    write_json(
        out / "metrics.json",
        {
            "circuits": len(scores),
            "exact_graphs": sum(row["graph_isomorphism"] for row in scores),
            **{
                f"mean_{metric}": mean(row[metric] for row in scores)
                for metric in (
                    "ned",
                    "ned_lower_bound",
                    "connection_precision",
                    "connection_recall",
                )
            },
        },
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ged-timeout", type=float, default=30)
    args = parser.parse_args()
    try:
        out = evaluate(args.folder, args.seed, args.ged_timeout)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"Evaluation error: {error}\n")
    if out is not None:
        print(f"Wrote private results to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
