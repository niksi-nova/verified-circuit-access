"""Tests for netlist alignment and per-element error diagnosis."""

import pytest

from vca.metrics.alignment import (
    align,
    component_scores,
    connection_scores,
    diagnose,
    ned_from_alignment,
)
from vca.schemas.netlist import Component, Net, NetEndpoint, Netlist, Terminal

MOS = ("Drain", "Gate", "Source")


def build(components: list[tuple[str, str, dict[str, str]]]) -> Netlist:
    """Build a netlist from (id, category, {terminal: net}) triples."""
    nets: dict[str, list[NetEndpoint]] = {}
    built = []
    for component_id, category, ports in components:
        built.append(
            Component(
                id=component_id,
                canonical_category=category,
                terminals=[Terminal(name=t) for t in ports],
            )
        )
        for terminal, net in ports.items():
            nets.setdefault(net, []).append(
                NetEndpoint(component_id=component_id, terminal_name=terminal)
            )
    return Netlist(
        components=built,
        nets=[Net(name=n, endpoints=e) for n, e in nets.items()],
    )


def reference() -> list[tuple[str, str, dict[str, str]]]:
    # Diodes pin down nets A and C so a drain/source swap can't be undone by
    # relabelling nets.
    return [
        ("M1", "nmos", {"Drain": "A", "Gate": "B", "Source": "C"}),
        ("D1", "diode", {"In": "A", "Out": "B"}),
        ("D2", "diode", {"In": "A", "Out": "B"}),
        ("R1", "resistor", {"Pos": "C", "Neg": "B"}),
    ]


def kinds(predicted: Netlist, truth: Netlist) -> list[str]:
    alignment = align(predicted, truth, timeout=10)
    return sorted(error.kind for error in diagnose(predicted, truth, alignment))


def test_identical_netlists_align_without_errors():
    truth = build(reference())
    alignment = align(truth, truth)

    assert alignment.isomorphic
    assert alignment.ged == 0
    assert diagnose(truth, truth, alignment) == []
    assert ned_from_alignment(alignment, truth) == 0


def test_missed_component():
    truth = build(reference())
    predicted = build(reference()[:-1])

    assert kinds(predicted, truth) == ["missed_component"]


def test_extra_component():
    truth = build(reference())
    predicted = build(
        reference() + [("C9", "capacitor", {"Pos": "A", "Neg": "C"})]
    )

    assert kinds(predicted, truth) == ["extra_component"]


def test_wrong_component_type():
    truth = build(reference())
    swapped = reference()
    swapped[3] = ("R1", "capacitor", {"Pos": "C", "Neg": "B"})

    assert kinds(build(swapped), truth) == ["wrong_component_type"]


def test_drain_source_swap_is_polarity_error():
    truth = build(reference())
    swapped = reference()
    swapped[0] = ("M1", "nmos", {"Drain": "C", "Gate": "B", "Source": "A"})

    assert kinds(build(swapped), truth) == ["wrong_polarity"]


def test_resistor_orientation_is_not_an_error():
    truth = build(reference())
    flipped = reference()
    flipped[3] = ("R1", "resistor", {"Pos": "B", "Neg": "C"})

    assert align(build(flipped), truth).isomorphic


def test_rewired_terminal_is_connection_error():
    truth = build(reference())
    rewired = reference()
    rewired[0] = ("M1", "nmos", {"Drain": "A", "Gate": "C", "Source": "C"})

    assert "wrong_connection" in kinds(build(rewired), truth)


def test_scores_give_partial_credit():
    truth = build(reference())
    predicted = build(reference()[:-1])
    alignment = align(predicted, truth)

    component_p, component_r = component_scores(predicted, truth, alignment)
    connection_p, connection_r = connection_scores(predicted, truth, alignment)

    assert component_p == 1.0
    assert component_r == pytest.approx(3 / 4)
    # Net B keeps its other endpoints but loses R1; nets A and C are intact
    # except C loses R1 too.
    assert 0.0 < connection_r < 1.0
    assert 0.0 < connection_p <= 1.0
