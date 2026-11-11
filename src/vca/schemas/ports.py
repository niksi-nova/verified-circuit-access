"""Terminal-name conventions per canonical category.

Taken from Image2Net's golden netlists and the port order table in the
official ``validation/utils_ged.py``. Shared by the VLM baseline prompt and,
in M2, by the detector-to-netlist stage.
"""

CATEGORY_TERMINALS: dict[str, tuple[str, ...]] = {
    "nmos": ("Drain", "Gate", "Source", "Body"),
    "pmos": ("Drain", "Gate", "Source", "Body"),
    "npn": ("Collector", "Base", "Emitter"),
    "pnp": ("Collector", "Base", "Emitter"),
    "resistor": ("Pos", "Neg"),
    "capacitor": ("Pos", "Neg"),
    "inductor": ("Pos", "Neg"),
    "switch": ("Pos", "Neg"),
    "diode": ("In", "Out"),
    "current": ("In", "Out"),
    "voltage": ("Positive", "Negative"),
    "diff-amp": ("InP", "InN", "Out"),
    "differential-amplifier": ("InP", "InN", "OutP", "OutN"),
    "single-input-single-end-amp": ("In", "Out"),
}

# Terminals a component may legitimately leave out (3-terminal MOS symbols).
OPTIONAL_TERMINALS: dict[str, frozenset[str]] = {
    "nmos": frozenset({"Body"}),
    "pmos": frozenset({"Body"}),
}

ALL_TERMINAL_NAMES: tuple[str, ...] = tuple(
    sorted({name for names in CATEGORY_TERMINALS.values() for name in names})
)
