import pytest
from pydantic import ValidationError

from vca.schemas.netlist import (
    Component,
    Netlist,
    Terminal,
)


@pytest.fixture
def valid_netlist_data():
    return {
        "components": [
            {
                "id": "R1",
                "canonical_category": "resistor",
                "terminals": [{"name": "1"}, {"name": "2"}],
            },
            {
                "id": "V1",
                "canonical_category": "voltage_source",
                "terminals": [{"name": "POS"}, {"name": "NEG"}],
            },
        ],
        "nets": [
            {
                "name": "GND",
                "endpoints": [
                    {"component_id": "R1", "terminal_name": "2"},
                    {"component_id": "V1", "terminal_name": "NEG"},
                ],
            },
        ],
    }


def test_valid_netlist(valid_netlist_data):
    netlist = Netlist(**valid_netlist_data)

    assert len(netlist.components) == 2
    assert len(netlist.nets) == 1


def test_missing_components_field():
    with pytest.raises(ValidationError):
        Netlist(nets=[])


def test_duplicate_component_id(valid_netlist_data):
    valid_netlist_data["components"].append(
        {
            "id": "R1",
            "canonical_category": "capacitor",
            "terminals": [{"name": "1"}, {"name": "2"}],
        }
    )

    with pytest.raises(ValidationError, match="R1"):
        Netlist(**valid_netlist_data)


def test_unknown_component_reference(valid_netlist_data):
    valid_netlist_data["nets"][0]["endpoints"][0]["component_id"] = "UNKNOWN"

    with pytest.raises(ValidationError, match="UNKNOWN"):
        Netlist(**valid_netlist_data)


def test_unknown_terminal_reference(valid_netlist_data):
    valid_netlist_data["nets"][0]["endpoints"][0]["terminal_name"] = "UNKNOWN"

    with pytest.raises(ValidationError, match="UNKNOWN"):
        Netlist(**valid_netlist_data)


def test_schema_version_default(valid_netlist_data):
    netlist = Netlist(**valid_netlist_data)

    assert netlist.schema_version == "1.0.0"


def test_invalid_terminal_name():
    with pytest.raises(ValidationError):
        Terminal(name="terminal!")


def test_duplicate_terminal_names():
    with pytest.raises(ValidationError, match="duplicate terminal"):
        Component(
            id="R1",
            canonical_category="resistor",
            terminals=[Terminal(name="1"), Terminal(name="1")],
        )


def test_duplicate_endpoints_within_net(valid_netlist_data):
    valid_netlist_data["nets"][0]["endpoints"].append(
        {"component_id": "R1", "terminal_name": "2"}
    )

    with pytest.raises(ValidationError, match="duplicate endpoints"):
        Netlist(**valid_netlist_data)


def test_endpoint_reused_across_nets(valid_netlist_data):
    valid_netlist_data["nets"].append(
        {
            "name": "NET2",
            "endpoints": [
                {"component_id": "R1", "terminal_name": "2"},
                {"component_id": "V1", "terminal_name": "POS"},
            ],
        }
    )

    with pytest.raises(ValidationError, match="both net"):
        Netlist(**valid_netlist_data)


def test_duplicate_net_names(valid_netlist_data):
    valid_netlist_data["nets"].append(
        {
            "name": "GND",
            "endpoints": [
                {"component_id": "R1", "terminal_name": "1"},
                {"component_id": "V1", "terminal_name": "POS"},
            ],
        }
    )

    with pytest.raises(ValidationError, match="Duplicate net name"):
        Netlist(**valid_netlist_data)