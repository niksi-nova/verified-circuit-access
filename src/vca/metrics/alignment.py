"""Align a predicted netlist to ground truth and explain the differences.

The alignment is the node mapping from the graph-edit path that realises the
(best found) graph edit distance on the canonical graph, so NED, connection
precision/recall and the per-element error list all come from one
consistent correspondence. Exact GED is exponential; when the search hits
``timeout`` the result is the cheaper of the best path found so far and an
assignment-based path (``vca.metrics.assignment_ged``): an upper bound, with
``Alignment.exact`` False.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

import networkx as nx
from networkx.algorithms import isomorphism

from vca.metrics.assignment_ged import heuristic_mapping
from vca.metrics.canonical import (
    SYMMETRIC_CATEGORIES,
    build_graph,
    canonical_terminal,
    ned_denominator,
)
from vca.schemas.netlist import Netlist

ErrorKind = Literal[
    "missed_component",
    "extra_component",
    "wrong_component_type",
    "wrong_polarity",
    "wrong_connection",
]


@dataclass(frozen=True)
class ElementError:
    """One component-level disagreement between prediction and truth."""

    kind: ErrorKind
    category: str
    gt_component: str | None = None
    pred_component: str | None = None
    detail: str = ""


@dataclass
class Alignment:
    """Node correspondence between a predicted and a ground-truth graph."""

    ged: float | None
    exact: bool
    isomorphic: bool
    component_map: dict[str, str] = field(default_factory=dict)
    net_map: dict[str, str] = field(default_factory=dict)


def _node_subst_cost(first: dict, second: dict) -> float:
    return float(
        first["node_type"] != second["node_type"]
        or first["category"] != second["category"]
    )


def _edge_subst_cost(first: dict, second: dict) -> float:
    return float(first["terminal"] != second["terminal"])


def _unit(_: dict) -> float:
    return 1.0


def _split_mapping(
    pairs: list[tuple[str | None, str | None]],
) -> tuple[dict[str, str], dict[str, str]]:
    component_map: dict[str, str] = {}
    net_map: dict[str, str] = {}

    for pred_node, gt_node in pairs:
        if pred_node is None or gt_node is None:
            continue
        pred_kind, _, pred_name = pred_node.partition(":")
        gt_kind, _, gt_name = gt_node.partition(":")
        if pred_kind != gt_kind:
            # GED may substitute a net for a component at unit cost; that
            # is not a meaningful correspondence, so treat both as unmatched.
            continue
        if pred_kind == "component":
            component_map[pred_name] = gt_name
        else:
            net_map[pred_name] = gt_name

    return component_map, net_map


def align(
    predicted: Netlist,
    ground_truth: Netlist,
    timeout: float = 30.0,
) -> Alignment:
    """Return the best alignment found within ``timeout`` seconds."""
    pred_graph = build_graph(predicted)
    gt_graph = build_graph(ground_truth)

    matcher = isomorphism.MultiGraphMatcher(
        pred_graph,
        gt_graph,
        node_match=isomorphism.categorical_node_match(
            ["node_type", "category"], ["", ""]
        ),
        edge_match=isomorphism.categorical_multiedge_match("terminal", ""),
    )
    if matcher.is_isomorphic():
        component_map, net_map = _split_mapping(list(matcher.mapping.items()))
        return Alignment(
            ged=0.0,
            exact=True,
            isomorphic=True,
            component_map=component_map,
            net_map=net_map,
        )

    best_pairs: list[tuple[str | None, str | None]] | None = None
    best_cost: float | None = None
    started = time.monotonic()

    for node_path, _edge_path, cost in nx.optimize_edit_paths(
        pred_graph,
        gt_graph,
        node_subst_cost=_node_subst_cost,
        node_del_cost=_unit,
        node_ins_cost=_unit,
        edge_subst_cost=_edge_subst_cost,
        edge_del_cost=_unit,
        edge_ins_cost=_unit,
        strictly_decreasing=True,
        timeout=timeout,
    ):
        best_pairs, best_cost = node_path, cost

    exact = time.monotonic() - started < timeout

    if not exact:
        # The search stopped early; its best path can be far from optimal.
        # An assignment-based mapping is often much closer: keep the lower.
        mapping, cost = heuristic_mapping(pred_graph, gt_graph)
        if best_cost is None or cost < best_cost:
            used = {v for v in mapping.values() if v is not None}
            best_pairs = list(mapping.items()) + [
                (None, v) for v in gt_graph if v not in used
            ]
            best_cost = cost

    if best_pairs is None:
        return Alignment(ged=None, exact=False, isomorphic=False)

    component_map, net_map = _split_mapping(best_pairs)
    return Alignment(
        ged=float(best_cost),
        exact=exact,
        isomorphic=False,
        component_map=component_map,
        net_map=net_map,
    )


def ned_from_alignment(
    alignment: Alignment,
    ground_truth: Netlist,
) -> float | None:
    """Normalised GED: GED / (devices + nets + ports of ground truth)."""
    denominator = ned_denominator(ground_truth)
    if alignment.ged is None or denominator == 0:
        return None
    return alignment.ged / denominator


def _terminal_nets(netlist: Netlist) -> dict[str, dict[str, str | None]]:
    """Map component id -> terminal name -> net name (None if floating)."""
    result: dict[str, dict[str, str | None]] = {
        component.id: {terminal.name: None for terminal in component.terminals}
        for component in netlist.components
    }
    for net in netlist.nets:
        for endpoint in net.endpoints:
            result[endpoint.component_id][endpoint.terminal_name] = net.name
    return result


def diagnose(
    predicted: Netlist,
    ground_truth: Netlist,
    alignment: Alignment,
) -> list[ElementError]:
    """List per-component errors implied by an alignment."""
    if alignment.isomorphic:
        return []

    pred_categories = {c.id: c.canonical_category for c in predicted.components}
    pred_terminals = _terminal_nets(predicted)
    gt_terminals = _terminal_nets(ground_truth)
    gt_to_pred = {gt: pred for pred, gt in alignment.component_map.items()}

    errors: list[ElementError] = []

    for gt_component in ground_truth.components:
        category = gt_component.canonical_category
        pred_id = gt_to_pred.get(gt_component.id)

        if pred_id is None:
            errors.append(
                ElementError(
                    kind="missed_component",
                    category=category,
                    gt_component=gt_component.id,
                )
            )
            continue

        if pred_categories[pred_id] != category:
            errors.append(
                ElementError(
                    kind="wrong_component_type",
                    category=category,
                    gt_component=gt_component.id,
                    pred_component=pred_id,
                    detail=f"predicted {pred_categories[pred_id]}",
                )
            )
            continue

        expected = gt_terminals[gt_component.id]
        observed = {
            terminal: (alignment.net_map.get(net) if net is not None else None)
            for terminal, net in pred_terminals[pred_id].items()
        }

        if category in SYMMETRIC_CATEGORIES:
            if Counter(observed.values()) != Counter(expected.values()):
                errors.append(
                    ElementError(
                        kind="wrong_connection",
                        category=category,
                        gt_component=gt_component.id,
                        pred_component=pred_id,
                        detail="terminal nets differ",
                    )
                )
            continue

        if observed == expected:
            continue

        wrong_terminals = sorted(
            t
            for t in set(expected) | set(observed)
            if expected.get(t) != observed.get(t)
        )
        same_terminals = set(observed) == set(expected)
        same_nets = Counter(observed.values()) == Counter(expected.values())

        errors.append(
            ElementError(
                kind=(
                    "wrong_polarity"
                    if same_terminals and same_nets
                    else "wrong_connection"
                ),
                category=category,
                gt_component=gt_component.id,
                pred_component=pred_id,
                detail="terminals: " + ", ".join(wrong_terminals),
            )
        )

    matched_pred = set(alignment.component_map)
    for component in predicted.components:
        if component.id not in matched_pred:
            errors.append(
                ElementError(
                    kind="extra_component",
                    category=component.canonical_category,
                    pred_component=component.id,
                )
            )

    return errors


def _endpoint_sets(
    netlist: Netlist,
    component_map: dict[str, str] | None,
) -> list[frozenset[tuple[str, str]]]:
    categories = {c.id: c.canonical_category for c in netlist.components}
    result = []
    for net in netlist.nets:
        endpoints = set()
        for endpoint in net.endpoints:
            component_id = endpoint.component_id
            if component_map is not None:
                # Unmatched predicted components can never match a GT net.
                component_id = component_map.get(
                    component_id, f"__unmatched__{component_id}"
                )
            endpoints.add(
                (
                    component_id,
                    canonical_terminal(
                        categories[endpoint.component_id],
                        endpoint.terminal_name,
                    ),
                )
            )
        result.append(frozenset(endpoints))
    return result


def connection_scores(
    predicted: Netlist,
    ground_truth: Netlist,
    alignment: Alignment,
) -> tuple[float | None, float | None]:
    """Net-level (precision, recall): a net matches if its endpoint set does."""
    pred_sets = _endpoint_sets(predicted, alignment.component_map)
    gt_sets = Counter(_endpoint_sets(ground_truth, None))

    matched = 0
    for endpoint_set in pred_sets:
        if gt_sets[endpoint_set] > 0:
            gt_sets[endpoint_set] -= 1
            matched += 1

    precision = matched / len(predicted.nets) if predicted.nets else None
    recall = matched / len(ground_truth.nets) if ground_truth.nets else None
    return precision, recall


def component_scores(
    predicted: Netlist,
    ground_truth: Netlist,
    alignment: Alignment,
) -> tuple[float | None, float | None]:
    """Netlist-level component (precision, recall): aligned with same type."""
    pred_categories = {c.id: c.canonical_category for c in predicted.components}
    gt_categories = {c.id: c.canonical_category for c in ground_truth.components}

    matched = sum(
        pred_categories[pred] == gt_categories[gt]
        for pred, gt in alignment.component_map.items()
    )

    precision = matched / len(predicted.components) if predicted.components else None
    recall = matched / len(ground_truth.components) if ground_truth.components else None
    return precision, recall
