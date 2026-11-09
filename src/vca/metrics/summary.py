
"""Aggregate circuit-level metrics into a summary."""

from pydantic import BaseModel

from vca.metrics.graph_iso import are_isomorphic
from vca.metrics.ned import compute_ned
from vca.metrics.precision_recall import (
    component_precision,
    component_recall,
    connection_precision,
    connection_recall,
)
from vca.schemas.annotation import AnnotationRecord
from vca.schemas.netlist import Netlist


class PerPairMetrics(BaseModel):
    """Metrics calculated for a single circuit pair."""

    ned: float | None
    graph_isomorphism: bool | None
    component_precision: float | None
    component_recall: float | None
    connection_precision: float | None
    connection_recall: float | None


class MetricsSummary(BaseModel):
    """Per-circuit metrics and macro averages."""

    per_pair: list[PerPairMetrics]
    macro_ned: float | None
    macro_graph_isomorphism_accuracy: float | None
    macro_component_precision: float | None
    macro_component_recall: float | None
    macro_connection_precision: float | None
    macro_connection_recall: float | None


def _mean(values: list[float | None]) -> float | None:
    """Calculate the mean while excluding None values."""
    valid_values = [value for value in values if value is not None]

    if not valid_values:
        return None

    return sum(valid_values) / len(valid_values)


def compute_metrics(
    pairs: list[tuple[Netlist, Netlist]],
    annotation_pairs: list[
        tuple[list[AnnotationRecord], list[AnnotationRecord]]
    ],
) -> MetricsSummary:
    """Compute per-pair metrics and macro averages.

    Netlist pairs contain (predicted, ground_truth).
    Annotation pairs contain (predicted, ground_truth).
    Pair order must be consistent between both lists.
    """
    if len(pairs) != len(annotation_pairs):
        raise ValueError(
            "pairs and annotation_pairs must contain the same number "
            "of circuits in corresponding order."
        )

    per_pair: list[PerPairMetrics] = []

    for (
        (predicted_netlist, ground_truth_netlist),
        (predicted_annotations, ground_truth_annotations),
    ) in zip(pairs, annotation_pairs, strict=True):
        per_pair.append(
            PerPairMetrics(
                ned=compute_ned(predicted_netlist, ground_truth_netlist),
                graph_isomorphism=are_isomorphic(
                    predicted_netlist, ground_truth_netlist
                ),
                component_precision=component_precision(
                    predicted_annotations, ground_truth_annotations
                ),
                component_recall=component_recall(
                    predicted_annotations, ground_truth_annotations
                ),
                connection_precision=connection_precision(
                    predicted_netlist, ground_truth_netlist
                ),
                connection_recall=connection_recall(
                    predicted_netlist, ground_truth_netlist
                ),
            )
        )

    return MetricsSummary(
        per_pair=per_pair,
        macro_ned=_mean([item.ned for item in per_pair]),
        macro_graph_isomorphism_accuracy=_mean(
            [
                float(item.graph_isomorphism)
                if item.graph_isomorphism is not None
                else None
                for item in per_pair
            ]
        ),
        macro_component_precision=_mean(
            [item.component_precision for item in per_pair]
        ),
        macro_component_recall=_mean(
            [item.component_recall for item in per_pair]
        ),
        macro_connection_precision=_mean(
            [item.connection_precision for item in per_pair]
        ),
        macro_connection_recall=_mean(
            [item.connection_recall for item in per_pair]
        ),
    )
