"""Picks the verifier probability source for a freshly analysed image.

If the upload's sha256 matches one of the 122 Image2Net validation
images, the out-of-fold probability already recorded for that circuit is
honest to reuse (it was produced by a model that never trained on that
circuit). Anything else is scored with the verifier's final fitted
model — the best available estimate for a genuinely new drawing.
"""

from __future__ import annotations

import json
from pathlib import Path

from vca.explain.verifier_source import load_oof, score_with_model


def _manifest_sha_to_circuit(manifest_path: Path) -> dict[str, str]:
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        entry["sha256"]: entry["id"]
        for entry in manifest
        if entry.get("type") == "image"
    }


def resolve_verifier_probs(
    image_sha256: str,
    prediction: dict,
    verifier_run: Path,
    manifest_path: Path,
) -> tuple[dict[str, float], str]:
    sha_to_circuit = _manifest_sha_to_circuit(manifest_path)
    circuit_id = sha_to_circuit.get(image_sha256)

    if circuit_id is not None:
        oof = load_oof(verifier_run)
        probs = {
            component_id: p
            for (cid, component_id), p in oof.items()
            if cid == circuit_id
        }
        wanted = {c["component_id"] for c in prediction["components"]}
        if wanted and wanted <= set(probs):
            return probs, "cross-validated (this image is in our evaluation set)"
        # Detection differs from the stored run (component ids won't
        # line up) even though the image is byte-identical — fall
        # through to a fresh model score rather than mixing the two.

    return score_with_model(prediction, verifier_run), "model"
