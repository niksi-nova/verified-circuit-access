
"""Graph-isomorphism metrics for circuit netlists.

Canonical graph policy:
- Component IDs and net names are ignored.
- Component nodes are matched by canonical_category.
- Net nodes are matched by node type.
- Component-net edges retain terminal names.
"""

import networkx as nx
from networkx.algorithms import isomorphism

from vca.schemas.netlist import Netlist


def _build_graph(netlist: Netlist) -> nx.Graph:
    """Build a canonical bipartite incidence graph from a netlist."""
    graph = nx.Graph()

    # Component nodes
    for component in netlist.components:
        graph.add_node(
            f"component:{component.id}",
            node_type="component",
            canonical_category=component.canonical_category,
        )

    # Net nodes
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


def are_isomorphic(predicted: Netlist, ground_truth: Netlist) -> bool:
    """Return whether two netlists have equivalent canonical topology."""
    predicted_graph = _build_graph(predicted)
    ground_truth_graph = _build_graph(ground_truth)

    node_match = isomorphism.categorical_node_match(
        ["node_type", "canonical_category"],
        ["", ""],
    )
    edge_match = isomorphism.categorical_edge_match(
        "terminal_name",
        "",
    )

    matcher = isomorphism.GraphMatcher(
        predicted_graph,
        ground_truth_graph,
        node_match=node_match,
        edge_match=edge_match,
    )

    return matcher.is_isomorphic()


def graph_isomorphism_accuracy(
    pairs: list[tuple[Netlist, Netlist]],
) -> float | None:
    """Return the fraction of isomorphic pairs, or None for no pairs."""
    if not pairs:
        return None

    correct = sum(
        are_isomorphic(predicted, ground_truth)
        for predicted, ground_truth in pairs
    )

    return correct / len(pairs)
