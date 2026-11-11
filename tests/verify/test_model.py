import numpy as np
from sklearn.metrics import roc_auc_score

from vca.verify.model import (
    cross_validate,
    evaluate,
    expected_calibration_error,
    feature_names,
    featurize,
    vocabulary,
)


def _rows(n=400, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        distance = float(rng.uniform(0, 1))
        rows.append(
            {
                "circuit_id": f"c{i // 10}",
                "category": "nmos" if i % 2 else "resistor",
                "orientation_source": "predicted",
                "mirror_source": None,
                "detector_score": float(rng.uniform(0.3, 1)),
                "max_terminal_distance": distance,
                "orientation_p": None,
                "rules": ["floating_terminal"] if distance > 0.7 else [],
                "circuit": {"components": 10, "rules": {"no_ground": 1}},
                # wrong mostly when the terminals sit far from the wires
                "wrong": bool(rng.uniform() < 0.1 + 0.8 * distance),
            }
        )
    return rows


def test_featurize_shapes_and_missing_values():
    rows = _rows(20)
    vocab = vocabulary(rows)
    x = featurize(rows, vocab)
    names = feature_names(vocab)
    assert x.shape == (20, len(names))
    assert (x[:, names.index("orientation_p")] == -1).all()
    assert (x[:, names.index("circuit_rule:no_ground")] == 1).all()
    assert x[:, names.index("category=nmos")].sum() == 10


def test_cross_validated_verifier_learns_the_signal():
    rows = _rows(1200)
    x = featurize(rows, vocabulary(rows))
    y = np.array([r["wrong"] for r in rows], dtype=int)
    groups = np.array([r["circuit_id"] for r in rows])
    p = cross_validate(x, y, groups, folds=4)
    metrics = evaluate(y, p)
    # Within reach of the best possible ranking (the true signal itself).
    best = roc_auc_score(y, [r["max_terminal_distance"] for r in rows])
    assert metrics["auroc"] > best - 0.06
    assert metrics["ece"] < 0.1


def test_ece_of_perfect_calibration_is_zero():
    y = np.array([0, 1, 0, 1])
    assert expected_calibration_error(y, np.full(4, 0.5)) == 0.0
    assert expected_calibration_error(y, y.astype(float)) == 0.0
