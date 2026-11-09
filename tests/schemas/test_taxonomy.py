from vca.schemas.taxonomy import TAXONOMY


def test_known_label_lookup():
    assert TAXONOMY.get_canonical("Image2Net", "resistor2_3") == (
        "resistor",
        24,
    )


def test_unknown_label_fallback():
    assert TAXONOMY.get_canonical("Image2Net", "not_a_label") == (
        "unknown",
        0,
    )


def test_canonical_ids_are_non_negative():
    for entry in TAXONOMY.entries:
        assert entry.canonical_id >= 0


def test_nonzero_canonical_ids_are_unique():
    nonzero_ids = [
        entry.canonical_id
        for entry in TAXONOMY.entries
        if entry.canonical_id != 0
    ]

    assert len(nonzero_ids) == len(set(nonzero_ids))


def test_every_source_label_is_accounted_for():
    source_labels = {
        "antenna",
        "capacitor",
        "capacitor-3",
        "cross-line-curved",
        "current",
        "diff-amp",
        "diode",
        "gnd",
        "inductor",
        "inductor-3",
        "nmos",
        "nmos-bulk",
        "nmos-cross",
        "npn",
        "npn-cross",
        "pmos",
        "pmos-bulk",
        "pmos-cross",
        "pnp",
        "pnp-cross",
        "port",
        "resistor",
        "resistor2",
        "resistor2_3",
        "single-end-amp",
        "single-input-single-end-amp",
        "switch",
        "switch-3",
        "vdd",
        "voltage",
        "voltage-lines",
    }

    represented_labels = {
        entry.source_label for entry in TAXONOMY.entries
    } | {
        entry.source_label for entry in TAXONOMY.unmapped_labels
    }

    assert source_labels <= represented_labels

def test_known_label_lookup_is_case_insensitive():
    assert TAXONOMY.get_canonical("Image2Net", "NMOS") == (
        "nmos",
        11,
    )