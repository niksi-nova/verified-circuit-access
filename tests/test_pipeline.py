from PIL import Image, ImageDraw

from vca.netting.extract import Crossing, Detection
from vca.pipeline import Pipeline


def drawing():
    """R1 -- R2 and R3 | R4 crossing without a dot, plus a GND under R4."""
    image = Image.new("RGB", (420, 470), "white")
    draw = ImageDraw.Draw(image)
    boxes = [
        (20, 190, 80, 230),
        (340, 190, 400, 230),
        (190, 20, 230, 80),
        (190, 340, 230, 400),
    ]
    for box in boxes:
        draw.rectangle(box, outline="black", width=3)
    draw.line((80, 210, 340, 210), fill="black", width=3)
    draw.line((210, 80, 210, 340), fill="black", width=3)
    draw.line((210, 400, 210, 440), fill="black", width=3)
    draw.line((190, 442, 230, 442), fill="black", width=3)
    dets = [Detection("resistor", b, 0.9) for b in boxes]
    dets.append(Detection("gnd", (185, 436, 235, 460), 0.8))
    return image, dets


def test_pipeline_threads_every_stage():
    image, dets = drawing()
    calls = []

    def classify(crop, task):
        calls.append(task)
        return "l", 0.7

    result = Pipeline(
        detect=lambda img: dets,
        crossings=lambda img: [Crossing("dot_junction", (195, 195, 225, 225), 0.6)],
        classify=classify,
    )(image)

    # The crossing model says "junction": all four resistors meet in one net.
    assert {n.name for n in result.netlist.nets} == {"net1", "GND"}
    assert calls == []  # resistors have no orientation classifier
    rows = result.component_features
    assert [r["detector_score"] for r in rows] == [0.9] * 4
    assert rows[3]["orientation_source"] == "box_shape"
    assert result.rules.circuit["no_ground"] == 0
    assert result.rules.circuit["no_supply"] == 1


def test_pipeline_without_crossing_model_cuts_plain_crossings():
    image, dets = drawing()
    result = Pipeline(detect=lambda img: dets)(image)
    assert len(result.netlist.nets) == 3  # two wires + GND
