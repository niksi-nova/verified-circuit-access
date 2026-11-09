"""Component and connection precision/recall metrics.

Component matching uses Hungarian optimal assignment, constrained by
canonical category and the provisional centre-distance threshold.

Connection matching compares complete net endpoint sets. Net names are
ignored; component IDs are mapped through circuit graph isomorphism.
"""

from math import hypot

import networkx as nx
from scipy.optimize import linear_sum_assignment

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


def _build_incidence_graph(netlist: Netlist) -> nx.Graph:
    """Build a bipartite graph for component-to-net incidence."""
    graph = nx.Graph()

    for component in netlist.components:
        graph.add_node(
            f"component:{component.id}",
            node_type="component",
            canonical_category=component.canonical_category,
        )

    for net in netlist.nets:
        graph.add_node(
            f"net:{net.name}",
            node_type="net",
        )

        for endpoint in net.endpoints:
            graph.add_edge(
                f"component:{endpoint.component_id}",
                f"net:{net.name}",
                terminal_name=endpoint.terminal_name,
            )

    return graph


def _component_mapping(
    predicted: Netlist,
    ground_truth: Netlist,
) -> dict[str, str] | None:
    """Return component-ID mapping from a graph-isomorphism bijection."""
    pred_graph = _build_incidence_graph(predicted)
    gt_graph = _build_incidence_graph(ground_truth)

    node_match = nx.algorithms.isomorphism.categorical_node_match(
        ["node_type", "canonical_category"],
        ["", ""],
    )
    edge_match = nx.algorithms.isomorphism.categorical_edge_match(
        "terminal_name",
        "",
    )

    matcher = nx.algorithms.isomorphism.GraphMatcher(
        pred_graph,
        gt_graph,
        node_match=node_match,
        edge_match=edge_match,
    )

    if not matcher.is_isomorphic():
        return None

    mapping = matcher.mapping

    return {
        pred_node.removeprefix("component:"):
        gt_node.removeprefix("component:")
        for pred_node, gt_node in mapping.items()
        if pred_node.startswith("component:")
    }


def _net_endpoint_sets(
    netlist: Netlist,
    component_mapping: dict[str, str] | None = None,
) -> set[frozenset[tuple[str, str]]]:
    """Return each net as a set of (component ID, terminal) endpoints."""
    result = set()

    for net in netlist.nets:
        endpoints = set()

        for endpoint in net.endpoints:
            component_id = endpoint.component_id

            if component_mapping is not None:
                component_id = component_mapping.get(component_id, component_id)

            endpoints.add((component_id, endpoint.terminal_name))

        result.add(frozenset(endpoints))

    return result


def connection_precision(
    predicted: Netlist,
    ground_truth: Netlist,
) -> float | None:
    """Matched predicted nets / predicted net count."""
    if not predicted.nets:
        return None

    mapping = _component_mapping(predicted, ground_truth)

    if mapping is None:
        return 0.0

    predicted_nets = _net_endpoint_sets(predicted, mapping)
    ground_truth_nets = _net_endpoint_sets(ground_truth)

    return len(predicted_nets & ground_truth_nets) / len(predicted.nets)


def connection_recall(
    predicted: Netlist,
    ground_truth: Netlist,
) -> float | None:
    """Matched ground-truth nets / ground-truth net count."""
    if not ground_truth.nets:
        return None

    mapping = _component_mapping(predicted, ground_truth)

    if mapping is None:
        return 0.0

    predicted_nets = _net_endpoint_sets(predicted, mapping)
    ground_truth_nets = _net_endpoint_sets(ground_truth)

    return len(predicted_nets & ground_truth_nets) / len(ground_truth.nets)