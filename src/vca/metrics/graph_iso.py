"""Graph-isomorphism metrics for circuit netlists.

Canonical graph policy (see ``vca.metrics.canonical``):
- Component IDs and net names are ignored.
- Component nodes are matched by canonical category.
- Component-net edges keep terminal names, except for orientation-free
  two-terminal passives whose terminals are interchangeable.
"""

from networkx.algorithms import isomorphism

from vca.metrics.canonical import build_graph
from vca.schemas.netlist import Netlist


def are_isomorphic(predicted: Netlist, ground_truth: Netlist) -> bool:
    """Return whether two netlists have equivalent canonical topology."""
    matcher = isomorphism.MultiGraphMatcher(
        build_graph(predicted),
        build_graph(ground_truth),
        node_match=isomorphism.categorical_node_match(
            ["node_type", "category"], ["", ""]
        ),
        # Multigraph edges must be compared per edge bundle; the plain
        # categorical_edge_match would compare key dicts and ignore labels.
        edge_match=isomorphism.categorical_multiedge_match("terminal", ""),
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
