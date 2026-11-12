"""Deterministic sentence templates for the three explanation layers.

No LLM calls, no invented values. Every sentence is a dict with ``text``
plus the ``components``/``nets`` ids it was built from, so a reader (or a
test) can always trace a claim back to the graph.
"""

from __future__ import annotations

from collections import Counter

from vca.explain.graph import CircuitGraph
from vca.explain.names import plain_name

# A circuit is called a "resistor network" only when every component is a
# resistor or a source, and at least one of each is present. Any other mix
# gets no circuit-type sentence at all.
_RESISTOR_NETWORK_PARTS = {"resistor", "voltage", "current"}


def _sentence(text: str, components: list[str] = (), nets: list[str] = ()) -> dict:
    return {"text": text, "components": list(components), "nets": list(nets)}


def build_layer1(graph: CircuitGraph, circuit_level_flags: dict) -> list[dict]:
    categories = [
        graph.components[cid]["canonical_category"] for cid in graph.reading_order
    ]
    counts = Counter(plain_name(c) for c in categories)
    all_ids = list(graph.reading_order)

    parts = ", ".join(
        f"{n} {name}{'s' if n != 1 else ''}" for name, n in sorted(counts.items())
    )
    sentences = [
        _sentence(f"This circuit has {len(all_ids)} components: {parts}.", all_ids, [])
    ]

    net_ids = list(graph.net_endpoints)
    ground_found = any(graph.label_of(n) == "ground" for n in net_ids)
    supply_found = any(graph.label_of(n) == "supply" for n in net_ids)
    sentences.append(
        _sentence(
            f"It has {len(net_ids)} electrical nets. "
            f"A ground net was {'found' if ground_found else 'not found'}, "
            f"and a supply net was "
            f"{'found' if supply_found else 'not found'}.",
            [],
            net_ids,
        )
    )

    raw_categories = {c for c in categories}
    if (
        raw_categories
        and raw_categories <= _RESISTOR_NETWORK_PARTS
        and ("resistor" in raw_categories)
        and (raw_categories & {"voltage", "current"})
    ):
        sentences.append(
            _sentence(
                "Because it contains only resistors and a source, this "
                "circuit appears to be a resistor network.",
                all_ids,
                [],
            )
        )

    if circuit_level_flags.get("no_ground"):
        sentences.append(_sentence("No ground net was found in this circuit.", [], []))
    if circuit_level_flags.get("no_supply"):
        sentences.append(_sentence("No supply net was found in this circuit.", [], []))
    if circuit_level_flags.get("rail_conflict"):
        sentences.append(
            _sentence("A wire appears to touch both a ground and a supply net.", [], [])
        )

    return sentences


_BLOCK_TEXT = {
    "diode_connected": (
        "{a} is possibly diode-connected (its gate and drain are on the "
        "same net, {net_a})."
    ),
    "current_mirror_candidate": (
        "{a} and {b} share a gate net and a source net, with one "
        "diode-connected: a possible current mirror."
    ),
    "differential_pair_candidate": (
        "{a} and {b} share a source net ({net_a}) but have different gate "
        "nets: a possible differential pair."
    ),
    "series_pair": (
        "{a} and {b} share a net ({net_a}) that connects only the two of "
        "them: a possible series pair."
    ),
    "parallel_pair": (
        "{a} and {b} both connect the same two nets ({net_a} and "
        "{net_b}): a possible parallel pair."
    ),
}


def build_layer2(graph: CircuitGraph, blocks: list[dict]) -> list[dict]:
    if not blocks:
        return [
            _sentence("No further circuit blocks were detected from the graph.", [], [])
        ]

    sentences = []
    for block in blocks:
        comp_ids = block["components"]
        net_labels = [graph.label_of(n) for n in block["nets"]]
        if block["kind"] == "shared_tail_node":
            text = (
                f"{len(comp_ids)} transistors ({', '.join(comp_ids)}) share a "
                f"source connection ({net_labels[0]}), which usually means a "
                "shared bias or tail node."
            )
        else:
            text = _BLOCK_TEXT[block["kind"]].format(
                a=comp_ids[0],
                b=comp_ids[1] if len(comp_ids) > 1 else "",
                net_a=net_labels[0] if net_labels else "",
                net_b=net_labels[1] if len(net_labels) > 1 else "",
            )
        sentences.append(_sentence(text, comp_ids, block["nets"]))
    return sentences


def build_layer3(
    graph: CircuitGraph, flags_by_component: dict[str, dict]
) -> list[dict]:
    sentences = []
    for comp_id in graph.reading_order:
        comp = graph.components[comp_id]
        type_name = plain_name(comp["canonical_category"])
        connections = []
        for terminal in comp["terminals"]:
            net_name = graph.net_of(comp_id, terminal["name"])
            if net_name is None:
                connections.append(f"{terminal['name']} is not connected")
                continue
            endpoints = graph.other_endpoints(net_name, (comp_id, terminal["name"]))
            other_parts = sorted(
                {other_id for other_id, _ in endpoints if other_id != comp_id}
            )
            own_other_terminals = sorted(
                {t for other_id, t in endpoints if other_id == comp_id}
            )
            label = graph.label_of(net_name)
            if other_parts:
                connections.append(
                    f"{terminal['name']} connects to {label} "
                    f"(with {', '.join(other_parts)})"
                )
            elif own_other_terminals:
                connections.append(
                    f"{terminal['name']} connects to {label} (tied to this "
                    f"part's {', '.join(own_other_terminals)})"
                )
            else:
                connections.append(f"{terminal['name']} connects to {label} alone")

        flags = flags_by_component[comp_id]
        status = flags["level"]
        reason_text = (
            "; ".join(flags["reasons"]) if flags["reasons"] else "no issues flagged"
        )
        text = (
            f"{comp_id} is a {type_name}. "
            f"{'; '.join(connections)}. "
            f"Status: {status} ({reason_text})."
        )
        nets_referenced = [
            graph.net_of(comp_id, t["name"])
            for t in comp["terminals"]
            if graph.net_of(comp_id, t["name"]) is not None
        ]
        sentences.append(_sentence(text, [comp_id], nets_referenced))
    return sentences
