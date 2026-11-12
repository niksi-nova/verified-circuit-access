"""Where a component's P(wrong) comes from.

``oof.json`` holds out-of-fold probabilities: honest, because each row's
probability came from a model that never saw that row's circuit during
training. ``model.joblib`` is the final model fit on everything, so a row
it scores saw its own circuit during training — only used as a fallback
for rows ``oof.json`` does not cover (e.g. a different pipeline run).
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib

from vca.verify.model import featurize


def load_oof(verifier_run: Path) -> dict[tuple[str, str], float]:
    rows = json.loads((Path(verifier_run) / "oof.json").read_text(encoding="utf-8"))
    return {(r["circuit_id"], r["component_id"]): r["p_wrong"] for r in rows}


def verifier_row(prediction: dict, component_row: dict) -> dict:
    """One component's feature row, in the shape ``vca.verify.model``
    expects (same construction as ``scripts/train_verifier.py``'s
    ``load``)."""
    nets = prediction["netlist"]["nets"]
    circuit = {
        "rules": prediction["rules"],
        "components": len(prediction["components"]),
        "single_terminal_nets": sum(len(n["endpoints"]) == 1 for n in nets),
        "crossings_cut": prediction["crossings_cut"],
    }
    return component_row | {"circuit": circuit}


def load_model_fallback(verifier_run: Path):
    bundle = joblib.load(Path(verifier_run) / "model.joblib")
    return bundle["model"], bundle["vocab"]


def score_with_model(prediction: dict, verifier_run: Path) -> dict[str, float]:
    """P(wrong) for every component of one fresh prediction, using the
    verifier's final fitted model (not out-of-fold — there is no
    cross-validation fold for a brand new image)."""
    model, vocab = load_model_fallback(verifier_run)
    rows = [verifier_row(prediction, c) for c in prediction["components"]]
    if not rows:
        return {}
    x = featurize(rows, vocab)
    p = model.predict_proba(x)[:, 1]
    return {
        c["component_id"]: float(pi)
        for c, pi in zip(prediction["components"], p, strict=True)
    }


def verifier_probs(
    predictions: dict[str, dict], verifier_run: Path
) -> tuple[dict[str, dict[str, float]], str]:
    """Returns ``{circuit_id: {component_id: p_wrong}}`` and which source
    was used: "oof.json" if it covers every component row in
    ``predictions``, otherwise "oof.json + model.joblib fallback"."""
    oof = load_oof(verifier_run)
    needed = {
        (circuit_id, c["component_id"])
        for circuit_id, prediction in predictions.items()
        for c in prediction["components"]
    }
    missing = needed - set(oof)

    probs: dict[str, dict[str, float]] = {}
    for (circuit_id, component_id), p in oof.items():
        if (circuit_id, component_id) in needed:
            probs.setdefault(circuit_id, {})[component_id] = p

    if not missing:
        return probs, "oof.json"

    model, vocab = load_model_fallback(verifier_run)
    rows_by_key = {}
    for circuit_id, prediction in predictions.items():
        for c in prediction["components"]:
            key = (circuit_id, c["component_id"])
            if key in missing:
                rows_by_key[key] = verifier_row(prediction, c)

    keys = list(rows_by_key)
    x = featurize([rows_by_key[k] for k in keys], vocab)
    fallback_p = model.predict_proba(x)[:, 1]
    for (circuit_id, component_id), p in zip(keys, fallback_p, strict=True):
        probs.setdefault(circuit_id, {})[component_id] = float(p)

    return probs, "oof.json + model.joblib fallback"
