"""Build demo/data/status.json by reading saved metrics files only.

No number here is computed from anything but a metrics.json/config.json
already written by a real run. Median NED is the only derived value, and
it's a plain median over the per-circuit NEDs already saved in the
pipeline run's metrics.json. A missing file means "not available" — never
a fallback or a guess.
"""

from __future__ import annotations

import json
from pathlib import Path

NOT_AVAILABLE = "not available"


def _read_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _latest_run(model_dir: Path) -> Path | None:
    if not model_dir.exists():
        return None
    runs = sorted(p for p in model_dir.iterdir() if p.is_dir() and p.name[0].isdigit())
    return runs[-1] if runs else None


def _median(values: list[float]) -> float:
    values = sorted(values)
    n = len(values)
    mid = n // 2
    if n % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def _pipeline_status(pipeline_run: Path) -> dict | str:
    metrics = _read_json(pipeline_run / "metrics.json")
    if not metrics:
        return NOT_AVAILABLE
    neds = [row["ned"] for row in metrics["per_circuit"]]
    return {
        "run": pipeline_run.name,
        "circuits": metrics["circuits"],
        "mean_ned": metrics["macro_ned"],
        "median_ned": round(_median(neds), 5),
        "exact_fraction": metrics["ned_exact_fraction"],
        "graph_isomorphism_accuracy": metrics["graph_isomorphism_accuracy"],
        "connection_precision": metrics["macro_connection_precision"],
        "connection_recall": metrics["macro_connection_recall"],
    }


def _verifier_status(verifier_run: Path) -> dict | str:
    metrics = _read_json(verifier_run / "metrics.json")
    config = _read_json(verifier_run / "config.json")
    if not metrics or not config:
        return NOT_AVAILABLE
    threshold = config["threshold"]
    flag = metrics["verifier_oof"].get(f"flag@{threshold}")
    if flag is None:
        return NOT_AVAILABLE
    return {
        "run": verifier_run.name,
        "components": metrics["verifier_oof"]["components"],
        "error_rate": metrics["verifier_oof"]["error_rate"],
        "auroc": metrics["verifier_oof"]["auroc"],
        "ece": metrics["verifier_oof"]["ece"],
        "brier": metrics["verifier_oof"]["brier"],
        "flag_threshold": threshold,
        "flag_precision": flag["precision"],
        "flag_recall": flag["recall"],
    }


def _detection_status(results_m2_dir: Path, name: str) -> dict | str:
    run = _latest_run(results_m2_dir / name)
    metrics = _read_json(run / "metrics.json") if run else None
    if not metrics:
        return NOT_AVAILABLE
    return {
        "run": run.name,
        "map50": metrics["map50"],
        "map50_95": metrics["map50_95"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
    }


def _orientation_status(results_m2_dir: Path) -> dict | str:
    tasks = {}
    for task_dir in sorted(results_m2_dir.glob("orientation_*")):
        if not task_dir.is_dir():
            continue
        run = _latest_run(task_dir)
        metrics = _read_json(run / "metrics.json") if run else None
        tasks[task_dir.name] = (
            {"run": run.name, "top1": metrics["top1"]} if metrics else NOT_AVAILABLE
        )
    return tasks or NOT_AVAILABLE


def build_status(pipeline_run: Path, verifier_run: Path, note: str | None) -> dict:
    results_m2_dir = pipeline_run.resolve().parent.parent
    detector = _detection_status(results_m2_dir, "detector_i2n_cghd")
    if detector == NOT_AVAILABLE:
        detector = _detection_status(results_m2_dir, "detector_i2n")
    return {
        "pipeline": _pipeline_status(pipeline_run),
        "verifier": _verifier_status(verifier_run),
        "detector": detector,
        "crossing": _detection_status(results_m2_dir, "crossing"),
        "orientation": _orientation_status(results_m2_dir),
        "verifier_note": note or NOT_AVAILABLE,
    }
