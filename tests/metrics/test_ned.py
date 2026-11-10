
import pytest

from vca.metrics.ned import compute_ned
from vca.schemas.netlist import Component, Net, NetEndpoint, Netlist, Terminal


def make_netlist(
    component_id: str = "R1",
    net_name: str = "N1",
) -> Netlist:
    return Netlist(
        components=[
            Component(
                id=component_id,
                canonical_category="resistor",
                terminals=[Terminal(name="1"), Terminal(name="2")],
            )
        ],
        nets=[
            Net(
                name=net_name,
                endpoints=[
                    NetEndpoint(component_id=component_id, terminal_name="1"),
                    NetEndpoint(component_id=component_id, terminal_name="2"),
                ],
            )
        ],
    )


def test_identical_netlists_have_zero_ned():
    netlist = make_netlist()

    assert compute_ned(netlist, netlist) == pytest.approx(0.0)


def test_component_ids_and_net_names_do_not_affect_ned():
    predicted = make_netlist("R1", "N1")
    ground_truth = make_netlist("R99", "N99")

    assert compute_ned(predicted, ground_truth) == pytest.approx(0.0)


def test_empty_ground_truth_returns_none():
    predicted = make_netlist()
    ground_truth = Netlist(components=[], nets=[])

    assert compute_ned(predicted, ground_truth) is None


def test_missing_endpoint_contributes_to_ged():
    predicted = make_netlist()
    ground_truth = Netlist(
        components=[
            Component(
                id="R2",
                canonical_category="resistor",
                terminals=[Terminal(name="1"), Terminal(name="2")],
            )
        ],
        nets=[
            Net(
                name="N2",
                endpoints=[
                    NetEndpoint(component_id="R2", terminal_name="2"),
                ],
            )
        ],
    )

    assert compute_ned(predicted, ground_truth) > 0.0

def test_different_component_categories_contribute_to_ged():
    predicted = make_netlist()

    ground_truth = Netlist(
        components=[
            Component(
                id="R1",
                canonical_category="capacitor",
                terminals=[Terminal(name="1"), Terminal(name="2")],
            )
        ],
        nets=[
            Net(
                name="N1",
                endpoints=[
                    NetEndpoint(component_id="R1", terminal_name="1"),
                    NetEndpoint(component_id="R1", terminal_name="2"),
                ],
            )
        ],
    )

    assert compute_ned(predicted, ground_truth) > 0.0


def test_different_terminal_labels_contribute_to_ged():
    predicted = Netlist(
        components=[
            Component(
                id="R1",
                canonical_category="resistor",
                terminals=[Terminal(name="1"), Terminal(name="2")],
            ),
            Component(
                id="C1",
                canonical_category="capacitor",
                terminals=[Terminal(name="1"), Terminal(name="2")],
            ),
        ],
        nets=[
            Net(
                name="N1",
                endpoints=[
                    NetEndpoint(component_id="R1", terminal_name="1"),
                    NetEndpoint(component_id="C1", terminal_name="1"),
                ],
            ),
            Net(
                name="N2",
                endpoints=[
                    NetEndpoint(component_id="R1", terminal_name="2"),
                    NetEndpoint(component_id="C1", terminal_name="2"),
                ],
            ),
        ],
    )

    ground_truth = Netlist(
        components=[
            Component(
                id="R1",
                canonical_category="resistor",
                terminals=[Terminal(name="1"), Terminal(name="2")],
            ),
            Component(
                id="C1",
                canonical_category="capacitor",
                terminals=[Terminal(name="1"), Terminal(name="2")],
            ),
        ],
        nets=[
            Net(
                name="N1",
                endpoints=[
                    NetEndpoint(component_id="R1", terminal_name="1"),
                    NetEndpoint(component_id="C1", terminal_name="2"),
                ],
            ),
            Net(
                name="N2",
                endpoints=[
                    NetEndpoint(component_id="R1", terminal_name="2"),
                    NetEndpoint(component_id="C1", terminal_name="1"),
                ],
            ),
        ],
    )

    assert compute_ned(predicted, ground_truth) > 0.0