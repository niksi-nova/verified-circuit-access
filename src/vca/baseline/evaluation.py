
"""Evaluation framework for circuit netlist extraction."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from vca.baseline.errors import (
    ApprovalRequiredError,
    VLMExhaustedError,
)
from vca.baseline.interface import VLMInterface
from vca.baseline.overlay import render_overlay
from vca.baseline.results import ResultsStore
from vca.data.image2net import load_labelme_json, load_validation_netlist
from vca.metrics.graph_iso import are_isomorphic
from vca.metrics.summary import MetricsSummary, PerPairMetrics
from vca.schemas.annotation import AnnotationRecord
from vca.schemas.netlist import Netlist

LOGGER = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class CircuitResult(BaseModel):
    circuit_id: str
    failure_categories: list[str] = Field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


class EvaluationResult(BaseModel):
    circuits: list[CircuitResult]
    metrics: MetricsSummary
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


def _check_approvals(
    *,
    data_approved: bool,
    vlm_approved: bool,
) -> None:
    """Require separate approval for dataset access and VLM usage."""
    if not data_approved or not vlm_approved:
        missing = []

        if not data_approved:
            missing.append("dataset usage (--data-approved)")

        if not vlm_approved:
            missing.append("VLM usage (--vlm-approved)")

        message = (
            "Evaluation cannot start. Explicit approval is required for: "
            + ", ".join(missing)
        )

        print(message)
        raise ApprovalRequiredError(message)


def _discover_images(image_dir: Path) -> list[Path]:
    """Find supported circuit images in a directory."""
    if not image_dir.is_dir():
        raise FileNotFoundError(f"Image directory not found: {image_dir}")

    return sorted(
        path
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _load_ground_truth(netlist_path: Path) -> Netlist:
    """Load exactly one ground-truth netlist from a JSON file."""
    netlists = load_validation_netlist(netlist_path)

    if len(netlists) != 1:
        raise ValueError(
            f"{netlist_path}: expected exactly one netlist, "
            f"found {len(netlists)}."
        )

    return netlists[0]


def _load_ground_truth_annotations(
    annotation_path: Path,
) -> list[AnnotationRecord]:
    """Load ground-truth spatial annotations."""
    return load_labelme_json(annotation_path)


def _sha256_file(path: Path) -> str:
    """Calculate the SHA-256 checksum of a file."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            digest.update(chunk)

    return digest.hexdigest()


def run_evaluation(
    image_dir: Path,
    netlist_dir: Path,
    vlm: VLMInterface,
    output_dir: Path,
    *,
    data_approved: bool = False,
    vlm_approved: bool = False,
    random_seed: int = 42,
) -> EvaluationResult:
    """Run evaluation on circuit images and their ground-truth netlists."""

    # Require both approvals before accessing input directories.
    _check_approvals(
        data_approved=data_approved,
        vlm_approved=vlm_approved,
    )

    images = _discover_images(image_dir)

    circuit_results: list[CircuitResult] = []
    manifest_entries: list[ManifestEntry] = []
    per_pair_metrics: list[PerPairMetrics] = []

    for image_path in images:
        circuit_id = image_path.stem
        netlist_path = netlist_dir / f"{circuit_id}.json"

        # Record image checksum.
        manifest_entries.append(
            ManifestEntry(
                file_path=str(image_path),
                sha256=_sha256_file(image_path),
            )
        )

        # Skip circuits without ground-truth netlists.
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

        # Record netlist checksum.
        manifest_entries.append(
            ManifestEntry(
                file_path=str(netlist_path),
                sha256=_sha256_file(netlist_path),
            )
        )

        ground_truth = _load_ground_truth(netlist_path)

        # Load optional ground-truth spatial annotations.
        annotation_path = (
            netlist_dir / f"{circuit_id}_labelme.json"
        )
        ground_truth_annotations: list[AnnotationRecord] = []

        if annotation_path.is_file():
            manifest_entries.append(
                ManifestEntry(
                    file_path=str(annotation_path),
                    sha256=_sha256_file(annotation_path),
                )
            )

            ground_truth_annotations = (
                _load_ground_truth_annotations(annotation_path)
            )

        # Obtain VLM prediction. Only exhausted retries are treated as
        # a circuit-level prediction failure. Configuration and unexpected
        # errors must propagate instead of being silently hidden.
        try:
            prediction = vlm.predict(image_path)
        except VLMExhaustedError:
            LOGGER.exception(
                "VLM prediction exhausted retries for circuit %s",
                circuit_id,
            )

            circuit_results.append(
                CircuitResult(
                    circuit_id=circuit_id,
                    failure_categories=["not_evaluated"],
                    skip_reason="VLM prediction failed after retries",
                )
            )
            continue

        # Compare predicted and ground-truth circuit graphs.
        graph_match = are_isomorphic(prediction, ground_truth)

        if graph_match:
            failure_categories = ["correct"]
        else:
            # A netlist-only mismatch cannot establish missed components,
            # wrong polarity, or a specific physical localization failure.
            failure_categories = ["not_evaluated"]

        circuit_results.append(
            CircuitResult(
                circuit_id=circuit_id,
                failure_categories=failure_categories,
            )
        )

        # NED and spatial metrics remain unavailable in the current M1
        # implementation. Connection metrics are also withheld because
        # the current component correspondence requires full graph
        # isomorphism and therefore cannot independently measure topology.
        per_pair_metrics.append(
            PerPairMetrics(
                ned=None,
                graph_isomorphism=graph_match,
                component_precision=None,
                component_recall=None,
                connection_precision=None,
                connection_recall=None,
            )
        )

        # The VLM currently returns no predicted bounding boxes.
        # Draw only ground-truth boxes and explain the localization limitation.
        if ground_truth_annotations:
            predicted_types = sorted(
                {
                    component.canonical_category
                    for component in prediction.components
                }
            )

            legend_lines = [
                "VLM predictions (localization unavailable):",
                *[f"- {category}" for category in predicted_types],
            ]

            overlay_path = (
                output_dir
                / "overlays"
                / f"{circuit_id}_overlay.png"
            )

            render_overlay(
                image_path=image_path,
                ground_truth_annotations=ground_truth_annotations,
                predicted_annotations=[],
                output_path=overlay_path,
                legend_lines=legend_lines,
            )

    # Calculate macro graph-isomorphism accuracy.
    graph_values = [
        float(item.graph_isomorphism)
        for item in per_pair_metrics
        if item.graph_isomorphism is not None
    ]

    macro_graph_accuracy = (
        sum(graph_values) / len(graph_values)
        if graph_values
        else None
    )

    metrics = MetricsSummary(
        per_pair=per_pair_metrics,
        macro_ned=None,
        macro_graph_isomorphism_accuracy=macro_graph_accuracy,
        macro_component_precision=None,
        macro_component_recall=None,
        macro_connection_precision=None,
        macro_connection_recall=None,
    )

    # Identify the evaluation run.
    run_id = datetime.now(UTC).strftime(
        "evaluation_%Y%m%dT%H%M%SZ"
    )

    results_store = ResultsStore()
    git_sha = results_store._get_git_sha()

    if git_sha is None:
        LOGGER.warning(
            "Could not determine Git commit SHA; recording it as unknown."
        )
        git_sha = "unknown"

    provider = vlm.provider
    provider_name = type(provider).__name__

    raw_model_identifier = getattr(
        provider,
        "model_identifier",
        None,
    )

    model_identifier = (
        raw_model_identifier
        if isinstance(raw_model_identifier, str)
        else "unknown"
    )

    evaluation_result = EvaluationResult(
        circuits=circuit_results,
        metrics=metrics,
        dataset_name="Image2Net",
        provider_name=provider_name,
        model_identifier=model_identifier,
        random_seed=random_seed,
        git_commit_sha=git_sha,
    )

    # Save evaluation result and configuration.
    # Use the returned path so the manifest follows ResultsStore's
    # collision-handling directory.
    metrics_path = results_store.save(
        evaluation_result,
        run_id=run_id,
        config={
            "dataset_name": "Image2Net",
            "provider_name": provider_name,
            "model_identifier": model_identifier,
            "random_seed": random_seed,
            "git_commit_sha": git_sha,
        },
        output_dir=output_dir / "results",
    )

    # Save input-file manifest alongside the metrics and configuration.
    manifest = EvaluationManifest(
        run_id=run_id,
        entries=manifest_entries,
    )

    manifest_dir = metrics_path.parent
    manifest_path = manifest_dir / f"{run_id}_manifest.json"

    manifest_path.write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )

    return evaluation_result
