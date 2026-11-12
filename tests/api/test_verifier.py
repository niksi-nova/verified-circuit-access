"""Test-only: picking the cross-validated vs. model verifier source."""

from __future__ import annotations

import json

from vca.api.verifier import resolve_verifier_probs


def _make_verifier_run(tmp_path, oof_rows):
    run = tmp_path / "verifier"
    run.mkdir()
    (run / "oof.json").write_text(json.dumps(oof_rows), encoding="utf-8")
    return run


def _manifest(tmp_path, entries):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_matching_sha256_uses_cross_validated_oof_probabilities(tmp_path):
    oof = [
        {"circuit_id": "015", "component_id": "C1", "p_wrong": 0.1},
        {"circuit_id": "015", "component_id": "C2", "p_wrong": 0.9},
    ]
    verifier_run = _make_verifier_run(tmp_path, oof)
    manifest = _manifest(
        tmp_path,
        [{"id": "015", "type": "image", "sha256": "deadbeef", "path": "x"}],
    )
    prediction = {"components": [{"component_id": "C1"}, {"component_id": "C2"}]}

    probs, source = resolve_verifier_probs(
        "deadbeef", prediction, verifier_run, manifest
    )

    assert probs == {"C1": 0.1, "C2": 0.9}
    assert source == "cross-validated (this image is in our evaluation set)"


def test_unknown_sha256_falls_back_to_model(tmp_path, monkeypatch):
    verifier_run = _make_verifier_run(tmp_path, [])
    manifest = _manifest(tmp_path, [])
    prediction = {"components": [{"component_id": "C1"}]}

    monkeypatch.setattr(
        "vca.api.verifier.score_with_model", lambda pred, run: {"C1": 0.42}
    )

    probs, source = resolve_verifier_probs(
        "unknownsha", prediction, verifier_run, manifest
    )

    assert probs == {"C1": 0.42}
    assert source == "model"


def test_matching_sha256_but_different_components_falls_back_to_model(
    tmp_path, monkeypatch
):
    """The image hash matches a validation circuit, but the fresh
    detection doesn't line up with the stored component ids (e.g. a
    code change since that oof run) — must not silently mix sources."""
    oof = [{"circuit_id": "015", "component_id": "C1", "p_wrong": 0.1}]
    verifier_run = _make_verifier_run(tmp_path, oof)
    manifest = _manifest(
        tmp_path, [{"id": "015", "type": "image", "sha256": "deadbeef", "path": "x"}]
    )
    prediction = {"components": [{"component_id": "C1"}, {"component_id": "C99"}]}

    monkeypatch.setattr(
        "vca.api.verifier.score_with_model", lambda pred, run: {"C1": 0.5, "C99": 0.6}
    )

    probs, source = resolve_verifier_probs(
        "deadbeef", prediction, verifier_run, manifest
    )

    assert source == "model"
    assert probs == {"C1": 0.5, "C99": 0.6}


def test_missing_manifest_file_falls_back_to_model(tmp_path, monkeypatch):
    verifier_run = _make_verifier_run(tmp_path, [])
    manifest = tmp_path / "does-not-exist.json"
    prediction = {"components": [{"component_id": "C1"}]}

    monkeypatch.setattr(
        "vca.api.verifier.score_with_model", lambda pred, run: {"C1": 0.3}
    )

    probs, source = resolve_verifier_probs("anysha", prediction, verifier_run, manifest)

    assert source == "model"
    assert probs == {"C1": 0.3}
