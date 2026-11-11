"""Train and evaluate the M2 YOLO models (detect, obb, classify).

One entry point for every model so each run is recorded the same way:
``results/m2/<name>/<run_id>/`` gets the Ultralytics training output,
``metrics.json`` (held-out val metrics, per class) and ``config.json``
(arguments, seed, code commit, library versions, device).

    python -m vca.training detect --name detector_i2n \\
        --data data/m2/detector_i2n/data.yaml
    python -m vca.training obb --name crossing --data data/m2/crossing/data.yaml
    python -m vca.training classify --name orientation_mos \\
        --data data/m2/orientation/mos

On Kaggle/Colab the repository is not cloned (it is private); the code ships
inside the dataset zip with its commit in ``CODE_COMMIT``.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_MODELS = {
    "detect": "yolo26s.pt",
    "obb": "yolo26s-obb.pt",
    "classify": "yolo26n-cls.pt",
}
DEFAULT_IMGSZ = {"detect": 1024, "obb": 1024, "classify": 128}


def code_commit() -> str | None:
    env = os.environ.get("VCA_CODE_COMMIT")
    if env:
        return env
    marker = Path(__file__).resolve().parents[2] / "CODE_COMMIT"
    if marker.exists():
        return marker.read_text(encoding="utf-8").strip()
    try:
        commit = _git("rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        return None
    return commit + ("-dirty" if uncommitted_diff() else "")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).parent,
    ).stdout


def uncommitted_diff() -> str:
    """Diff of src/ against HEAD, including new files; '' when clean or no git."""
    try:
        root = Path(_git("rev-parse", "--show-toplevel").strip())
        diff = _git("diff", "HEAD", "--", str(root / "src"))
        untracked = _git(
            "ls-files",
            "--others",
            "--exclude-standard",
            "--full-name",
            "--",
            str(root / "src"),
        ).split()
    except (OSError, subprocess.CalledProcessError):
        return ""
    for rel in untracked:
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        diff += f"\n--- new file: {rel}\n{text}"
    return diff


def _device_name(device: str) -> str:
    import torch

    if device != "cpu" and torch.cuda.is_available():
        index = int(str(device).split(",")[0]) if str(device).isdigit() else 0
        return torch.cuda.get_device_name(index)
    return platform.processor() or platform.machine()


def _floats(values) -> list[float]:
    return [round(float(v), 5) for v in values]


def detection_metrics(metrics, names: dict[int, str]) -> dict:
    box = metrics.box
    per_class = {}
    for i, cls in enumerate(box.ap_class_index):
        per_class[names[int(cls)]] = {
            "precision": round(float(box.p[i]), 5),
            "recall": round(float(box.r[i]), 5),
            "ap50": round(float(box.ap50[i]), 5),
            "ap50_95": round(float(box.ap[i]), 5),
        }
    return {
        "map50": round(float(box.map50), 5),
        "map50_95": round(float(box.map), 5),
        "precision": round(float(box.mp), 5),
        "recall": round(float(box.mr), 5),
        "per_class": per_class,
        "classes_without_val_instances": sorted(set(names.values()) - set(per_class)),
    }


def classification_metrics(metrics, names: dict[int, str]) -> dict:
    matrix = metrics.confusion_matrix.matrix  # rows: predicted, cols: true
    n = len(names)
    per_class = {}
    for i in range(n):
        true_total = float(matrix[:n, i].sum())
        pred_total = float(matrix[i, :n].sum())
        hit = float(matrix[i, i])
        per_class[names[i]] = {
            "support": int(true_total),
            "recall": round(hit / true_total, 5) if true_total else None,
            "precision": round(hit / pred_total, 5) if pred_total else None,
        }
    return {
        "top1": round(float(metrics.top1), 5),
        "per_class": per_class,
        "confusion_matrix_pred_by_true": [_floats(r[:n]) for r in matrix[:n]],
    }


def train(args: argparse.Namespace) -> Path:
    import ultralytics
    from ultralytics import YOLO

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    project = Path(args.output_dir).resolve() / args.name
    model = YOLO(args.model or DEFAULT_MODELS[args.task])
    imgsz = args.imgsz or DEFAULT_IMGSZ[args.task]

    model.train(
        data=str(Path(args.data).resolve()),
        epochs=args.epochs,
        imgsz=imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        cache=args.cache or False,
        seed=args.seed,
        deterministic=True,
        patience=args.patience,
        project=str(project),
        name=run_id,
        exist_ok=False,
        plots=True,
        verbose=True,
    )
    run_dir = project / run_id
    best = run_dir / "weights" / "best.pt"

    # Re-evaluate the best checkpoint on the held-out val split.
    evaluator = YOLO(str(best))
    val_kwargs = dict(
        data=str(Path(args.data).resolve()),
        imgsz=imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=str(run_dir),
        name="val",
        plots=True,
    )
    if args.task != "classify":
        val_kwargs["split"] = "val"
    metrics = evaluator.val(**val_kwargs)
    names = evaluator.names
    summary = (
        classification_metrics(metrics, names)
        if args.task == "classify"
        else detection_metrics(metrics, names)
    )

    import torch

    config = {
        "task": args.task,
        "name": args.name,
        "run_id": run_id,
        "data": args.data,
        "model": args.model or DEFAULT_MODELS[args.task],
        "epochs": args.epochs,
        "imgsz": imgsz,
        "batch": args.batch,
        "patience": args.patience,
        "cache": args.cache,
        "seed": args.seed,
        "device": args.device,
        "device_name": _device_name(str(args.device)),
        "code_commit": code_commit(),
        "python": sys.version.split()[0],
        "ultralytics": ultralytics.__version__,
        "torch": torch.__version__,
        "best_weights": best.relative_to(Path(args.output_dir).resolve()).as_posix(),
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    if str(config["code_commit"]).endswith("-dirty"):
        (run_dir / "uncommitted.diff").write_text(uncommitted_diff(), encoding="utf-8")
    (run_dir / "metrics.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    brief = {k: v for k, v in summary.items() if not isinstance(v, (dict, list))}
    print(json.dumps(brief, indent=2))
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train an M2 YOLO model.")
    parser.add_argument("task", choices=["detect", "obb", "classify"])
    parser.add_argument(
        "--data", required=True, help="data.yaml, or a folder for classify"
    )
    parser.add_argument("--name", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--patience", type=int, default=30)
    parser.add_argument("--device", default="0", help="'0', '1', '0,1' or 'cpu'")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--cache", choices=["ram", "disk"], default=None, help="cache decoded images"
    )
    parser.add_argument("--output-dir", default="results/m2")
    args = parser.parse_args(argv)
    train(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
