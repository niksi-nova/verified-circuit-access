"""Loads the M2 models once and runs the real pipeline + explanation
layer on one image. No mocking, no synthetic output: every call here
either runs the real pipeline or raises.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from vca.explain.build import build_circuit_record, text_layers
from vca.netting.orient import YoloClassifiers
from vca.outputs.braille import braille_output
from vca.outputs.tactile import tactile_output
from vca.pipeline import STAGES, Pipeline, YoloCrossings, YoloDetector

ALL_STAGES: tuple[str, ...] = (*STAGES, "verifier", "explanation")

PIPELINE_RUN_DEFAULT = "results/m2/pipeline/20261111T171400Z"
VERIFIER_RUN_DEFAULT = "results/m2/verifier/20261111T171904Z"


class EngineStartupError(RuntimeError):
    """A required weights file or run directory is missing."""


@dataclass
class EngineInfo:
    pipeline_run: str
    verifier_run: str
    detector_sha256: str
    crossings_sha256: str
    device: str


def _require(path: Path, what: str) -> Path:
    if not path.exists():
        raise EngineStartupError(f"Missing {what}: {path}")
    return path


class Engine:
    """Stateful, loaded once at process startup. Not thread-safe to call
    concurrently — the API's job queue guarantees one analysis at a
    time."""

    def __init__(
        self,
        root: Path,
        pipeline_run: str = PIPELINE_RUN_DEFAULT,
        verifier_run: str = VERIFIER_RUN_DEFAULT,
        device: str = "cpu",
    ):
        self.root = Path(root)
        self.pipeline_run_dir = self.root / pipeline_run
        self.verifier_run_dir = self.root / verifier_run
        self.device = device

        config_path = _require(
            self.pipeline_run_dir / "config.json", "pipeline run config.json"
        )
        config = json.loads(config_path.read_text(encoding="utf-8"))
        weights = config["weights"]

        def weight_path(entry: dict) -> Path:
            # Config paths were recorded on Windows; make them portable.
            relative = entry["path"].replace("\\", "/")
            return _require(self.root / relative, f"weight file {relative}")

        self.detector_path = weight_path(weights["detector"])
        self.crossings_path = weight_path(weights["crossings"])
        self.detector_sha256 = weights["detector"]["sha256"]
        self.crossings_sha256 = weights["crossings"]["sha256"]

        _require(self.verifier_run_dir / "model.joblib", "verifier model.joblib")
        _require(self.verifier_run_dir / "oof.json", "verifier oof.json")

        kw = dict(
            conf=config.get("conf", 0.25),
            imgsz=config.get("imgsz", 1024),
            device=device,
        )
        orientation = {
            name.removeprefix("orientation_"): weight_path(entry)
            for name, entry in weights.items()
            if name.startswith("orientation_")
        }
        self.model_runs = {
            name: Path(entry["path"].replace("\\", "/")).parents[1].name
            for name, entry in weights.items()
        }
        os.environ["YOLO_AUTOINSTALL"] = "false"
        os.environ["YOLO_OFFLINE"] = "true"
        self.pipeline = Pipeline(
            detect=YoloDetector(self.detector_path, **kw),
            crossings=YoloCrossings(self.crossings_path, **kw),
            classify=YoloClassifiers(orientation, device),
            detect_plain_crossings=config.get("detect_plain_crossings", True),
        )

        self.pipeline_run = pipeline_run
        self.verifier_run = verifier_run
        self.manifest_path = self.root / "data/image2net/manifest.json"
        self.images_dir = self.root / "data/image2net/images"

    def info(self) -> EngineInfo:
        return EngineInfo(
            pipeline_run=self.pipeline_run,
            verifier_run=self.verifier_run,
            detector_sha256=self.detector_sha256,
            crossings_sha256=self.crossings_sha256,
            device=self.device,
        )

    def analyze(
        self,
        image: Image.Image,
        sha256: str,
        extension: str,
        on_stage=None,
    ) -> dict:
        from vca.api.verifier import resolve_verifier_probs
        from vca.training import code_commit

        notify = on_stage or (lambda _stage: None)

        result = self.pipeline(image, on_stage=notify)

        prediction = {
            "image": f"input.{extension}",
            "netlist": result.netlist.model_dump(mode="json"),
            "components": result.component_features,
            "rules": result.rules.counts(),
            "crossings_cut": result.extraction.crossings_cut,
        }

        if not prediction["components"]:
            raise NoComponentsFoundError(
                "No components were found in this image. This tool works best "
                "on a clean, single schematic diagram."
            )

        notify("verifier")
        probs, verifier_source_label = resolve_verifier_probs(
            sha256, prediction, self.verifier_run_dir, self.manifest_path
        )

        notify("explanation")
        from vca.explain.build import verifier_note

        verifier_metrics = json.loads(
            (self.verifier_run_dir / "metrics.json").read_text(encoding="utf-8")
        )
        verifier_config = json.loads(
            (self.verifier_run_dir / "config.json").read_text(encoding="utf-8")
        )
        note = verifier_note(verifier_metrics, verifier_config["threshold"])

        record = build_circuit_record(
            prediction,
            probs,
            note,
            image.size,
            circuit_id=sha256[:12],
            score=None,
        )
        try:
            record["braille"] = braille_output(text_layers(record)["all"])
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            logging.getLogger(__name__).exception("Braille translation failed")
        tactile_features = [
            feature | {"mirrored": report.layout.mirrored}
            for feature, report in zip(
                result.component_features, result.extraction.components, strict=True
            )
        ]
        try:
            record["tactile"] = tactile_output(
                record["netlist"], image.size, tactile_features
            )
        except ValueError:
            logging.getLogger(__name__).exception("Raised diagram generation failed")
        record.pop("evaluation", None)
        record["image_url"] = f"/api/runs/{sha256}/image"
        record["verifier_source"] = verifier_source_label
        record["code_commit"] = code_commit()

        warnings = []
        if len(prediction["components"]) < 3:
            warnings.append(
                "Very few components were found; this tool works best on clean "
                "schematic images."
            )
        record["warnings"] = warnings

        return record


class NoComponentsFoundError(RuntimeError):
    pass
