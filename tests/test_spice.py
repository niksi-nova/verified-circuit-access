import pytest

from vca.outputs.spice import SpiceRequest, available, simulate

pytestmark = pytest.mark.skipif(not available(), reason="ngspice is unavailable")


def request(parts, operation, reference="B", target="A"):
    components = []
    nets = {}
    values = {}
    for part_id, category, value, a, b in parts:
        terminals = {
            "voltage": ["Positive", "Negative"],
            "current": ["In", "Out"],
        }.get(category, ["A", "B"])
        components.append(
            {
                "id": part_id,
                "canonical_category": category,
                "terminals": [{"name": terminal} for terminal in terminals],
            }
        )
        for name, terminal in zip((a, b), terminals, strict=True):
            nets.setdefault(name, []).append(
                {
                    "component_id": part_id,
                    "terminal_name": terminal,
                }
            )
        values[part_id] = value
    return SpiceRequest.model_validate(
        {
            "netlist": {
                "components": components,
                "nets": [
                    {"name": name, "endpoints": ends} for name, ends in nets.items()
                ],
            },
            "values": values,
            "operation": operation,
            "reference": reference,
            "target": target,
        }
    )


def test_resistors_in_series():
    # 100 Ω + 220 Ω = 320 Ω.
    result = simulate(
        request(
            [
                ("R1", "resistor", 100, "A", "middle"),
                ("R2", "resistor", 220, "middle", "B"),
            ],
            "resistance",
        )
    )
    assert result["values"]["equivalent resistance"] == pytest.approx(320)


def test_resistors_in_parallel():
    # (1/100 Ω + 1/100 Ω)⁻¹ = 50 Ω.
    result = simulate(
        request(
            [
                ("R1", "resistor", 100, "A", "B"),
                ("R2", "resistor", 100, "A", "B"),
            ],
            "resistance",
        )
    )
    assert result["values"]["equivalent resistance"] == pytest.approx(50)


def test_voltage_divider():
    # 9 V × 200 Ω / (100 Ω + 200 Ω) = 6 V at middle.
    result = simulate(
        request(
            [
                ("V1", "voltage", 9, "A", "B"),
                ("R1", "resistor", 100, "A", "middle"),
                ("R2", "resistor", 200, "middle", "B"),
            ],
            "voltages",
        )
    )
    assert result["values"] == pytest.approx({"A": 9, "B": 0, "middle": 6})


def test_current_source_uses_in_to_out_polarity():
    # 0.02 A into 100 Ω makes the test net 2 V relative to B.
    result = simulate(
        request(
            [
                ("I1", "current", 0.02, "B", "A"),
                ("R1", "resistor", 100, "A", "B"),
            ],
            "voltages",
        )
    )
    assert result["values"]["A"] == pytest.approx(2)


def test_unsupported_component():
    with pytest.raises(ValueError, match="Not supported yet: diode"):
        simulate(request([("D1", "diode", 0, "A", "B")], "voltages"))
