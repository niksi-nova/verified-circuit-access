"""Train and evaluate the component verifier on a pipeline run.

    uv run python scripts/train_verifier.py results/m2/pipeline/<run>

Each predicted component is one example, labelled wrong when the GED
alignment puts it in any error. Evaluation is 5-fold cross-validation by
circuit (out-of-fold probabilities); the saved model is then fitted on all
circuits. Writes ``results/m2/verifier/<run_id>/``: ``config.json``,
``metrics.json`` (verifier vs. the rule flags alone), ``oof.json`` and
``model.joblib``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vca.training import code_commit, uncommitted_diff  # noqa: E402
from vca.verify.model import (  # noqa: E402
    cross_validate,
    evaluate,
    feature_names,
    featurize,
    fit,
    flag_scores,
    vocabulary,
)


def load(run: Path) -> list[dict]:
    rows = []
    for path in sorted((run / "predictions").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        wrong = {
            e["pred_component"]
            for e in record["score"]["errors"]
            if e.get("pred_component")
        }
        nets = record["netlist"]["nets"]
        circuit = {
            "rules": record["rules"],
            "components": len(record["components"]),
            "single_terminal_nets": sum(len(n["endpoints"]) == 1 for n in nets),
            "crossings_cut": record["crossings_cut"],
        }
        for c in record["components"]:
            rows.append(
                c
                | {
                    "circuit_id": path.stem,
                    "circuit": circuit,
                    "wrong": c["component_id"] in wrong,
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run", type=Path, help="results/m2/pipeline/<run>")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/m2/verifier")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args(argv)

    rows = load(args.run)
    vocab = vocabulary(rows)
    x = featurize(rows, vocab)
    y = np.array([r["wrong"] for r in rows], dtype=int)
    groups = np.array([r["circuit_id"] for r in rows])

    p = cross_validate(x, y, groups, args.folds, args.seed)
    any_rule = np.array([bool(r["rules"]) for r in rows])
    strong = np.array(
        [bool(set(r["rules"]) - {"extra_contacts", "floating_terminal"}) for r in rows]
    )
    metrics = {
        "verifier_oof": evaluate(y, p, args.threshold),
        "rules_any": flag_scores(y, any_rule),
        "rules_strong": flag_scores(y, strong),
        "circuits": len(set(groups)),
    }
    order = np.argsort(-p)
    metrics["verifier_oof"]["precision_at_recall"] = {
        str(target): float(
            y[order][
                : int(np.searchsorted(np.cumsum(y[order]), target * y.sum())) + 1
            ].mean()
        )
        for target in (0.5, 0.8)
    }

    run_dir = args.output_dir / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True)
    model = fit(x, y, groups, args.seed)
    joblib.dump(
        {"model": model, "vocab": vocab, "features": feature_names(vocab)},
        run_dir / "model.joblib",
    )
    commit = code_commit()
    config = {
        "pipeline_run": str(args.run),
        "folds": args.folds,
        "seed": args.seed,
        "threshold": args.threshold,
        "features": feature_names(vocab),
        "code_commit": commit,
        "python": sys.version.split()[0],
    }
    (run_dir / "config.json").write_text(json.dumps(config, indent=2), "utf-8")
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), "utf-8")
    (run_dir / "oof.json").write_text(
        json.dumps(
            [
                {
                    "circuit_id": r["circuit_id"],
                    "component_id": r["component_id"],
                    "wrong": int(t),
                    "p_wrong": round(float(q), 4),
                }
                for r, t, q in zip(rows, y, p, strict=True)
            ]
        ),
        "utf-8",
    )
    if str(commit).endswith("-dirty"):
        (run_dir / "uncommitted.diff").write_text(uncommitted_diff(), "utf-8")
    print(json.dumps(metrics, indent=2))
    print("wrote", run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
