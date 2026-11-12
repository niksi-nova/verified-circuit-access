"""Test-only: build_circuit_record determinism and validation."""

import copy

from vca.explain.build import build_circuit_record, validate_record

PREDICTION = {
    "image": "001.png",
    "netlist": {
        "components": [
            {
                "id": "C1",
                "canonical_category": "resistor",
                "terminals": [{"name": "Pos"}, {"name": "Neg"}],
                "bbox": {"x": 0, "y": 0, "width": 20, "height": 20},
            },
            {
                "id": "C2",
                "canonical_category": "resistor",
                "terminals": [{"name": "Pos"}, {"name": "Neg"}],
                "bbox": {"x": 50, "y": 0, "width": 20, "height": 20},
            },
        ],
        "nets": [
            {
                "name": "VDD",
                "endpoints": [{"component_id": "C1", "terminal_name": "Pos"}],
            },
            {
                "name": "junction",
                "endpoints": [
                    {"component_id": "C1", "terminal_name": "Neg"},
                    {"component_id": "C2", "terminal_name": "Pos"},
                ],
            },
            {
                "name": "GND",
                "endpoints": [{"component_id": "C2", "terminal_name": "Neg"}],
            },
        ],
    },
    "components": [
        {"component_id": "C1", "category": "resistor", "rules": []},
        {"component_id": "C2", "category": "resistor", "rules": ["floating_terminal"]},
    ],
    "rules": {
        "unconnected_terminal": 0,
        "floating_terminal": 1,
        "shorted_two_terminal": 0,
        "shorted_source": 0,
        "drain_source_short": 0,
        "collector_emitter_short": 0,
        "extra_contacts": 0,
        "no_ground": 0,
        "no_supply": 0,
        "rail_conflict": 0,
        "isolated_component": 0,
    },
    "crossings_cut": 0,
    "score": {
        "circuit_id": "001",
        "ned": 0.0,
        "ned_lower_bound": 0.0,
        "graph_isomorphism": True,
        "connection_precision": 1.0,
        "connection_recall": 1.0,
        "errors": [],
    },
}


def test_build_is_deterministic():
    first = build_circuit_record(
        copy.deepcopy(PREDICTION), {"C2": 0.1}, "note text", (640, 480)
    )
    second = build_circuit_record(
        copy.deepcopy(PREDICTION), {"C2": 0.1}, "note text", (640, 480)
    )
    assert first == second


def test_build_passes_validation():
    record = build_circuit_record(
        copy.deepcopy(PREDICTION), {"C2": 0.1}, "note text", (640, 480)
    )
    assert validate_record(record) == []


def test_evaluation_block_copied_not_recomputed():
    record = build_circuit_record(copy.deepcopy(PREDICTION), {}, "note text", None)
    assert record["evaluation"]["evaluation_only"] is True
    assert record["evaluation"]["ned"] == 0.0
    assert record["evaluation"]["true_error_count"] == 0


def test_series_block_found_between_the_two_resistors():
    record = build_circuit_record(copy.deepcopy(PREDICTION), {}, "note text", None)
    component_groups = [s["components"] for s in record["explanation"]["layer2_blocks"]]
    assert ["C1", "C2"] in component_groups
