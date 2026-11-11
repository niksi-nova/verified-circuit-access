"""Detector class set shared by Image2Net and CGHD.

The detector predicts Image2Net's drawing-level classes, because the
evaluation circuits are Image2Net's. Variants that only differ in drawing
style (``resistor2`` box resistors, ``nmos-cross`` arrow MOS symbols, ``-3``
variants) are merged; variants that change the terminal set (``*-bulk``
MOS with a body terminal) are kept apart.

CGHD labels map onto this set where the symbol means the same thing.
CGHD symbols with no counterpart (logic gates, lamps, BJTs and FETs whose
polarity is not labelled, ...) are returned as ``MASK``: the dataset
builder paints them out so the detector is not taught that a real symbol
is background. Text, junction dots and wire crossings are unlabelled in
Image2Net's detection set too, so they stay as ordinary background.
"""

from __future__ import annotations

from typing import Final

MASK: Final = "__mask__"
BACKGROUND: Final = None

DETECTOR_CLASSES: Final[tuple[str, ...]] = (
    "nmos",
    "nmos-bulk",
    "pmos",
    "pmos-bulk",
    "npn",
    "pnp",
    "resistor",
    "capacitor",
    "inductor",
    "diode",
    "current",
    "voltage",
    "voltage-lines",  # battery symbol
    "switch",
    "single-end-amp",  # op-amp: differential in, single-ended out
    "diff-amp",  # fully differential amplifier
    "single-input-single-end-amp",  # buffer triangle
    "port",
    "gnd",
    "vdd",
    "cross-line-curved",  # wire hop: crossing without connection
    "antenna",
)
CLASS_INDEX: Final = {name: i for i, name in enumerate(DETECTOR_CLASSES)}

_IMAGE2NET_ALIASES: Final = {
    "nmos-cross": "nmos",
    "pmos-cross": "pmos",
    "npn-cross": "npn",
    "pnp-cross": "pnp",
    "resistor2": "resistor",
    "resistor2_3": "resistor",
    "capacitor-3": "capacitor",
    "inductor-3": "inductor",
    "switch-3": "switch",
}

_CGHD_MAP: Final[dict[str, str | None]] = {
    "text": BACKGROUND,
    "junction": BACKGROUND,
    "crossover": BACKGROUND,
    "terminal": "port",
    "gnd": "gnd",
    "voltage.dc": "voltage",
    "voltage.ac": "voltage",
    "voltage.battery": "voltage-lines",
    "resistor": "resistor",
    "capacitor.unpolarized": "capacitor",
    "capacitor.polarized": "capacitor",
    "inductor": "inductor",
    "diode": "diode",
    "operational_amplifier": "single-end-amp",
    "switch": "switch",
    "antenna": "antenna",
}

# Detector class -> netlist category (vca.schemas.ports). None: the symbol
# is not a netlist component (rails, ports, hops are nets or wiring).
NETLIST_CATEGORY: Final[dict[str, str | None]] = {
    "nmos": "nmos",
    "nmos-bulk": "nmos",
    "pmos": "pmos",
    "pmos-bulk": "pmos",
    "npn": "npn",
    "pnp": "pnp",
    "resistor": "resistor",
    "capacitor": "capacitor",
    "inductor": "inductor",
    "diode": "diode",
    "current": "current",
    "voltage": "voltage",
    "voltage-lines": "voltage",
    "switch": "switch",
    "single-end-amp": "diff-amp",
    "diff-amp": "differential-amplifier",
    "single-input-single-end-amp": "single-input-single-end-amp",
    "port": None,
    "gnd": None,
    "vdd": None,
    "cross-line-curved": None,
    "antenna": None,
}


def from_image2net(label: str) -> str:
    """Detector class for an Image2Net detection label (KeyError if unknown)."""
    name = _IMAGE2NET_ALIASES.get(label, label)
    if name not in CLASS_INDEX:
        raise KeyError(f"Unknown Image2Net detection label: {label!r}")
    return name


def from_cghd(label: str) -> str | None:
    """Detector class, ``None`` for background, or ``MASK`` to paint out."""
    return _CGHD_MAP.get(label, MASK)
