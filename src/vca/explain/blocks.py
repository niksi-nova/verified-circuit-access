"""Explicit, testable graph rules for "possible" circuit blocks.

Every rule here looks only at the predicted netlist (categories, terminals,
nets) — never at ground truth. A rule either fires or it doesn't; there is
no scoring or guessing. All findings are worded "possible" because the
rule is necessary, not sufficient, for the real block.
"""

from __future__ import annotations

from vca.explain.graph import CircuitGraph

MOS_CATEGORIES = ("nmos", "pmos")
TWO_TERMINAL_CATEGORIES = (
    "resistor",
    "capacitor",
    "inductor",
    "switch",
    "diode",
    "current",
    "voltage",
)


def _components_of(graph: CircuitGraph, categories: tuple[str, ...]) -> list[dict]:
    return [
        graph.components[cid]
        for cid in graph.reading_order
        if graph.components[cid]["canonical_category"] in categories
    ]


def find_diode_connected(graph: CircuitGraph) -> list[dict]:
    """A MOS transistor is "diode-connected" when its Gate and Drain are
    tied to the same net — a textbook pattern (e.g. biasing, a mirror's
    reference leg). Rule: ``net(Gate) == net(Drain)`` for an nmos/pmos."""
    found = []
    for comp in _components_of(graph, MOS_CATEGORIES):
        cid = comp["id"]
        gate_net = graph.net_of(cid, "Gate")
        drain_net = graph.net_of(cid, "Drain")
        if gate_net is not None and gate_net == drain_net:
            found.append(
                {
                    "kind": "diode_connected",
                    "components": [cid],
                    "nets": [gate_net],
                }
            )
    return found


def find_current_mirror_candidates(graph: CircuitGraph) -> list[dict]:
    """Two same-type MOS transistors sharing both their Gate net and their
    Source net, where at least one of them is diode-connected, are a
    possible current mirror: the diode-connected device sets a gate
    voltage that the other device (same source, same gate) copies as a
    current. Rule: ``net(Gate_A) == net(Gate_B) and net(Source_A) ==
    net(Source_B)``, A != B, same category, and ``diode_connected(A) or
    diode_connected(B)``."""
    diode_ids = {b["components"][0] for b in find_diode_connected(graph)}
    found = []
    seen_pairs: set[frozenset[str]] = set()
    for category in MOS_CATEGORIES:
        comps = _components_of(graph, (category,))
        for i, a in enumerate(comps):
            for b in comps[i + 1 :]:
                pair = frozenset({a["id"], b["id"]})
                if pair in seen_pairs:
                    continue
                gate_a, gate_b = (
                    graph.net_of(a["id"], "Gate"),
                    graph.net_of(b["id"], "Gate"),
                )
                src_a, src_b = (
                    graph.net_of(a["id"], "Source"),
                    graph.net_of(b["id"], "Source"),
                )
                if (
                    gate_a is not None
                    and gate_a == gate_b
                    and src_a is not None
                    and src_a == src_b
                    and (a["id"] in diode_ids or b["id"] in diode_ids)
                ):
                    seen_pairs.add(pair)
                    found.append(
                        {
                            "kind": "current_mirror_candidate",
                            "components": sorted(pair),
                            "nets": [gate_a, src_a],
                        }
                    )
    return found


def find_differential_pairs(graph: CircuitGraph) -> list[dict]:
    """Groups same-type MOS transistors by shared Source net.

    Exactly two same-type MOS on one source net, with different Gate
    nets, are a possible differential pair: a shared tail current, two
    separate inputs. Rule: ``net(Source_A) == net(Source_B) and
    net(Gate_A) != net(Gate_B)``.

    Three or more same-type MOS on one source net are not called a
    differential pair (the pattern doesn't generalize past two inputs):
    one "shared tail node" sentence is emitted instead, naming every
    transistor on that net, regardless of their gate nets — this is
    usually a shared bias or tail node, not a pairwise relationship.
    """
    found = []
    for category in MOS_CATEGORIES:
        comps = _components_of(graph, (category,))
        groups: dict[str, list[str]] = {}
        for comp in comps:
            source_net = graph.net_of(comp["id"], "Source")
            if source_net is not None:
                groups.setdefault(source_net, []).append(comp["id"])

        for source_net, ids in groups.items():
            if len(ids) == 2:
                gate_a = graph.net_of(ids[0], "Gate")
                gate_b = graph.net_of(ids[1], "Gate")
                if gate_a is not None and gate_a != gate_b:
                    found.append(
                        {
                            "kind": "differential_pair_candidate",
                            "components": list(ids),
                            "nets": [source_net],
                        }
                    )
            elif len(ids) >= 3:
                found.append(
                    {
                        "kind": "shared_tail_node",
                        "components": list(ids),
                        "nets": [source_net],
                    }
                )
    return found


def _two_terminal_nets(graph: CircuitGraph, comp: dict) -> tuple[str, str] | None:
    terminals = comp["terminals"]
    if len(terminals) != 2:
        return None
    nets = tuple(graph.net_of(comp["id"], t["name"]) for t in terminals)
    if None in nets:
        return None
    return nets


def find_series_pairs(graph: CircuitGraph) -> list[dict]:
    """Two two-terminal parts (resistor, capacitor, inductor, switch,
    diode, current or voltage source) are a possible series pair when one
    net joins exactly one terminal of each, and nothing else: that net's
    only two endpoints are those two terminals. Rule: a shared net with
    ``len(net.endpoints) == 2``, one endpoint on each component."""
    comps = _components_of(graph, TWO_TERMINAL_CATEGORIES)
    found = []
    seen_pairs: set[frozenset[str]] = set()
    for i, a in enumerate(comps):
        a_nets = _two_terminal_nets(graph, a)
        if a_nets is None:
            continue
        for b in comps[i + 1 :]:
            pair = frozenset({a["id"], b["id"]})
            if pair in seen_pairs:
                continue
            b_nets = _two_terminal_nets(graph, b)
            if b_nets is None:
                continue
            shared = set(a_nets) & set(b_nets)
            for net_name in shared:
                if len(graph.net_endpoints.get(net_name, [])) == 2:
                    seen_pairs.add(pair)
                    found.append(
                        {
                            "kind": "series_pair",
                            "components": sorted(pair),
                            "nets": [net_name],
                        }
                    )
                    break
    return found


def find_parallel_pairs(graph: CircuitGraph) -> list[dict]:
    """Two two-terminal parts are a possible parallel pair when both of
    their terminals land on the very same two nets. Rule:
    ``{net(A.t0), net(A.t1)} == {net(B.t0), net(B.t1)}`` and the two nets
    differ."""
    comps = _components_of(graph, TWO_TERMINAL_CATEGORIES)
    found = []
    seen_pairs: set[frozenset[str]] = set()
    for i, a in enumerate(comps):
        a_nets = _two_terminal_nets(graph, a)
        if a_nets is None or a_nets[0] == a_nets[1]:
            continue
        for b in comps[i + 1 :]:
            pair = frozenset({a["id"], b["id"]})
            if pair in seen_pairs:
                continue
            b_nets = _two_terminal_nets(graph, b)
            if b_nets is not None and set(a_nets) == set(b_nets):
                seen_pairs.add(pair)
                found.append(
                    {
                        "kind": "parallel_pair",
                        "components": sorted(pair),
                        "nets": sorted(set(a_nets)),
                    }
                )
    return found


BLOCK_FINDERS = (
    find_diode_connected,
    find_current_mirror_candidates,
    find_differential_pairs,
    find_series_pairs,
    find_parallel_pairs,
)


def find_blocks(graph: CircuitGraph) -> list[dict]:
    """All blocks found, in a deterministic order (by kind, then by the
    sorted component ids involved)."""
    blocks = [block for finder in BLOCK_FINDERS for block in finder(graph)]
    blocks.sort(key=lambda b: (b["kind"], b["components"]))
    return blocks
