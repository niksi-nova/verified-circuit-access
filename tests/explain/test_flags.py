"""Test-only fixtures for flags: levels, reasons, and ground-truth isolation."""

from vca.explain.flags import circuit_flags, component_flags, is_isolated
from vca.explain.graph import CircuitGraph


def _comp(cid, category="resistor", terminals=("Pos", "Neg"), x=0, y=0):
    return {
        "id": cid,
        "canonical_category": category,
        "terminals": [{"name": t} for t in terminals],
        "bbox": {"x": x, "y": y, "width": 20, "height": 20},
    }


def _net(name, endpoints):
    return {
        "name": name,
        "endpoints": [{"component_id": c, "terminal_name": t} for c, t in endpoints],
    }


def _graph(components, nets):
    return CircuitGraph.build({"components": components, "nets": nets})


def test_strong_rule_flag_means_needs_check():
    graph = _graph(
        [_comp("C1")],
        [_net("GND", [("C1", "Pos")]), _net("n1", [("C1", "Neg")])],
    )
    row = {"component_id": "C1", "rules": ["shorted_two_terminal"]}
    flags = component_flags(graph, row, p_wrong=None)
    assert flags["level"] == "needs check"
    assert flags["strong_flags"] == ["shorted_two_terminal"]
    assert "joined together" in flags["reasons"][0]


def test_weak_rule_flag_alone_means_no_concern():
    graph = _graph(
        [_comp("C1")],
        [_net("GND", [("C1", "Pos")]), _net("n1", [("C1", "Neg")])],
    )
    row = {"component_id": "C1", "rules": ["floating_terminal"]}
    flags = component_flags(graph, row, p_wrong=None)
    assert flags["level"] == "no concern"
    assert flags["weak_flags"] == ["floating_terminal"]


def test_high_verifier_probability_means_needs_check():
    graph = _graph(
        [_comp("C1")],
        [_net("GND", [("C1", "Pos")]), _net("n1", [("C1", "Neg")])],
    )
    row = {"component_id": "C1", "rules": []}
    flags = component_flags(graph, row, p_wrong=0.63)
    assert flags["level"] == "needs check"
    assert any("63%" in r for r in flags["reasons"])


def test_low_verifier_probability_means_no_concern():
    graph = _graph(
        [_comp("C1")],
        [_net("GND", [("C1", "Pos")]), _net("n1", [("C1", "Neg")])],
    )
    row = {"component_id": "C1", "rules": []}
    flags = component_flags(graph, row, p_wrong=0.1)
    assert flags["level"] == "no concern"


def test_isolated_component_detected_without_ground_truth():
    # C1 shares no net with a rail or another component.
    graph = _graph(
        [_comp("C1"), _comp("C2", x=100)],
        [_net("n1", [("C1", "Pos"), ("C1", "Neg")]), _net("n2", [("C2", "Pos")])],
    )
    assert is_isolated(graph, "C1") is True
    assert is_isolated(graph, "C2") is True  # C2's Neg terminal is unconnected


def test_isolated_component_false_when_sharing_a_net():
    graph = _graph(
        [_comp("C1"), _comp("C2", x=100)],
        [
            _net("shared", [("C1", "Pos"), ("C2", "Pos")]),
            _net("a", [("C1", "Neg")]),
            _net("b", [("C2", "Neg")]),
        ],
    )
    assert is_isolated(graph, "C1") is False


def test_ground_truth_fields_never_change_flags():
    """A component_row carrying fabricated ground-truth-looking fields
    (as a real pipeline prediction would, via its sibling `score` key)
    must not change the flag outcome: component_flags never reads them."""
    graph = _graph(
        [_comp("C1")],
        [_net("GND", [("C1", "Pos")]), _net("n1", [("C1", "Neg")])],
    )
    clean_row = {"component_id": "C1", "rules": ["floating_terminal"]}
    contaminated_row = clean_row | {
        "wrong": True,
        "gt_error_kind": "wrong_connection",
    }
    assert component_flags(graph, clean_row, p_wrong=0.2) == component_flags(
        graph, contaminated_row, p_wrong=0.2
    )


def test_circuit_flags_read_counts_as_booleans():
    counts = {"no_ground": 0, "no_supply": 2, "rail_conflict": 0}
    assert circuit_flags(counts) == {
        "no_ground": False,
        "no_supply": True,
        "rail_conflict": False,
    }
