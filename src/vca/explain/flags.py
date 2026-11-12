"""Per-component and per-circuit "needs check" flags.

Every flag here comes from the predicted netlist and the rule-check /
verifier evidence already computed by the pipeline — never from ground
truth (``score``, ``ned``, alignment, golden netlists). That evidence is
surfaced separately, in an evaluation-only block.
"""

from __future__ import annotations

from vca.explain.graph import CircuitGraph

STRONG_RULES = (
    "shorted_two_terminal",
    "shorted_source",
    "drain_source_short",
    "collector_emitter_short",
    "unconnected_terminal",
)
WEAK_RULES = ("floating_terminal", "extra_contacts")

_RULE_REASONS = {
    "unconnected_terminal": "a terminal of this part has no wire reaching it",
    "floating_terminal": "a terminal of this part is on a net nothing else is on",
    "shorted_two_terminal": "both terminals of this part are joined together",
    "shorted_source": "this source's + and - terminals are joined together",
    "drain_source_short": "this transistor's drain and source are joined together",
    "collector_emitter_short": "this transistor's collector and emitter are "
    "joined together",
    "extra_contacts": "more wires touch this part's box than it has terminals",
    "isolated_component": "this part shares no net with anything else in the circuit",
}

VERIFIER_THRESHOLD = 0.5


def is_isolated(graph: CircuitGraph, component_id: str) -> bool:
    """Mirrors ``vca.verify.rules.check``'s ``isolated_component`` rule:
    true when none of this component's terminals sits on a net that also
    reaches a ground/supply rail or another component."""
    comp = graph.components[component_id]
    for terminal in comp["terminals"]:
        net_name = graph.net_of(component_id, terminal["name"])
        if net_name is None:
            continue
        if net_name.strip().upper() in ("GND", "VDD"):
            return False
        others = graph.other_endpoints(net_name, (component_id, terminal["name"]))
        if any(other_id != component_id for other_id, _ in others):
            return False
    return True


def component_flags(
    graph: CircuitGraph, component_row: dict, p_wrong: float | None
) -> dict:
    """``component_row`` is one entry of a prediction's ``components``
    list (has ``component_id`` and a ``rules`` list of violated
    component-level rule names)."""
    component_id = component_row["component_id"]
    rules = set(component_row.get("rules", ()))

    strong = sorted(rules & set(STRONG_RULES))
    weak = sorted(rules & set(WEAK_RULES))
    if is_isolated(graph, component_id):
        weak.append("isolated_component")
        weak.sort()

    reasons = [_RULE_REASONS[r] for r in strong] + [_RULE_REASONS[r] for r in weak]
    high_p = p_wrong is not None and p_wrong >= VERIFIER_THRESHOLD
    if p_wrong is not None:
        reasons.append(
            f"verifier estimates a {round(p_wrong * 100)}% chance of an error here"
        )

    level = "needs check" if (strong or high_p) else "no concern"
    return {
        "component_id": component_id,
        "level": level,
        "strong_flags": strong,
        "weak_flags": weak,
        "verifier_p_wrong": p_wrong,
        "reasons": reasons,
    }


def circuit_flags(rule_counts: dict) -> dict:
    """``rule_counts`` is a prediction's top-level ``rules`` dict (same
    shape as ``RuleReport.counts()``)."""
    return {
        "no_ground": bool(rule_counts.get("no_ground", 0)),
        "no_supply": bool(rule_counts.get("no_supply", 0)),
        "rail_conflict": bool(rule_counts.get("rail_conflict", 0)),
    }
