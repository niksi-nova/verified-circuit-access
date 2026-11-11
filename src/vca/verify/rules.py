"""Electrical sanity rules over an extracted netlist.

Each rule names something a correct schematic rarely contains. Violations
are not errors by themselves (an open output or a single-ended input can be
legitimate) — they are features for the verifier, which learns how much
each one predicts a real extraction mistake.

Component-level rules (flag one component):

- ``unconnected_terminal``: a terminal with no wire reached it.
- ``floating_terminal``: a terminal on a net no other terminal or rail is on.
- ``shorted_two_terminal``: both terminals of a two-terminal part on one net.
- ``shorted_source``: a voltage source's + and - on one net.
- ``drain_source_short``: MOS drain and source on one net.
- ``collector_emitter_short``: BJT collector and emitter on one net.
- ``extra_contacts``: more wires touch the box than the part has terminals.

Circuit-level rules:

- ``no_ground``: no net reaches a ground symbol.
- ``no_supply``: no net reaches a supply symbol.
- ``rail_conflict``: a wire touches both a ground and a supply symbol.
- ``isolated_component``: a component sharing no net with anything else.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from vca.netting.extract import NetExtraction

COMPONENT_RULES = (
    "unconnected_terminal",
    "floating_terminal",
    "shorted_two_terminal",
    "shorted_source",
    "drain_source_short",
    "collector_emitter_short",
    "extra_contacts",
)
CIRCUIT_RULES = ("no_ground", "no_supply", "rail_conflict", "isolated_component")

_PAIRS = {
    "drain_source_short": ("Drain", "Source"),
    "collector_emitter_short": ("Collector", "Emitter"),
    "shorted_source": ("Positive", "Negative"),
}


@dataclass
class RuleReport:
    per_component: dict[str, list[str]] = field(default_factory=dict)
    circuit: dict[str, int] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        """Number of components violating each component rule, plus circuit rules."""
        tally = Counter(r for rules in self.per_component.values() for r in rules)
        return {r: tally.get(r, 0) for r in COMPONENT_RULES} | self.circuit


def check(extraction: NetExtraction) -> RuleReport:
    netlist = extraction.netlist
    fanout = {net.name: len(net.endpoints) for net in netlist.nets}
    floating = set(extraction.single_terminal_nets)
    net_names = set(fanout)

    report = RuleReport()
    isolated = 0
    for comp in extraction.components:
        nets = comp.terminal_nets
        flags = []
        if comp.unconnected_terminals:
            flags.append("unconnected_terminal")
        if any(n in floating for n in nets.values()):
            flags.append("floating_terminal")
        names = list(comp.layout.anchors)
        if (
            len(names) == 2
            and len(nets) == 2
            and len(set(nets.values())) == 1
            and comp.layout.category != "voltage"
        ):
            flags.append("shorted_two_terminal")
        for rule, (a, b) in _PAIRS.items():
            if a in nets and b in nets and nets[a] == nets[b]:
                flags.append(rule)
        if comp.extra_contacts:
            flags.append("extra_contacts")
        report.per_component[comp.component_id] = flags

        # Shares no net with another component or a rail.
        others = [
            n for n in nets.values() if n in ("GND", "VDD") or _shared(n, comp, netlist)
        ]
        if not others:
            isolated += 1

    report.circuit = {
        "no_ground": int("GND" not in net_names),
        "no_supply": int("VDD" not in net_names),
        "rail_conflict": extraction.rail_conflicts,
        "isolated_component": isolated,
    }
    return report


def _shared(net_name: str, comp, netlist) -> bool:
    for net in netlist.nets:
        if net.name == net_name:
            return any(e.component_id != comp.component_id for e in net.endpoints)
    return False
