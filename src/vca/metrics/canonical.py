"""Canonical heterogeneous graph shared by every netlist metric.

Mirrors the graph used by Image2Net's official NED script
(``validation/utils_ged.py`` in LAD021/ci2n_datasets):

- One node per component, labelled with its canonical category.
- One node per net. Net names are ignored.
- One edge per component terminal, labelled with the terminal name.
- Two-terminal passives (resistor, capacitor, inductor, switch) are
  orientation-free: the official script gives both of their edges the same
  type, so we label both terminals ``"pin"``. Every other device keeps its
  terminal names, so swapped drain/source, collector/emitter, diode or
  source polarity is a real topology difference.
"""

import networkx as nx

from vca.schemas.netlist import Netlist

SYMMETRIC_CATEGORIES: frozenset[str] = frozenset(
    {"resistor", "capacitor", "inductor", "switch"}
)
SYMMETRIC_TERMINAL = "pin"


def canonical_terminal(category: str, terminal_name: str) -> str:
    """Return the terminal label used for graph comparison."""
    if category in SYMMETRIC_CATEGORIES:
        return SYMMETRIC_TERMINAL
    return terminal_name


def component_node(component_id: str) -> str:
    return f"component:{component_id}"


def net_node(net_name: str) -> str:
    return f"net:{net_name}"


def build_graph(netlist: Netlist) -> nx.MultiGraph:
    """Build the canonical component-net multigraph for a netlist."""
    graph = nx.MultiGraph()
    categories = {}

    for component in netlist.components:
        categories[component.id] = component.canonical_category
        graph.add_node(
            component_node(component.id),
            node_type="component",
            category=component.canonical_category,
        )

    for net in netlist.nets:
        graph.add_node(net_node(net.name), node_type="net", category="")

        for endpoint in net.endpoints:
            graph.add_edge(
                component_node(endpoint.component_id),
                net_node(net.name),
                terminal=canonical_terminal(
                    categories[endpoint.component_id],
                    endpoint.terminal_name,
                ),
            )

    return graph


def ned_denominator(ground_truth: Netlist) -> int:
    """Devices + nets + ports of the ground truth (Image2Net normalisation)."""
    return (
        len(ground_truth.components)
        + len(ground_truth.nets)
        + sum(len(net.endpoints) for net in ground_truth.nets)
    )
