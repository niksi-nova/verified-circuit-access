
"""Property-based tests for netlist serialization."""

from hypothesis import given, settings
from hypothesis import strategies as st

from vca.schemas.netlist import (
    Component,
    Net,
    NetEndpoint,
    Netlist,
    Terminal,
)


@st.composite
def valid_netlists(draw):
    """Generate valid netlists with 0–20 components."""

    component_count = draw(
        st.integers(min_value=0, max_value=20)
    )

    components = []
    available_endpoints = []

    for index in range(component_count):
        terminal_count = draw(
            st.integers(min_value=1, max_value=4)
        )

        terminals = [
            Terminal(name=f"T{terminal_index}")
            for terminal_index in range(terminal_count)
        ]

        component = Component(
            id=f"C{index}",
            canonical_category=draw(
                st.sampled_from(
                    ["RESISTOR", "CAPACITOR", "DIODE", "TRANSISTOR"]
                )
            ),
            terminals=terminals,
        )

        components.append(component)

        for terminal in terminals:
            available_endpoints.append(
                (component.id, terminal.name)
            )

    # Shuffle endpoints and connect them in pairs.
    # Every endpoint is used at most once.
    shuffled_endpoints = draw(
        st.permutations(available_endpoints)
    )

    maximum_net_count = len(shuffled_endpoints) // 2

    net_count = draw(
        st.integers(
            min_value=0,
            max_value=maximum_net_count,
        )
    )

    nets = []

    for index in range(net_count):
        first_endpoint = shuffled_endpoints[2 * index]
        second_endpoint = shuffled_endpoints[2 * index + 1]

        nets.append(
            Net(
                name=f"N{index}",
                endpoints=[
                    NetEndpoint(
                        component_id=first_endpoint[0],
                        terminal_name=first_endpoint[1],
                    ),
                    NetEndpoint(
                        component_id=second_endpoint[0],
                        terminal_name=second_endpoint[1],
                    ),
                ],
            )
        )

    return Netlist(
        schema_version="1.0.0",
        components=components,
        nets=nets,
    )


# Feature: m1-data-audit-baseline, Property 1: Netlist round-trip
@given(netlist=valid_netlists())
@settings(max_examples=100)
def test_netlist_serialisation_round_trip(netlist: Netlist) -> None:
    """Serializing and deserializing a valid netlist preserves all fields."""

    serialized = netlist.model_dump_json()

    restored = Netlist.model_validate_json(serialized)

    assert restored.schema_version == netlist.schema_version
    assert restored.components == netlist.components
    assert restored.nets == netlist.nets
    assert restored == netlist
