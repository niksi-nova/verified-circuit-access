"""Slow integration test: the real engine against a real weights set and
a real validation image. Skipped if the weights aren't present (this
matters on a machine that only has the `dev` extra installed).
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PIPELINE_RUN = ROOT / "results/m2/pipeline/20261111T171400Z"
VERIFIER_RUN = ROOT / "results/m2/verifier/20261111T171904Z"

pytest.importorskip("ultralytics")
pytest.importorskip("torch")

if not (PIPELINE_RUN / "config.json").exists():
    pytest.skip("pipeline run weights not present", allow_module_level=True)


@pytest.mark.slow
def test_engine_matches_saved_prediction_for_a_known_validation_image():
    import hashlib

    from PIL import Image

    from vca.api.engine import Engine

    engine = Engine(ROOT)
    image_path = ROOT / "data/image2net/images/015.png"
    sha256 = hashlib.sha256(image_path.read_bytes()).hexdigest()
    with Image.open(image_path) as raw:
        image = raw.convert("RGB")
    stages_seen = []
    record = engine.analyze(image, sha256, "png", on_stage=stages_seen.append)

    # Every documented stage boundary fired, in order.
    assert stages_seen == [
        "read_image",
        "detect_components",
        "detect_crossings",
        "orientation",
        "netting",
        "rule_checks",
        "verifier",
        "explanation",
    ]

    import json

    saved = json.loads(
        (PIPELINE_RUN / "predictions" / "015.json").read_text(encoding="utf-8")
    )
    live_components = {(c["id"], c["category"]) for c in record["components"]}
    saved_components = {
        (c["id"], c["canonical_category"]) for c in saved["netlist"]["components"]
    }
    assert live_components == saved_components

    live_nets = {(n["id"], tuple(sorted(n["components"]))) for n in record["nets"]}
    saved_nets = {
        (n["name"], tuple(sorted({e["component_id"] for e in n["endpoints"]})))
        for n in saved["netlist"]["nets"]
    }
    assert live_nets == saved_nets

    assert "evaluation" not in record
    assert "cross-validated" in record["verifier_source"]
