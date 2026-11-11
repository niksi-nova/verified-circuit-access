"""Where each terminal sits on a detected symbol.

Terminal positions are given as normalised box coordinates (x, y in [0, 1],
origin top-left) in the "l" frame of the Image2Net orientation dataset, then
rotated to the predicted orientation.

Orientation classes (checked on the dataset; the four classes of one crop
are exact rotations of each other):

- ``l``: the symbol faces left (MOS gate / BJT base / diode cathode /
  amplifier output / battery long plate on the left).
- ``d`` = ``l`` rotated 90 deg counter-clockwise, ``r`` = 180 deg,
  ``u`` = 90 deg clockwise.

Mirroring (``bjt_m``, ``amp_m``) flips the symbol across its facing axis,
which is ``y -> 1 - y`` in the ``l`` frame. Mirror 0 of a BJT has the emitter
(arrow) on top; mirror 0 of an op-amp has the + input on top in the ``l``
frame (left when the output points down).

Where no classifier exists or none is given, drawing conventions are used:
NMOS drain / PMOS source on top, NPN emitter at the bottom, PNP emitter on
top. These are guesses and are reported as such (``orientation_source``).
"""

from __future__ import annotations

from dataclasses import dataclass

ORIENTATIONS = ("l", "d", "r", "u")

Point = tuple[float, float]

# Anchors in the "l" frame, mirror 0.
_ANCHORS: dict[str, dict[str, Point]] = {
    "nmos": {"Gate": (0, 0.5), "Drain": (1, 0), "Source": (1, 1), "Body": (1, 0.5)},
    "pmos": {"Gate": (0, 0.5), "Source": (1, 0), "Drain": (1, 1), "Body": (1, 0.5)},
    "npn": {"Base": (0, 0.5), "Emitter": (1, 0), "Collector": (1, 1)},
    "pnp": {"Base": (0, 0.5), "Emitter": (1, 0), "Collector": (1, 1)},
    "diode": {"Out": (0, 0.5), "In": (1, 0.5)},
    "current": {"Out": (0, 0.5), "In": (1, 0.5)},
    "voltage": {"Positive": (0, 0.5), "Negative": (1, 0.5)},
    "resistor": {"Pos": (0, 0.5), "Neg": (1, 0.5)},
    "capacitor": {"Pos": (0, 0.5), "Neg": (1, 0.5)},
    "inductor": {"Pos": (0, 0.5), "Neg": (1, 0.5)},
    "switch": {"Pos": (0, 0.5), "Neg": (1, 0.5)},
    "diff-amp": {"Out": (0, 0.5), "InP": (1, 0.25), "InN": (1, 0.75)},
    "differential-amplifier": {
        "OutP": (0, 0.25),
        "OutN": (0, 0.75),
        "InP": (1, 0.25),
        "InN": (1, 0.75),
    },
    "single-input-single-end-amp": {"Out": (0, 0.5), "In": (1, 0.5)},
}

# Detector classes whose symbol has no drawn body terminal.
_NO_BODY = {"nmos", "pmos"}

# Categories with no orientation classifier: the axis comes from the box shape.
_AXIS_FROM_SHAPE = {"resistor", "capacitor", "inductor", "switch"}
_DEFAULT_ORIENTATION = {
    "nmos": "l",
    "pmos": "l",
    "npn": "l",
    "pnp": "l",
    "diode": "d",
    "current": "d",  # arrow down: current enters at the top
    "voltage": "u",  # + on top
    "diff-amp": "r",
    "differential-amplifier": "r",
    "single-input-single-end-amp": "r",
}
# Mirror by convention when not predicted (True = flip y in the l frame).
_DEFAULT_MIRROR = {"npn": True, "pnp": False}


def rotate(point: Point, orientation: str) -> Point:
    """Map an "l"-frame point to the given orientation's frame."""
    x, y = point
    if orientation == "l":
        return (x, y)
    if orientation == "d":
        return (y, 1 - x)
    if orientation == "r":
        return (1 - x, 1 - y)
    if orientation == "u":
        return (1 - y, x)
    raise ValueError(f"unknown orientation {orientation!r}")


@dataclass(frozen=True)
class TerminalLayout:
    category: str
    anchors: dict[str, Point]  # terminal -> normalised (x, y) in the box
    orientation: str
    mirrored: bool
    orientation_source: str  # "predicted", "box_shape" or "default"
    mirror_source: str  # "predicted", "convention" or "n/a"


def terminal_layout(
    detector_class: str,
    category: str,
    box: tuple[float, float, float, float],
    orientation: str | None = None,
    mirrored: bool | None = None,
) -> TerminalLayout:
    """Terminal anchors of one detection, in its box's normalised frame."""
    anchors = dict(_ANCHORS[category])
    if detector_class in _NO_BODY:
        anchors.pop("Body", None)

    if orientation is not None:
        if orientation not in ORIENTATIONS:
            raise ValueError(f"unknown orientation {orientation!r}")
        orientation_source = "predicted"
    elif category in _AXIS_FROM_SHAPE or category == "voltage":
        x1, y1, x2, y2 = box
        wide = (x2 - x1) >= (y2 - y1)
        orientation = "l" if wide else ("u" if category == "voltage" else "d")
        orientation_source = "box_shape"
    else:
        orientation = _DEFAULT_ORIENTATION[category]
        orientation_source = "default"

    if mirrored is not None:
        mirror_source = "predicted"
    elif category in ("nmos", "pmos", "npn", "pnp"):
        # Convention is about the drawing as seen (drain / emitter position),
        # so a symbol facing right keeps it by mirroring the 180 deg rotation.
        mirrored = _DEFAULT_MIRROR.get(category, False) ^ (orientation == "r")
        mirror_source = "convention"
    else:
        mirrored = False
        mirror_source = "n/a" if len(anchors) == 2 else "convention"

    placed = {}
    for name, (x, y) in anchors.items():
        if mirrored:
            y = 1 - y
        placed[name] = rotate((x, y), orientation)
    return TerminalLayout(
        category=category,
        anchors=placed,
        orientation=orientation,
        mirrored=mirrored,
        orientation_source=orientation_source,
        mirror_source=mirror_source,
    )
