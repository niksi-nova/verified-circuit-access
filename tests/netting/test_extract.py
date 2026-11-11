import numpy as np
import pytest
from PIL import Image, ImageDraw

from vca.netting.extract import (
    Crossing,
    Detection,
    binarize,
    extract_netlist,
    find_through_lines,
    line_width,
)
from vca.netting.terminals import rotate, terminal_layout

W = 3  # stroke width of the synthetic drawings


def canvas(size=(400, 300)):
    image = Image.new("RGB", size, "white")
    return image, ImageDraw.Draw(image)


def resistor(draw, box):
    """A box resistor; returns its detection."""
    draw.rectangle(box, outline="black", width=W)
    return Detection("resistor", box)


def wire(draw, *points):
    draw.line(points, fill="black", width=W)


def nets_of(result):
    """{frozenset of (component, terminal)} for each net."""
    return {
        frozenset((e.component_id, e.terminal_name) for e in net.endpoints)
        for net in result.netlist.nets
    }


def test_binarize_and_stroke_width():
    image, draw = canvas()
    wire(draw, (10, 10), (300, 10))
    wire(draw, (10, 50), (10, 250))
    ink = binarize(image)
    assert ink[10, 100] and not ink[100, 100]
    assert line_width(ink) == pytest.approx(W, abs=1)


@pytest.mark.parametrize("orientation,k", [("d", 1), ("r", 2), ("u", 3)])
def test_rotation_matches_image_rotation(orientation, k):
    grid = np.zeros((11, 11))
    for x, y in ((0, 5), (10, 0), (10, 10), (3, 7)):
        grid[:] = 0
        grid[y, x] = 1
        ry, rx = np.argwhere(np.rot90(grid, k))[0]
        assert rotate((x / 10, y / 10), orientation) == pytest.approx(
            (rx / 10, ry / 10)
        )


def test_mos_conventions():
    box = (0, 0, 10, 10)
    left = terminal_layout("nmos", "nmos", box, "l").anchors
    assert left == {"Gate": (0, 0.5), "Drain": (1, 0), "Source": (1, 1)}
    # Facing right keeps the drain on top by convention.
    right = terminal_layout("nmos", "nmos", box, "r")
    assert right.anchors["Gate"] == (1, 0.5) and right.anchors["Drain"][1] == 0
    assert right.mirror_source == "convention"
    assert "Body" in terminal_layout("pmos-bulk", "pmos", box, "l").anchors


def test_series_resistors_between_rails():
    image, draw = canvas()
    r1 = resistor(draw, (100, 40, 140, 100))
    r2 = resistor(draw, (100, 160, 140, 220))
    wire(draw, (120, 10), (120, 40))  # VDD - R1
    wire(draw, (120, 100), (120, 160))  # R1 - R2
    wire(draw, (120, 220), (120, 270))  # R2 - GND
    wire(draw, (120, 130), (250, 130))  # output tap
    draw.line((100, 8, 140, 8), fill="black", width=W)  # vdd bar
    draw.line((100, 272, 140, 272), fill="black", width=W)  # gnd bar
    draw.text((150, 60), "R1", fill="black")  # designator, not a wire
    result = extract_netlist(
        image,
        [
            r1,
            r2,
            Detection("vdd", (95, 0, 145, 12)),
            Detection("gnd", (95, 268, 145, 290)),
        ],
    )

    assert {n.name for n in result.netlist.nets} == {"VDD", "GND", "net1"}
    by_net = {
        n.name: {(e.component_id, e.terminal_name) for e in n.endpoints}
        for n in result.netlist.nets
    }
    assert by_net["VDD"] == {("C1", "Neg")}
    assert by_net["net1"] == {("C1", "Pos"), ("C2", "Neg")}
    assert by_net["GND"] == {("C2", "Pos")}
    assert all(not r.unconnected_terminals for r in result.components)


def crossing_drawing(dot: bool):
    """R1 -- R2 horizontally, R3 | R4 vertically, the wires cross mid-way."""
    image, draw = canvas((420, 420))
    dets = [
        resistor(draw, (20, 190, 80, 230)),
        resistor(draw, (340, 190, 400, 230)),
        resistor(draw, (190, 20, 230, 80)),
        resistor(draw, (190, 340, 230, 400)),
    ]
    wire(draw, (80, 210), (340, 210))
    wire(draw, (210, 80), (210, 340))
    if dot:
        draw.ellipse((202, 202, 218, 218), fill="black")
    return image, dets


def test_plain_crossing_is_not_a_connection():
    image, dets = crossing_drawing(dot=False)
    result = extract_netlist(image, dets)
    assert nets_of(result) == {
        frozenset({("C1", "Neg"), ("C2", "Pos")}),
        frozenset({("C3", "Pos"), ("C4", "Neg")}),
    }
    assert result.crossings_cut == 1


def test_dotted_crossing_is_a_connection():
    image, dets = crossing_drawing(dot=True)
    result = extract_netlist(image, dets)
    assert frozenset(
        {("C1", "Neg"), ("C2", "Pos"), ("C3", "Pos"), ("C4", "Neg")}
    ) in nets_of(result)


def test_crossing_model_overrides_the_image_heuristic():
    image, dets = crossing_drawing(dot=False)
    joined = extract_netlist(
        image, dets, [Crossing("dot_junction", (195, 195, 225, 225))]
    )
    assert len(joined.netlist.nets) == 1
    image, dets = crossing_drawing(dot=True)
    hopped = extract_netlist(image, dets, [Crossing("hop", (195, 195, 225, 225))])
    assert len(hopped.netlist.nets) == 2


def test_mos_terminals_follow_the_wires():
    image, draw = canvas((300, 300))
    draw.rectangle((120, 110, 170, 190), outline="black", width=W)
    wire(draw, (40, 150), (120, 150))  # gate from the left
    wire(draw, (170, 112), (260, 112))  # top right: drain
    wire(draw, (170, 188), (260, 188))  # bottom right: source
    wire(draw, (40, 150), (40, 40), (260, 40), (260, 112))  # gate tied to drain
    result = extract_netlist(image, [Detection("nmos", (120, 110, 170, 190))])
    (report,) = result.components
    assert report.terminal_nets["Gate"] == report.terminal_nets["Drain"]
    assert report.terminal_nets["Source"] != report.terminal_nets["Drain"]
    assert result.single_terminal_nets == [report.terminal_nets["Source"]]


def mos_strokes(draw, box):
    """Gate plate, channel and drain/source stubs of a MOS symbol (gate right)."""
    x1, y1, x2, y2 = box
    wire(draw, (x2 - 15, y1 + 15), (x2 - 15, y2 - 15))  # gate plate
    wire(draw, (x2 - 30, y1 + 10), (x2 - 30, y2 - 10))  # channel
    wire(draw, (x1, y1 + 10), (x2 - 30, y1 + 10))  # drain stub
    wire(draw, (x1, y2 - 10), (x2 - 30, y2 - 10))  # source stub


def test_symbol_strokes_are_not_a_through_line():
    image, draw = canvas()
    box = (150, 100, 230, 180)
    mos_strokes(draw, box)
    assert find_through_lines(binarize(image), box, W) == []


def test_bus_drawn_through_a_transistor_stays_one_net():
    image, draw = canvas()
    box = (150, 100, 230, 180)
    mos_strokes(draw, box)
    left = resistor(draw, (20, 125, 50, 155))
    right = resistor(draw, (350, 125, 380, 155))
    wire(draw, (50, 140), (350, 140))  # gate bus straight through the symbol
    ink = binarize(image)
    assert find_through_lines(ink, box, W) == [("row", 140)]

    mos = Detection("nmos", box, orientation="r")
    result = extract_netlist(image, [left, mos, right], detect_plain_crossings=False)
    assert frozenset({("C1", "Neg"), ("C2", "Gate"), ("C3", "Pos")}) in nets_of(result)
