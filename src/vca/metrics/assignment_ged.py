"""Assignment-based upper bound on the netlist graph edit distance.

Exact GED (``networkx.optimize_edit_paths``) is exponential. On circuits
with a few dozen components it times out, and the best path it has found
by then can be far from optimal: it explores node pairings in a fixed
order, so more time barely helps. This module builds a good node mapping
directly, then prices it exactly:

1. Components are paired by category and wiring signature (Hungarian).
2. Nets and components are re-paired in turn, each given the other
   (block-coordinate descent on the shared-endpoint count).
3. Pairwise swaps that lower the exact edit cost are applied until none do.

``mapping_cost`` is the cost of the edit path a mapping implies (unit
costs, the same as the exact search), so the result is a valid GED upper
bound and never worse than reporting the search's own path.
"""

from __future__ import annotations

from collections import Counter, defaultdict

import networkx as nx
import numpy as np
from scipy.optimize import linear_sum_assignment

Mapping = dict[str, str | None]  # predicted node -> ground-truth node or None

_FAR = 1e6


def _edges(graph: nx.MultiGraph) -> dict[tuple[str, str], Counter]:
    """(component node, net node) -> Counter of terminal labels."""
    out: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for u, v, data in graph.edges(data=True):
        if graph.nodes[u]["node_type"] != "component":
            u, v = v, u
        out[(u, v)][data["terminal"]] += 1
    return out


def mapping_cost(g1: nx.MultiGraph, g2: nx.MultiGraph, mapping: Mapping) -> float:
    """Unit-cost edit distance of the edit path implied by ``mapping``."""
    cost = 0.0
    used = set()
    for u, target in mapping.items():
        if target is None:
            cost += 1
            continue
        used.add(target)
        a, b = g1.nodes[u], g2.nodes[target]
        cost += float(
            a["node_type"] != b["node_type"] or a["category"] != b["category"]
        )
    cost += sum(1 for v in g2 if v not in used)

    e1, e2 = _edges(g1), _edges(g2)
    moved: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for (c, n), labels in e1.items():
        mc, mn = mapping.get(c), mapping.get(n)
        if mc is None or mn is None:
            cost += sum(labels.values())  # edge deleted with its node
        else:
            moved[
                (mc, mn) if g2.nodes[mc]["node_type"] == "component" else (mn, mc)
            ] += labels
    for key in set(moved) | set(e2):
        a, b = moved.get(key, Counter()), e2.get(key, Counter())
        common = sum((a & b).values())
        cost += max(sum(a.values()), sum(b.values())) - common
    return cost


def _assign(cost: np.ndarray, rows: list[str], cols: list[str]) -> Mapping:
    """Hungarian with a "leave unmatched" option priced at ``_FAR / 2``."""
    if not rows:
        return {}
    if not cols:
        return {r: None for r in rows}
    r, c = linear_sum_assignment(cost)
    mapping: Mapping = {row: None for row in rows}
    for i, j in zip(r, c, strict=True):
        if cost[i, j] < _FAR / 2:
            mapping[rows[i]] = cols[j]
    return mapping


def _nodes(graph: nx.MultiGraph, kind: str) -> list[str]:
    return sorted(n for n, d in graph.nodes(data=True) if d["node_type"] == kind)


def _endpoints(graph: nx.MultiGraph, net: str) -> Counter:
    return Counter((c, d["terminal"]) for _, c, d in graph.edges(net, data=True))


def heuristic_mapping(g1: nx.MultiGraph, g2: nx.MultiGraph) -> tuple[Mapping, float]:
    comps1, comps2 = _nodes(g1, "component"), _nodes(g2, "component")
    nets1, nets2 = _nodes(g1, "net"), _nodes(g2, "net")

    def signature(graph, comp):
        return Counter(
            (d["terminal"], graph.degree(net))
            for _, net, d in graph.edges(comp, data=True)
        )

    sig1 = {c: signature(g1, c) for c in comps1}
    sig2 = {c: signature(g2, c) for c in comps2}
    cost = np.full((len(comps1), len(comps2)), _FAR)
    for i, a in enumerate(comps1):
        for j, b in enumerate(comps2):
            if g1.nodes[a]["category"] == g2.nodes[b]["category"]:
                total = sum((sig1[a] | sig2[b]).values())
                cost[i, j] = 1 - sum((sig1[a] & sig2[b]).values()) / max(total, 1)
            else:
                cost[i, j] = 10.0
    comp_map = _assign(cost, comps1, comps2)

    ends1 = {n: _endpoints(g1, n) for n in nets1}
    ends2 = {n: _endpoints(g2, n) for n in nets2}
    net_map: Mapping = {}
    for _ in range(4):
        cost = np.zeros((len(nets1), len(nets2)))
        for i, a in enumerate(nets1):
            moved = Counter({(comp_map.get(c), t): k for (c, t), k in ends1[a].items()})
            for j, b in enumerate(nets2):
                cost[i, j] = -sum((moved & ends2[b]).values())
        net_map = _assign(cost, nets1, nets2)

        # Components given nets: shared (net, terminal) endpoints.
        inv = {v: k for k, v in net_map.items() if v}
        cost = np.full((len(comps1), len(comps2)), _FAR)
        for i, a in enumerate(comps1):
            mine = Counter(
                (net_map.get(n), d["terminal"]) for _, n, d in g1.edges(a, data=True)
            )
            for j, b in enumerate(comps2):
                theirs = Counter(
                    (n, d["terminal"]) for _, n, d in g2.edges(b, data=True) if n in inv
                )
                shared = sum((mine & theirs).values())
                same = g1.nodes[a]["category"] == g2.nodes[b]["category"]
                cost[i, j] = (0 if same else 10.0) - shared
        new_map = _assign(cost, comps1, comps2)
        if new_map == comp_map:
            break
        comp_map = new_map

    mapping: Mapping = comp_map | net_map
    best = mapping_cost(g1, g2, mapping)
    return _swap_descent(g1, g2, mapping, best)


def _swap_descent(g1, g2, mapping: Mapping, best: float, rounds: int = 3):
    """Swap the targets of two same-kind nodes (or retarget to a free node)."""
    for _ in range(rounds):
        improved = False
        for kind in ("net", "component"):
            ours = _nodes(g1, kind)
            free = [n for n in _nodes(g2, kind) if n not in set(mapping.values())]
            for i, a in enumerate(ours):
                options = [(b, None) for b in ours[i + 1 :]] + [(None, f) for f in free]
                for b, f in options:
                    trial = dict(mapping)
                    if b is not None:
                        trial[a], trial[b] = mapping[b], mapping[a]
                    else:
                        trial[a] = f
                    cost = mapping_cost(g1, g2, trial)
                    if cost < best:
                        mapping, best, improved = trial, cost, True
                        free = [
                            n
                            for n in _nodes(g2, kind)
                            if n not in set(mapping.values())
                        ]
                        break
        if not improved:
            break
    return mapping, best
