"""Net extraction with ground-truth boxes (no detector, no classifiers).

Some Image2Net detection images are copies of netlist-evaluation circuits
(found by the M2 leakage check and excluded from detector training). They
carry hand-drawn component boxes *and* have a golden netlist, so they
measure the net-extraction stage on its own: boxes are perfect. Terminal
orientation comes from drawing conventions, or, with
``--orientation-results``, from the trained orientation classifiers.

    uv run python scripts/eval_netting_oracle.py

Writes results/m2/netting_oracle/<run_id>/{config,metrics}.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from vca.data.image2net import load_validation_netlist
from vca.detect.classes import from_image2net
from vca.metrics.alignment import align, connection_scores, ned_from_alignment
from vca.netting.extract import Detection, extract_netlist
from vca.netting.orient import YoloClassifiers, orient
from vca.training import code_commit, uncommitted_diff


def detections(labelme_json: Path) -> list[Detection]:
    data = json.loads(labelme_json.read_text(encoding="utf-8"))
    out = []
    for shape in data["shapes"]:
        (x1, y1), (x2, y2) = shape["points"]
        out.append(
            Detection(
                from_image2net(shape["label"]),
                (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)),
            )
        )
    return out


_CLASSIFIERS: dict[Path, YoloClassifiers] = {}


def score(job, timeout: float) -> dict:
    item, detection_dir, golden_dir, plain_crossings, orientation_dir = job
    image_path = detection_dir / item["image"]
    (truth,) = load_validation_netlist(
        golden_dir / (Path(item["validation_image"]).stem + ".json")
    )
    image = Image.open(image_path)
    dets = detections(image_path.with_suffix(".json"))
    if orientation_dir is not None:
        if orientation_dir not in _CLASSIFIERS:  # once per worker process
            _CLASSIFIERS[orientation_dir] = YoloClassifiers.from_results(
                orientation_dir
            )
        dets, _ = orient(image, dets, _CLASSIFIERS[orientation_dir])
    result = extract_netlist(image, dets, detect_plain_crossings=plain_crossings)
    predicted = result.netlist
    alignment = align(predicted, truth, timeout=timeout)
    precision, recall = connection_scores(predicted, truth, alignment)
    return {
        "image": item["image"],
        "validation_image": item["validation_image"],
        "hash_distance": item["distance"],
        "components_true": len(truth.components),
        "components_pred": len(predicted.components),
        "ned": ned_from_alignment(alignment, truth),
        "ned_exact": alignment.exact,
        "graph_isomorphism": alignment.isomorphic,
        "connection_precision": precision,
        "connection_recall": recall,
        "unconnected_terminals": sum(
            len(c.unconnected_terminals) for c in result.components
        ),
        "extra_contacts": sum(c.extra_contacts for c in result.components),
        "crossings_cut": result.crossings_cut,
        "orientation_sources": dict(
            Counter(c.layout.orientation_source for c in result.components)
        ),
    }


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 5) if values else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--manifest", default="data/m2/detector_i2n/manifest.json", type=Path
    )
    parser.add_argument(
        "--detection-dir",
        default="data/image2net/train/device_identification",
        type=Path,
    )
    parser.add_argument("--golden-dir", default="data/image2net/golden", type=Path)
    parser.add_argument("--output-dir", default="results/m2/netting_oracle", type=Path)
    parser.add_argument("--no-plain-crossings", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0, help="GED search, s")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument(
        "--orientation-results",
        type=Path,
        default=None,
        help="folder with orientation_<task>/<run>/weights/best.pt "
        "(latest run per task); default: drawing conventions",
    )
    args = parser.parse_args(argv)

    overlaps = json.loads(args.manifest.read_text(encoding="utf-8"))[
        "excluded_validation_overlaps"
    ]
    jobs = [
        (
            item,
            args.detection_dir,
            args.golden_dir,
            not args.no_plain_crossings,
            args.orientation_results,
        )
        for item in sorted(overlaps, key=lambda e: e["validation_image"])
        if (args.golden_dir / (Path(item["validation_image"]).stem + ".json")).exists()
    ]
    # One graph alignment per circuit (GED search, up to --timeout seconds),
    # circuits spread over worker processes.
    rows = []
    with ProcessPoolExecutor(args.workers) as pool:
        for row in pool.map(score, jobs, [args.timeout] * len(jobs)):
            rows.append(row)
            print(
                f"{row['validation_image']} <- {row['image']:>9}  "
                f"d={row['hash_distance']:>2}  ned={row['ned']}",
                flush=True,
            )

    def summary(subset):
        return {
            "circuits": len(subset),
            "macro_ned": mean([r["ned"] for r in subset]),
            "ned_exact_fraction": mean([float(r["ned_exact"]) for r in subset]),
            "graph_isomorphism_accuracy": mean(
                [float(r["graph_isomorphism"]) for r in subset]
            ),
            "macro_connection_precision": mean(
                [r["connection_precision"] for r in subset]
            ),
            "macro_connection_recall": mean([r["connection_recall"] for r in subset]),
            "component_count_match": mean(
                [float(r["components_true"] == r["components_pred"]) for r in subset]
            ),
        }

    metrics = {
        "all": summary(rows),
        "exact_copies": summary([r for r in rows if r["hash_distance"] == 0]),
        "per_circuit": rows,
    }
    run_dir = args.output_dir / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)
    commit = code_commit()
    config = {
        "stage": "net extraction, ground-truth boxes, conventional orientation",
        "manifest": str(args.manifest),
        "detect_plain_crossings": not args.no_plain_crossings,
        "ged_timeout_s": args.timeout,
        "orientation": (
            {
                task: str(path)
                for task, path in YoloClassifiers.weights_in(
                    args.orientation_results
                ).items()
            }
            if args.orientation_results
            else "drawing conventions"
        ),
        "code_commit": commit,
        "python": sys.version.split()[0],
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), "utf-8")
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), "utf-8")
    if str(commit).endswith("-dirty"):
        (run_dir / "uncommitted.diff").write_text(uncommitted_diff(), "utf-8")
    print(json.dumps({k: metrics[k] for k in ("all", "exact_copies")}, indent=2))
    print("wrote", run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
