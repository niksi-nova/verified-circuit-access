"""Evaluation framework for circuit netlist extraction.

For every image with a golden netlist: get a prediction (from the VLM, or a
previously saved one), align it to the ground truth, and derive NED,
graph-isomorphism, component and connection precision/recall, and a typed
list of element errors from that single alignment. Raw predictions, an
overlay for each failure, metrics, config and an input checksum manifest are
written under ``output_dir/<run_id>/`` and ``output_dir/results/``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from vca.baseline.errors import ApprovalRequiredError, VLMExhaustedError
from vca.baseline.interface import VLMInterface
from vca.baseline.overlay import render_overlay
from vca.baseline.results import ResultsStore
from vca.data.image2net import load_labelme_json, load_validation_netlist
from vca.metrics.alignment import (
    align,
    component_scores,
    connection_scores,
    diagnose,
    ned_from_alignment,
)
from vca.metrics.summary import MetricsSummary, PerPairMetrics
from vca.schemas.annotation import AnnotationRecord
from vca.schemas.netlist import Netlist

LOGGER = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

OK_COLOR = (0, 160, 0)
ERROR_COLOR = (220, 0, 0)


class CircuitResult(BaseModel):
    circuit_id: str
    failure_categories: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


class EvaluationResult(BaseModel):
    circuits: list[CircuitResult]
    metrics: MetricsSummary
    error_counts: dict[str, int] = Field(default_factory=dict)
    dataset_name: str
    provider_name: str
    model_identifier: str
    random_seed: int
    git_commit_sha: str


class ManifestEntry(BaseModel):
    file_path: str
    sha256: str


class EvaluationManifest(BaseModel):
    run_id: str
    entries: list[ManifestEntry]


def _check_approvals(*, data_approved: bool, vlm_approved: bool) -> None:
    """Require separate approval for dataset access and VLM usage."""
    missing = []
    if not data_approved:
        missing.append("dataset usage (--data-approved)")
    if not vlm_approved:
        missing.append("VLM usage (--vlm-approved)")

    if missing:
        message = (
            "Evaluation cannot start. Explicit approval is required for: "
            + ", ".join(missing)
        )
        print(message)
        raise ApprovalRequiredError(message)


def _discover_images(image_dir: Path) -> list[Path]:
    if not image_dir.is_dir():
        raise FileNotFoundError(f"Image directory not found: {image_dir}")
    return sorted(
        path
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _load_ground_truth(netlist_path: Path) -> Netlist:
    netlists = load_validation_netlist(netlist_path)
    if len(netlists) != 1:
        raise ValueError(
            f"{netlist_path}: expected exactly one netlist, found {len(netlists)}."
        )
    return netlists[0]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _predict(
    vlm: VLMInterface,
    image_path: Path,
    prediction_path: Path,
    reuse_predictions: bool,
) -> Netlist:
    """Return a saved prediction when allowed, else call the VLM and save."""
    if reuse_predictions and prediction_path.is_file():
        return Netlist.model_validate_json(
            prediction_path.read_text(encoding="utf-8")
        )

    prediction = vlm.predict(image_path)
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    prediction_path.write_text(prediction.model_dump_json(indent=2), encoding="utf-8")
    return prediction


def _render_failure_overlay(
    image_path: Path,
    output_path: Path,
    prediction: Netlist,
    errors: list[dict[str, Any]],
    ground_truth_annotations: list[AnnotationRecord],
    ned: float | None,
) -> None:
    flagged = {e["pred_component"] for e in errors if e.get("pred_component")}
    boxes = [
        (
            component.bbox,
            f"{component.id} {component.canonical_category}",
            ERROR_COLOR if component.id in flagged else OK_COLOR,
        )
        for component in prediction.components
        if component.bbox is not None
    ]

    ned_text = "n/a" if ned is None else f"{ned:.3f}"
    legend = [
        f"{image_path.stem}: NED {ned_text}. Boxes are VLM-estimated "
        "locations (red = involved in an error).",
    ]
    for error in errors:
        who = " / ".join(
            part
            for part in (
                f"gt {error['gt_component']}" if error.get("gt_component") else "",
                f"pred {error['pred_component']}"
                if error.get("pred_component")
                else "",
            )
            if part
        )
        detail = f" ({error['detail']})" if error.get("detail") else ""
        legend.append(f"- {error['kind']}: {error['category']} [{who}]{detail}")

    render_overlay(
        image_path=image_path,
        ground_truth_annotations=ground_truth_annotations,
        predicted_annotations=[],
        output_path=output_path,
        legend_lines=legend,
        labelled_boxes=boxes,
        legend_panel=True,
    )


def _mean(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    return sum(valid) / len(valid) if valid else None


def run_evaluation(
    image_dir: Path,
    netlist_dir: Path,
    vlm: VLMInterface,
    output_dir: Path,
    *,
    data_approved: bool = False,
    vlm_approved: bool = False,
    random_seed: int = 42,
    ned_timeout: float = 30.0,
    limit: int | None = None,
    predictions_dir: Path | None = None,
    extra_config: dict[str, Any] | None = None,
) -> EvaluationResult:
    """Run evaluation on circuit images and their ground-truth netlists."""
    # Require both approvals before accessing input directories.
    _check_approvals(data_approved=data_approved, vlm_approved=vlm_approved)

    images = _discover_images(image_dir)
    if limit is not None:
        images = images[:limit]

    run_id = datetime.now(UTC).strftime("evaluation_%Y%m%dT%H%M%SZ")
    run_dir = output_dir / run_id
    # Reusing an earlier run's predictions re-scores without new VLM calls.
    reuse_predictions = predictions_dir is not None
    predictions_dir = predictions_dir or run_dir / "predictions"

    circuit_results: list[CircuitResult] = []
    manifest_entries: list[ManifestEntry] = []
    per_pair: list[PerPairMetrics] = []
    error_counts: Counter[str] = Counter()

    for index, image_path in enumerate(images, start=1):
        circuit_id = image_path.stem
        netlist_path = netlist_dir / f"{circuit_id}.json"

        manifest_entries.append(
            ManifestEntry(file_path=str(image_path), sha256=_sha256_file(image_path))
        )

        if not netlist_path.is_file():
            LOGGER.warning(
                "Skipping %s: ground-truth netlist not found at %s",
                circuit_id,
                netlist_path,
            )
            circuit_results.append(
                CircuitResult(
                    circuit_id=circuit_id,
                    skipped=True,
                    skip_reason=f"Missing netlist: {netlist_path}",
                )
            )
            continue

        manifest_entries.append(
            ManifestEntry(
                file_path=str(netlist_path), sha256=_sha256_file(netlist_path)
            )
        )
        ground_truth = _load_ground_truth(netlist_path)

        annotation_path = netlist_dir / f"{circuit_id}_labelme.json"
        ground_truth_annotations: list[AnnotationRecord] = []
        if annotation_path.is_file():
            manifest_entries.append(
                ManifestEntry(
                    file_path=str(annotation_path),
                    sha256=_sha256_file(annotation_path),
                )
            )
            ground_truth_annotations = load_labelme_json(annotation_path)

        # Only exhausted retries count as a circuit-level prediction failure;
        # configuration and unexpected errors propagate.
        try:
            prediction = _predict(
                vlm,
                image_path,
                predictions_dir / f"{circuit_id}.json",
                reuse_predictions,
            )
        except VLMExhaustedError as error:
            LOGGER.error("Prediction failed for %s: %s", circuit_id, error)
            circuit_results.append(
                CircuitResult(
                    circuit_id=circuit_id,
                    failure_categories=["prediction_failed"],
                    skip_reason="VLM prediction failed after retries",
                )
            )
            error_counts["prediction_failed"] += 1
            continue

        alignment = align(prediction, ground_truth, timeout=ned_timeout)
        ned = ned_from_alignment(alignment, ground_truth)
        component_p, component_r = component_scores(
            prediction, ground_truth, alignment
        )
        connection_p, connection_r = connection_scores(
            prediction, ground_truth, alignment
        )
        errors = [asdict(e) for e in diagnose(prediction, ground_truth, alignment)]

        if alignment.isomorphic:
            categories = ["correct"]
        elif alignment.ged is None:
            categories = ["alignment_timeout"]
        else:
            categories = sorted({e["kind"] for e in errors}) or ["other_mismatch"]

        error_counts.update(e["kind"] for e in errors)
        circuit_results.append(
            CircuitResult(
                circuit_id=circuit_id,
                failure_categories=categories,
                errors=errors,
            )
        )
        per_pair.append(
            PerPairMetrics(
                circuit_id=circuit_id,
                ned_exact=alignment.exact,
                ned=ned,
                graph_isomorphism=alignment.isomorphic,
                component_precision=component_p,
                component_recall=component_r,
                connection_precision=connection_p,
                connection_recall=connection_r,
            )
        )

        if not alignment.isomorphic:
            _render_failure_overlay(
                image_path,
                run_dir / "overlays" / f"{circuit_id}_overlay.png",
                prediction,
                errors,
                ground_truth_annotations,
                ned,
            )

        LOGGER.info(
            "[%d/%d] %s: %s (NED %s)",
            index,
            len(images),
            circuit_id,
            ",".join(categories),
            "n/a" if ned is None else f"{ned:.3f}",
        )

    metrics = MetricsSummary(
        per_pair=per_pair,
        macro_ned=_mean([item.ned for item in per_pair]),
        macro_graph_isomorphism_accuracy=_mean(
            [float(item.graph_isomorphism) for item in per_pair]
        ),
        macro_component_precision=_mean([i.component_precision for i in per_pair]),
        macro_component_recall=_mean([i.component_recall for i in per_pair]),
        macro_connection_precision=_mean([i.connection_precision for i in per_pair]),
        macro_connection_recall=_mean([i.connection_recall for i in per_pair]),
    )

    results_store = ResultsStore()
    git_sha = results_store._get_git_sha()
    if git_sha is None:
        LOGGER.warning("Could not determine Git commit SHA; recording it as unknown.")
        git_sha = "unknown"

    provider = vlm.provider
    provider_name = type(provider).__name__
    raw_model_identifier = getattr(provider, "model_identifier", None)
    model_identifier = (
        raw_model_identifier if isinstance(raw_model_identifier, str) else "unknown"
    )

    evaluation_result = EvaluationResult(
        circuits=circuit_results,
        metrics=metrics,
        error_counts=dict(sorted(error_counts.items())),
        dataset_name="Image2Net",
        provider_name=provider_name,
        model_identifier=model_identifier,
        random_seed=random_seed,
        git_commit_sha=git_sha,
    )

    config: dict[str, Any] = {
        "dataset_name": "Image2Net",
        "image_dir": str(image_dir),
        "netlist_dir": str(netlist_dir),
        "circuits_requested": len(images),
        "provider_name": provider_name,
        "model_identifier": model_identifier,
        "random_seed": random_seed,
        "ned_timeout_s": ned_timeout,
        "predictions_dir": str(predictions_dir),
        "reused_predictions": reuse_predictions,
        "git_commit_sha": git_sha,
    }
    config.update(extra_config or {})

    metrics_path = results_store.save(
        evaluation_result,
        run_id=run_id,
        config=config,
        output_dir=output_dir / "results",
    )

    call_log = getattr(provider, "call_log", None)
    if isinstance(call_log, list):
        (metrics_path.parent / f"{run_id}_calls.json").write_text(
            json.dumps(call_log, indent=2), encoding="utf-8"
        )

    manifest = EvaluationManifest(run_id=run_id, entries=manifest_entries)
    (metrics_path.parent / f"{run_id}_manifest.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )

    return evaluation_result
