"""Run the full M2 pipeline on the Image2Net evaluation circuits.

Detector + crossing model + orientation classifiers + net extraction on
every image in ``--images``, scored against ``--golden`` with the
Image2Net NED (one GED alignment per circuit, ``--timeout`` seconds).

    uv run python scripts/eval_pipeline.py \\
        --detector results/m2/detector_i2n_cghd/<run>/weights/best.pt \\
        --crossings results/m2/crossing/<run>/weights/best.pt \\
        --orientation-results results/m2

Writes ``results/m2/pipeline/<run_id>/``:

- ``config.json``: weights (path + sha256), thresholds, code commit.
- ``metrics.json``: macro NED, isomorphism accuracy, connection P/R.
- ``predictions/<id>.json``: predicted netlist, per-component evidence
  (verifier features), rule report, alignment to the golden netlist and the
  component-level errors it implies (the verifier's labels).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vca.data.image2net import load_validation_netlist  # noqa: E402
from vca.metrics.alignment import (  # noqa: E402
    align,
    connection_scores,
    diagnose,
    ned_from_alignment,
)
from vca.netting.orient import YoloClassifiers  # noqa: E402
from vca.pipeline import Pipeline, YoloCrossings, YoloDetector  # noqa: E402
from vca.schemas.netlist import Netlist  # noqa: E402
from vca.training import code_commit, uncommitted_diff  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def score(job: tuple[str, str, str, float]) -> dict:
    circuit_id, predicted_json, golden_path, timeout = job
    predicted = Netlist.model_validate_json(predicted_json)
    (truth,) = load_validation_netlist(Path(golden_path))
    alignment = align(predicted, truth, timeout=timeout)
    precision, recall = connection_scores(predicted, truth, alignment)
    return {
        "circuit_id": circuit_id,
        "ned": ned_from_alignment(alignment, truth),
        "ned_exact": alignment.exact,
        "graph_isomorphism": alignment.isomorphic,
        "connection_precision": precision,
        "connection_recall": recall,
        "components_true": len(truth.components),
        "components_pred": len(predicted.components),
        "alignment": asdict(alignment),
        "errors": [asdict(e) for e in diagnose(predicted, truth, alignment)],
    }


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 5) if values else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--detector", type=Path, required=True)
    parser.add_argument("--crossings", type=Path, default=None)
    parser.add_argument("--orientation-results", type=Path, default=None)
    parser.add_argument("--images", type=Path, default=ROOT / "data/image2net/images")
    parser.add_argument("--golden", type=Path, default=ROOT / "data/image2net/golden")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/m2/pipeline")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--no-plain-crossings", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0, help="GED search, s")
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, (os.cpu_count() or 2) - 2),
        help="scoring processes (default: all cores but two)",
    )
    parser.add_argument("--limit", type=int, default=None, help="first N circuits")
    args = parser.parse_args(argv)

    kw = dict(conf=args.conf, imgsz=args.imgsz, device=args.device)
    pipeline = Pipeline(
        detect=YoloDetector(args.detector, **kw),
        crossings=YoloCrossings(args.crossings, **kw) if args.crossings else None,
        classify=(
            YoloClassifiers.from_results(args.orientation_results, args.device)
            if args.orientation_results
            else None
        ),
        detect_plain_crossings=not args.no_plain_crossings,
    )

    images = sorted(
        p
        for p in args.images.glob("*.png")
        if (args.golden / f"{p.stem}.json").exists()
    )[: args.limit]
    run_dir = args.output_dir / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (run_dir / "predictions").mkdir(parents=True)

    records, jobs = {}, []
    for i, path in enumerate(images, start=1):
        result = pipeline(Image.open(path))
        records[path.stem] = {
            "image": path.name,
            "netlist": result.netlist.model_dump(mode="json"),
            "components": result.component_features,
            "rules": result.rules.counts(),
            "crossings": [asdict(c) for c in result.crossings],
            "crossings_cut": result.extraction.crossings_cut,
            "line_width": result.extraction.line_width,
        }
        jobs.append(
            (
                path.stem,
                result.netlist.model_dump_json(),
                str(args.golden / f"{path.stem}.json"),
                args.timeout,
            )
        )
        print(f"[{i}/{len(images)}] {path.name}: inferred", flush=True)

    rows = []
    with ProcessPoolExecutor(args.workers) as pool:
        for row in pool.map(score, jobs):
            rows.append(row)
            record = records[row["circuit_id"]] | {"score": row}
            (run_dir / "predictions" / f"{row['circuit_id']}.json").write_text(
                json.dumps(record, indent=1), encoding="utf-8"
            )
            print(f"{row['circuit_id']}: ned={row['ned']}", flush=True)

    metrics = {
        "circuits": len(rows),
        "macro_ned": mean([r["ned"] for r in rows]),
        "ned_exact_fraction": mean([float(r["ned_exact"]) for r in rows]),
        "graph_isomorphism_accuracy": mean(
            [float(r["graph_isomorphism"]) for r in rows]
        ),
        "macro_connection_precision": mean([r["connection_precision"] for r in rows]),
        "macro_connection_recall": mean([r["connection_recall"] for r in rows]),
        "component_count_match": mean(
            [float(r["components_true"] == r["components_pred"]) for r in rows]
        ),
        "per_circuit": [
            {k: v for k, v in r.items() if k not in ("alignment", "errors")}
            for r in rows
        ],
    }
    commit = code_commit()
    weights = {"detector": args.detector, "crossings": args.crossings}
    if args.orientation_results:
        weights |= {
            f"orientation_{t}": p
            for t, p in YoloClassifiers.weights_in(args.orientation_results).items()
        }
    config = {
        "weights": {
            k: {"path": str(p), "sha256": sha256(p)} for k, p in weights.items() if p
        },
        "images": str(args.images),
        "circuits": len(images),
        "conf": args.conf,
        "imgsz": args.imgsz,
        "device": args.device,
        "detect_plain_crossings": not args.no_plain_crossings,
        "ged_timeout_s": args.timeout,
        "code_commit": commit,
        "python": sys.version.split()[0],
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), "utf-8")
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), "utf-8")
    if str(commit).endswith("-dirty"):
        (run_dir / "uncommitted.diff").write_text(uncommitted_diff(), "utf-8")
    print(
        json.dumps({k: v for k, v in metrics.items() if k != "per_circuit"}, indent=2)
    )
    print("wrote", run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
