"""Plain-English names for the canonical categories in taxonomy.json.

Only categories that actually appear in ``taxonomy.json`` get a name here.
Anything else (a future category, a typo) falls back to a raw-name sentence
rather than silently mislabelling a part.
"""

from __future__ import annotations

PLAIN_NAMES: dict[str, str] = {
    "antenna": "antenna",
    "capacitor": "capacitor",
    "cross-line-curved": "curved wire crossing",
    "current": "current source",
    "diff-amp": "differential amplifier (single-ended output)",
    "diode": "diode",
    "ground": "ground symbol",
    "inductor": "inductor",
    "nmos": "N-channel transistor",
    "npn": "NPN transistor",
    "pmos": "P-channel transistor",
    "pnp": "PNP transistor",
    "port": "port",
    "resistor": "resistor",
    "single-end-amp": "single-ended amplifier",
    "single-input-single-end-amp": "single-input amplifier",
    "switch": "switch",
    "vdd": "supply symbol",
    "voltage": "voltage source",
    "voltage-lines": "voltage source (multi-line)",
    "differential-amplifier": "differential amplifier",
}


def plain_name(canonical_category: str) -> str:
    return PLAIN_NAMES.get(
        canonical_category, f"component of type {canonical_category}"
    )
