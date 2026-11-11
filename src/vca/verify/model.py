"""Verifier: a calibrated probability that a predicted component is wrong.

Trained on the pipeline's per-component evidence (``component_features``)
and labelled by the GED alignment (a component is wrong when the alignment
puts it in any error). Gradient boosting ranks; isotonic regression, fitted
on held-out circuits, turns scores into probabilities. Splits are always by
circuit: components of one drawing share its style and its mistakes.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

from vca.verify.rules import CIRCUIT_RULES, COMPONENT_RULES

NUMERIC = (
    "detector_score",
    "box_area",
    "box_aspect",
    "orientation_p",
    "mirrored_p",
    "terminals",
    "unconnected_terminals",
    "extra_contacts",
    "max_terminal_distance",
    "mean_terminal_distance",
    "min_net_fanout",
)
CATEGORICAL = ("category", "orientation_source", "mirror_source")
CIRCUIT = ("components", "single_terminal_nets", "crossings_cut")
# Every numeric feature is >= 0. Not NaN: an all-missing column (one
# fold without mirror scores) breaks the booster's binning.
MISSING = -1.0


def feature_names(vocab: dict[str, list[str]]) -> list[str]:
    return (
        list(NUMERIC)
        + [f"rule:{r}" for r in COMPONENT_RULES]
        + [f"circuit_rule:{r}" for r in CIRCUIT_RULES]
        + [f"circuit:{c}" for c in CIRCUIT]
        + [f"{k}={v}" for k in CATEGORICAL for v in vocab[k]]
    )


def vocabulary(rows: Iterable[dict]) -> dict[str, list[str]]:
    rows = list(rows)
    return {k: sorted({str(r.get(k)) for r in rows}) for k in CATEGORICAL}


def featurize(rows: list[dict], vocab: dict[str, list[str]]) -> np.ndarray:
    """One row per component; ``row["circuit"]`` holds circuit-level context."""
    out = []
    for r in rows:
        circuit = r.get("circuit", {})
        x = [MISSING if r.get(k) is None else float(r[k]) for k in NUMERIC]
        x += [float(rule in r.get("rules", [])) for rule in COMPONENT_RULES]
        x += [
            float(circuit.get("rules", {}).get(rule, 0) > 0) for rule in CIRCUIT_RULES
        ]
        x += [float(circuit.get(c, 0)) for c in CIRCUIT]
        x += [float(str(r.get(k)) == v) for k in CATEGORICAL for v in vocab[k]]
        out.append(x)
    return np.asarray(out, dtype=float)


def make_model(seed: int = 0, calibration_splits=None) -> CalibratedClassifierCV:
    booster = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=20,
        l2_regularization=1.0,
        random_state=seed,
    )
    return CalibratedClassifierCV(
        booster, method="isotonic", cv=calibration_splits or 5, ensemble=True
    )


def fit(x: np.ndarray, y: np.ndarray, groups: np.ndarray, seed: int = 0):
    """Boosting + isotonic calibration, calibration folds split by circuit."""
    folds = min(5, len(set(groups)))
    splits = list(GroupKFold(folds).split(x, y, groups))
    return make_model(seed, splits).fit(x, y)


def expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    which = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    ece = 0.0
    for b in range(bins):
        mask = which == b
        if mask.any():
            ece += mask.mean() * abs(y[mask].mean() - p[mask].mean())
    return float(ece)


def flag_scores(y: np.ndarray, flagged: np.ndarray) -> dict[str, float]:
    tp = float((flagged & (y == 1)).sum())
    return {
        "flagged": int(flagged.sum()),
        "precision": tp / max(flagged.sum(), 1),
        "recall": tp / max((y == 1).sum(), 1),
    }


def evaluate(y: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict:
    return {
        "components": int(len(y)),
        "error_rate": float(y.mean()),
        "auroc": float(roc_auc_score(y, p)),
        "ece": expected_calibration_error(y, p),
        "brier": float(brier_score_loss(y, p)),
        f"flag@{threshold}": flag_scores(y, p >= threshold),
    }


def cross_validate(
    x: np.ndarray, y: np.ndarray, groups: np.ndarray, folds: int = 5, seed: int = 0
) -> np.ndarray:
    """Out-of-fold P(wrong) for every component, outer folds by circuit."""
    p = np.zeros(len(y))
    for train, test in GroupKFold(folds).split(x, y, groups):
        p[test] = fit(x[train], y[train], groups[train], seed).predict_proba(x[test])[
            :, 1
        ]
    return p
