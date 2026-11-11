import numpy as np
from PIL import Image

from vca.netting.extract import Detection
from vca.netting.orient import orient, to_frame


def marked(orientation_turns: int) -> Image.Image:
    """10x10 image with one dark pixel at the left middle, then rotated."""
    a = np.full((10, 10, 3), 255, dtype=np.uint8)
    a[5, 0] = 0
    return Image.fromarray(np.rot90(a, orientation_turns))


def dark(image: Image.Image) -> tuple[int, int]:
    y, x = np.argwhere(np.asarray(image)[:, :, 0] == 0)[0]
    return int(x), int(y)


def test_to_frame_undoes_rotation():
    for turns, orientation in enumerate("ldru"):
        assert dark(to_frame(marked(turns), orientation, "l")) == (0, 5)
    # The amplifier mirror frame faces down: the left-middle mark goes bottom.
    assert dark(to_frame(marked(0), "l", "d"))[1] == 9


def test_orient_classifies_rotation_then_mirror_in_its_frame():
    seen = []

    def classify(crop, task):
        seen.append((task, crop.size))
        return ("r", 0.9) if task == "bjt_d" else ("1", 0.8)

    image = Image.new("RGB", (100, 100), "white")
    dets = [
        Detection("npn", (10, 10, 50, 30)),
        Detection("resistor", (60, 60, 90, 70)),
    ]
    out, scores = orient(image, dets, classify, margin=0)
    assert out[0].orientation == "r" and out[0].mirrored is True
    assert out[1] == dets[1] and scores[1] == {}
    assert seen == [("bjt_d", (40, 20)), ("bjt_m", (40, 20))]
