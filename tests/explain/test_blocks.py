"""Test-only fixtures for each block rule: positive and negative cases."""

from vca.explain.blocks import (
    find_current_mirror_candidates,
    find_differential_pairs,
    find_diode_connected,
    find_parallel_pairs,
    find_series_pairs,
)
from vca.explain.graph import CircuitGraph


def _mos(cid, category, x=0, y=0):
    return {
        "id": cid,
        "canonical_category": category,
        "terminals": [{"name": "Gate"}, {"name": "Drain"}, {"name": "Source"}],
        "bbox": {"x": x, "y": y, "width": 20, "height": 20},
    }


def _two_terminal(cid, category, x=0, y=0):
    return {
        "id": cid,
        "canonical_category": category,
        "terminals": [{"name": "Pos"}, {"name": "Neg"}],
        "bbox": {"x": x, "y": y, "width": 20, "height": 20},
    }


def _net(name, endpoints):
    return {
        "name": name,
        "endpoints": [{"component_id": c, "terminal_name": t} for c, t in endpoints],
    }


def _graph(components, nets):
    return CircuitGraph.build({"components": components, "nets": nets})


def test_diode_connected_positive():
    graph = _graph(
        [_mos("C1", "nmos")],
        [_net("gd", [("C1", "Gate"), ("C1", "Drain")]), _net("s", [("C1", "Source")])],
    )
    found = find_diode_connected(graph)
    assert [b["components"] for b in found] == [["C1"]]


def test_diode_connected_negative_when_gate_and_drain_differ():
    graph = _graph(
        [_mos("C1", "nmos")],
        [
            _net("g", [("C1", "Gate")]),
            _net("d", [("C1", "Drain")]),
            _net("s", [("C1", "Source")]),
        ],
    )
    assert find_diode_connected(graph) == []


def test_current_mirror_positive():
    # C1 diode-connected (gate==drain); C2 shares gate and source with C1.
    graph = _graph(
        [_mos("C1", "pmos", x=0), _mos("C2", "pmos", x=50)],
        [
            _net("gate_drain", [("C1", "Gate"), ("C1", "Drain"), ("C2", "Gate")]),
            _net("source", [("C1", "Source"), ("C2", "Source")]),
            _net("d2", [("C2", "Drain")]),
        ],
    )
    found = find_current_mirror_candidates(graph)
    assert [b["components"] for b in found] == [["C1", "C2"]]


def test_current_mirror_negative_when_neither_diode_connected():
    graph = _graph(
        [_mos("C1", "pmos", x=0), _mos("C2", "pmos", x=50)],
        [
            _net("gate", [("C1", "Gate"), ("C2", "Gate")]),
            _net("source", [("C1", "Source"), ("C2", "Source")]),
            _net("d1", [("C1", "Drain")]),
            _net("d2", [("C2", "Drain")]),
        ],
    )
    assert find_current_mirror_candidates(graph) == []


def test_differential_pair_positive():
    graph = _graph(
        [_mos("C1", "nmos", x=0), _mos("C2", "nmos", x=50)],
        [
            _net("tail", [("C1", "Source"), ("C2", "Source")]),
            _net("g1", [("C1", "Gate")]),
            _net("g2", [("C2", "Gate")]),
            _net("d1", [("C1", "Drain")]),
            _net("d2", [("C2", "Drain")]),
        ],
    )
    found = find_differential_pairs(graph)
    assert [b["components"] for b in found] == [["C1", "C2"]]


def test_differential_pair_negative_when_gates_match():
    graph = _graph(
        [_mos("C1", "nmos", x=0), _mos("C2", "nmos", x=50)],
        [
            _net("tail", [("C1", "Source"), ("C2", "Source")]),
            _net("gate", [("C1", "Gate"), ("C2", "Gate")]),
            _net("d1", [("C1", "Drain")]),
            _net("d2", [("C2", "Drain")]),
        ],
    )
    assert find_differential_pairs(graph) == []


def test_three_transistors_on_one_source_net_is_a_shared_tail_node():
    graph = _graph(
        [
            _mos("C1", "nmos", x=0),
            _mos("C2", "nmos", x=50),
            _mos("C3", "nmos", x=100),
        ],
        [
            _net(
                "tail",
                [("C1", "Source"), ("C2", "Source"), ("C3", "Source")],
            ),
            _net("g1", [("C1", "Gate")]),
            _net("g2", [("C2", "Gate")]),
            _net("g3", [("C3", "Gate")]),
            _net("d1", [("C1", "Drain")]),
            _net("d2", [("C2", "Drain")]),
            _net("d3", [("C3", "Drain")]),
        ],
    )
    found = find_differential_pairs(graph)
    assert len(found) == 1
    assert found[0]["kind"] == "shared_tail_node"
    assert found[0]["components"] == ["C1", "C2", "C3"]


def test_series_pair_positive():
    graph = _graph(
        [_two_terminal("C1", "resistor", x=0), _two_terminal("C2", "resistor", x=50)],
        [
            _net("junction", [("C1", "Neg"), ("C2", "Pos")]),
            _net("a", [("C1", "Pos")]),
            _net("b", [("C2", "Neg")]),
        ],
    )
    found = find_series_pairs(graph)
    assert [b["components"] for b in found] == [["C1", "C2"]]


def test_series_pair_negative_when_junction_has_a_third_part():
    graph = _graph(
        [
            _two_terminal("C1", "resistor", x=0),
            _two_terminal("C2", "resistor", x=50),
            _two_terminal("C3", "resistor", x=100),
        ],
        [
            _net("junction", [("C1", "Neg"), ("C2", "Pos"), ("C3", "Pos")]),
            _net("a", [("C1", "Pos")]),
            _net("b", [("C2", "Neg")]),
            _net("c", [("C3", "Neg")]),
        ],
    )
    assert find_series_pairs(graph) == []


def test_parallel_pair_positive():
    graph = _graph(
        [_two_terminal("C1", "resistor", x=0), _two_terminal("C2", "resistor", x=50)],
        [
            _net("top", [("C1", "Pos"), ("C2", "Pos")]),
            _net("bottom", [("C1", "Neg"), ("C2", "Neg")]),
        ],
    )
    found = find_parallel_pairs(graph)
    assert [b["components"] for b in found] == [["C1", "C2"]]


def test_parallel_pair_negative_when_nets_differ():
    graph = _graph(
        [_two_terminal("C1", "resistor", x=0), _two_terminal("C2", "resistor", x=50)],
        [
            _net("top", [("C1", "Pos"), ("C2", "Pos")]),
            _net("bottom1", [("C1", "Neg")]),
            _net("bottom2", [("C2", "Neg")]),
        ],
    )
    assert find_parallel_pairs(graph) == []
