
"""Normalized Graph Edit Distance for canonical circuit netlists."""

import networkx as nx

from vca.schemas.netlist import Netlist


def _build_ged_graph(netlist: Netlist) -> nx.MultiGraph:
    """Build a canonical component-net incidence graph."""
    graph = nx.MultiGraph()

    for component in netlist.components:
        graph.add_node(
            f"component:{component.id}",
            node_type="component",
            category=component.canonical_category,
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
                terminal=endpoint.terminal_name,
            )

    return graph


def _node_subst_cost(first: dict, second: dict) -> float:
    """Unit cost for incompatible node substitutions."""
    return float(
        first["node_type"] != second["node_type"]
        or (
            first["node_type"] == "component"
            and first["category"] != second["category"]
        )
    )


def _edge_subst_cost(first: dict, second: dict) -> float:
    """Unit cost for different terminal labels."""
    return float(first["terminal"] != second["terminal"])


def compute_ned(
    predicted: Netlist,
    ground_truth: Netlist,
    timeout: float = 30.0,
) -> float | None:
    """Return normalized GED, or None if undefined or timed out."""
    denominator = (
        len(ground_truth.components)
        + len(ground_truth.nets)
        + sum(len(net.endpoints) for net in ground_truth.nets)
    )

    if denominator == 0:
        return None

    predicted_graph = _build_ged_graph(predicted)
    ground_truth_graph = _build_ged_graph(ground_truth)

    ged = nx.graph_edit_distance(
        predicted_graph,
        ground_truth_graph,
        node_subst_cost=_node_subst_cost,
        edge_subst_cost=_edge_subst_cost,
        node_del_cost=lambda _: 1.0,
        node_ins_cost=lambda _: 1.0,
        edge_del_cost=lambda _: 1.0,
        edge_ins_cost=lambda _: 1.0,
        timeout=timeout,
    )

    if ged is None:
        return None

    return ged / denominator
