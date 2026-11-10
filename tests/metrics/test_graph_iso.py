
from vca.metrics.graph_iso import (
    are_isomorphic,
    graph_isomorphism_accuracy,
)
from vca.schemas.netlist import (
    Component,
    Net,
    NetEndpoint,
    Netlist,
    Terminal,
)


def make_netlist(
    component_ids: tuple[str, str] = ("R1", "C1"),
    net_name: str = "N1",
    categories: tuple[str, str] = ("resistor", "capacitor"),
) -> Netlist:
    """Create a small handcrafted circuit for testing."""
    first_id, second_id = component_ids

    return Netlist(
        components=[
            Component(
                id=first_id,
                canonical_category=categories[0],
                terminals=[Terminal(name="1")],
            ),
            Component(
                id=second_id,
                canonical_category=categories[1],
                terminals=[Terminal(name="1")],
            ),
        ],
        nets=[
            Net(
                name=net_name,
                endpoints=[
                    NetEndpoint(
                        component_id=first_id,
                        terminal_name="1",
                    ),
                    NetEndpoint(
                        component_id=second_id,
                        terminal_name="1",
                    ),
                ],
            )
        ],
    )


def test_identical_netlists_are_isomorphic():
    netlist = make_netlist()

    assert are_isomorphic(netlist, netlist)


def test_component_and_net_names_are_ignored():
    predicted = make_netlist(
        component_ids=("X7", "X8"),
        net_name="renamed_net",
    )
    ground_truth = make_netlist(
        component_ids=("R1", "C1"),
        net_name="N1",
    )

    assert are_isomorphic(predicted, ground_truth)


def test_different_component_categories_are_not_isomorphic():
    predicted = make_netlist(
        categories=("resistor", "diode"),
    )
    ground_truth = make_netlist(
        categories=("resistor", "capacitor"),
    )

    assert not are_isomorphic(predicted, ground_truth)


def test_different_topology_is_not_isomorphic():
    predicted = make_netlist()

    ground_truth = Netlist(
        components=[
            Component(
                id="R1",
                canonical_category="resistor",
                terminals=[
                    Terminal(name="1"),
                    Terminal(name="2"),
                ],
            ),
            Component(
                id="C1",
                canonical_category="capacitor",
                terminals=[
                    Terminal(name="1"),
                    Terminal(name="2"),
                ],
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

    assert not are_isomorphic(predicted, ground_truth)


def test_empty_pairs_return_none():
    assert graph_isomorphism_accuracy([]) is None


def test_accuracy_for_mixed_pairs():
    identical = make_netlist()
    different = make_netlist(categories=("resistor", "diode"))

    accuracy = graph_isomorphism_accuracy(
        [
            (identical, identical),
            (different, identical),
        ]
    )

    assert accuracy == 0.5

def test_multiple_terminals_on_same_net_are_preserved():
    predicted = Netlist(
        components=[
            Component(
                id="R1",
                canonical_category="resistor",
                terminals=[
                    Terminal(name="1"),
                    Terminal(name="2"),
                ],
            ),
            Component(
                id="C1",
                canonical_category="capacitor",
                terminals=[Terminal(name="1")],
            ),
        ],
        nets=[
            Net(
                name="N1",
                endpoints=[
                    NetEndpoint(component_id="R1", terminal_name="1"),
                    NetEndpoint(component_id="R1", terminal_name="2"),
                    NetEndpoint(component_id="C1", terminal_name="1"),
                ],
            )
        ],
    )

    ground_truth = Netlist(
        components=[
            Component(
                id="R1",
                canonical_category="resistor",
                terminals=[
                    Terminal(name="1"),
                    Terminal(name="2"),
                ],
            ),
            Component(
                id="C1",
                canonical_category="capacitor",
                terminals=[Terminal(name="1")],
            ),
        ],
        nets=[
            Net(
                name="N1",
                endpoints=[
                    NetEndpoint(component_id="R1", terminal_name="2"),
                    NetEndpoint(component_id="C1", terminal_name="1"),
                ],
            )
        ],
    )

    assert not are_isomorphic(predicted, ground_truth)