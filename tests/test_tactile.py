from xml.etree import ElementTree

import pytest

from vca.outputs.tactile import render
from vca.schemas.netlist import Netlist


def graph():
    return Netlist.model_validate(
        {
            "components": [
                {
                    "id": f"R{i}",
                    "canonical_category": "resistor",
                    "terminals": [{"name": "Pos"}, {"name": "Neg"}],
                    "bbox": {"x": x, "y": 10, "width": 20, "height": 10},
                }
                for i, x in enumerate((5, 60), 1)
            ],
            "nets": [
                {
                    "name": "N1",
                    "endpoints": [
                        {"component_id": "R1", "terminal_name": "Neg"},
                        {"component_id": "R2", "terminal_name": "Pos"},
                    ],
                }
            ],
        }
    )


def test_vector_only_orthogonal_diagram_with_letter_dimensions():
    output = render(graph(), (100, 50), [], page="Letter", thickness=1.5)
    svg = ElementTree.fromstring(output["svg"])
    assert output["kind"] == "diagram"
    assert (svg.attrib["width"], svg.attrib["height"]) == ("215.9mm", "279.4mm")
    assert svg.find(".//{*}g").attrib["stroke-width"] == "1.5"
    assert svg.find(".//{*}image") is None
    wire = svg.find(".//{*}polyline")
    points = [point.split(",") for point in wire.attrib["points"].split()]
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:]))


def test_missing_image_geometry_gets_a_labelled_terminal_listing():
    output = render(graph(), None, [])
    assert output["kind"] == "connections"
    assert "Parts and connections" in output["svg"]
    assert "R1.Neg, R2.Pos" in output["svg"]
    assert "<polyline" not in output["svg"]


def test_line_thickness_out_of_range_is_rejected():
    with pytest.raises(ValueError, match="thickness"):
        render(graph(), (100, 50), [], thickness=0)
