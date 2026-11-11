from vca.netting.extract import ComponentReport, NetExtraction
from vca.netting.terminals import terminal_layout
from vca.schemas.netlist import Component, Net, NetEndpoint, Netlist, Terminal
from vca.verify.rules import check


def extraction(parts, *, single=(), rail_conflicts=0):
    """parts: (id, detector class, category, {terminal: net}, extra contacts)."""
    components, reports, nets = [], [], {}
    for cid, det, cat, wiring, extra in parts:
        layout = terminal_layout(det, cat, (0, 0, 10, 10), "l")
        components.append(
            Component(
                id=cid,
                canonical_category=cat,
                terminals=[Terminal(name=t) for t in layout.anchors],
            )
        )
        reports.append(
            ComponentReport(
                cid,
                det,
                layout,
                terminal_nets=dict(wiring),
                unconnected_terminals=[t for t in layout.anchors if t not in wiring],
                extra_contacts=extra,
            )
        )
        for t, n in wiring.items():
            nets.setdefault(n, []).append(
                NetEndpoint(component_id=cid, terminal_name=t)
            )
    netlist = Netlist(
        components=components,
        nets=[Net(name=n, endpoints=e) for n, e in nets.items()],
    )
    return NetExtraction(netlist, reports, 2.0, 0, list(single), rail_conflicts)


def test_clean_circuit_has_no_component_flags():
    report = check(
        extraction(
            [
                ("C1", "resistor", "resistor", {"Pos": "VDD", "Neg": "out"}, 0),
                (
                    "C2",
                    "nmos",
                    "nmos",
                    {"Drain": "out", "Gate": "in", "Source": "GND"},
                    0,
                ),
                ("C3", "resistor", "resistor", {"Pos": "in", "Neg": "GND"}, 0),
            ]
        )
    )
    assert all(not flags for flags in report.per_component.values())
    assert report.circuit == {
        "no_ground": 0,
        "no_supply": 0,
        "rail_conflict": 0,
        "isolated_component": 0,
    }


def test_shorts_floats_and_missing_rails():
    report = check(
        extraction(
            [
                ("C1", "resistor", "resistor", {"Pos": "a", "Neg": "a"}, 0),
                ("C2", "voltage", "voltage", {"Positive": "a", "Negative": "a"}, 0),
                ("C3", "nmos", "nmos", {"Drain": "a", "Gate": "g", "Source": "a"}, 2),
                ("C4", "capacitor", "capacitor", {"Pos": "x"}, 0),
            ],
            single=["g", "x"],
            rail_conflicts=1,
        )
    )
    assert report.per_component["C1"] == ["shorted_two_terminal"]
    assert report.per_component["C2"] == ["shorted_source"]
    assert report.per_component["C3"] == [
        "floating_terminal",
        "drain_source_short",
        "extra_contacts",
    ]
    assert report.per_component["C4"] == ["unconnected_terminal", "floating_terminal"]
    assert report.circuit == {
        "no_ground": 1,
        "no_supply": 1,
        "rail_conflict": 1,
        "isolated_component": 1,
    }
    assert report.counts()["shorted_two_terminal"] == 1
