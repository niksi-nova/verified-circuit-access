"""Component and connection precision/recall metrics.

Component matching uses Hungarian optimal assignment, constrained by
canonical category and the provisional centre-distance threshold.

Connection matching compares complete net endpoint sets. Net names are
ignored; component IDs are mapped through the graph-edit alignment in
``vca.metrics.alignment``, so a partly wrong prediction still gets credit
for the nets it got right.
"""

from math import hypot

from scipy.optimize import linear_sum_assignment

from vca.metrics.alignment import align, connection_scores
from vca.schemas.annotation import AnnotationRecord
from vca.schemas.netlist import Netlist
from vca.schemas.taxonomy import TAXONOMY

COMPONENT_CENTRE_THRESHOLD_PX: int = 10


def _centre(annotation: AnnotationRecord) -> tuple[float, float]:
    """Return the centre of a COCO-style bounding box."""
    bbox = annotation.bbox
    return (
        bbox.x + bbox.width / 2,
        bbox.y + bbox.height / 2,
    )


def _canonical_category(annotation: AnnotationRecord) -> str:
    """Return the taxonomy's canonical category for an annotation."""
    canonical_name, _ = TAXONOMY.get_canonical(
        annotation.dataset_id,
        annotation.source_label,
    )
    return canonical_name


def _component_match_count(
    predicted: list[AnnotationRecord],
    ground_truth: list[AnnotationRecord],
) -> int:
    """Count optimal one-to-one component matches."""
    if not predicted or not ground_truth:
        return 0

    # Hungarian assignment requires a rectangular cost matrix.
    # Invalid matches receive a large cost and are filtered afterward.
    invalid_cost = (
        COMPONENT_CENTRE_THRESHOLD_PX + 1
    ) * (min(len(predicted), len(ground_truth)) + 1)

    costs: list[list[float]] = []

    for pred in predicted:
        pred_centre = _centre(pred)
        pred_category = _canonical_category(pred)

        row: list[float] = []

        for truth in ground_truth:
            if pred_category != _canonical_category(truth):
                row.append(float(invalid_cost))
                continue

            truth_centre = _centre(truth)
            distance = hypot(
                pred_centre[0] - truth_centre[0],
                pred_centre[1] - truth_centre[1],
            )

            if distance <= COMPONENT_CENTRE_THRESHOLD_PX:
                row.append(distance)
            else:
                row.append(float(invalid_cost))

        costs.append(row)

    rows, columns = linear_sum_assignment(costs)

    return sum(
        costs[row][column] <= COMPONENT_CENTRE_THRESHOLD_PX
        for row, column in zip(rows, columns, strict=True)
    )


def component_precision(
    predicted: list[AnnotationRecord],
    ground_truth: list[AnnotationRecord],
) -> float | None:
    """Matched predictions / predicted component count."""
    if not predicted:
        return None

    return _component_match_count(predicted, ground_truth) / len(predicted)


def component_recall(
    predicted: list[AnnotationRecord],
    ground_truth: list[AnnotationRecord],
) -> float | None:
    """Matched ground-truth components / ground-truth count."""
    if not ground_truth:
        return None

    return _component_match_count(predicted, ground_truth) / len(ground_truth)


def connection_precision(
    predicted: Netlist,
    ground_truth: Netlist,
    timeout: float = 30.0,
) -> float | None:
    """Matched predicted nets / predicted net count (alignment-based)."""
    return connection_scores(
        predicted, ground_truth, align(predicted, ground_truth, timeout)
    )[0]


def connection_recall(
    predicted: Netlist,
    ground_truth: Netlist,
    timeout: float = 30.0,
) -> float | None:
    """Matched ground-truth nets / ground-truth net count (alignment-based)."""
    return connection_scores(
        predicted, ground_truth, align(predicted, ground_truth, timeout)
    )[1]
