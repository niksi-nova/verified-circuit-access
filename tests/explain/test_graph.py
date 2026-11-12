"""Test-only fixtures for CircuitGraph: reading order and net labels."""

from vca.explain.graph import CircuitGraph


def _comp(cid, category, terminals, x, y, w=20, h=20):
    return {
        "id": cid,
        "canonical_category": category,
        "terminals": [{"name": t} for t in terminals],
        "bbox": {"x": x, "y": y, "width": w, "height": h},
    }


def _net(name, endpoints):
    return {
        "name": name,
        "endpoints": [{"component_id": c, "terminal_name": t} for c, t in endpoints],
    }


def test_reading_order_left_to_right_top_to_bottom():
    netlist = {
        "components": [
            _comp("C2", "resistor", ["Pos", "Neg"], x=100, y=0),
            _comp("C1", "resistor", ["Pos", "Neg"], x=0, y=0),
            _comp("C3", "resistor", ["Pos", "Neg"], x=0, y=200),
        ],
        "nets": [
            _net("n1", [("C1", "Pos"), ("C2", "Pos")]),
            _net("n2", [("C1", "Neg"), ("C3", "Pos")]),
            _net("n3", [("C2", "Neg"), ("C3", "Neg")]),
        ],
    }
    graph = CircuitGraph.build(netlist)
    assert graph.reading_order == ["C1", "C2", "C3"]


def test_ground_and_supply_nets_get_fixed_labels():
    netlist = {
        "components": [_comp("C1", "resistor", ["Pos", "Neg"], x=0, y=0)],
        "nets": [
            _net("GND", [("C1", "Neg")]),
            _net("VDD", [("C1", "Pos")]),
        ],
    }
    graph = CircuitGraph.build(netlist)
    assert graph.label_of("GND") == "ground"
    assert graph.label_of("VDD") == "supply"


def test_other_nets_are_numbered_in_reading_order():
    netlist = {
        "components": [
            _comp("C1", "resistor", ["Pos", "Neg"], x=0, y=0),
            _comp("C2", "resistor", ["Pos", "Neg"], x=100, y=0),
        ],
        "nets": [
            _net("zeta", [("C2", "Pos")]),
            _net("alpha", [("C1", "Pos")]),
            _net("beta", [("C1", "Neg"), ("C2", "Neg")]),
        ],
    }
    graph = CircuitGraph.build(netlist)
    # C1 is read first: its first terminal (Pos, net "alpha") becomes
    # "net 1"; its second terminal (Neg, net "beta") becomes "net 2";
    # C2's remaining terminal (Pos, net "zeta") becomes "net 3".
    assert graph.label_of("alpha") == "net 1"
    assert graph.label_of("beta") == "net 2"
    assert graph.label_of("zeta") == "net 3"


def test_net_labels_are_deterministic_across_builds():
    netlist = {
        "components": [
            _comp("C1", "resistor", ["Pos", "Neg"], x=0, y=0),
            _comp("C2", "resistor", ["Pos", "Neg"], x=100, y=0),
        ],
        "nets": [
            _net("zeta", [("C2", "Pos")]),
            _net("alpha", [("C1", "Pos")]),
        ],
    }
    first = CircuitGraph.build(netlist).net_label
    second = CircuitGraph.build(netlist).net_label
    assert first == second
