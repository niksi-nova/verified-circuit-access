import json
from pathlib import Path

from vca.detect.classes import (
    DETECTOR_CLASSES,
    MASK,
    NETLIST_CATEGORY,
    from_cghd,
    from_image2net,
)
from vca.schemas.ports import CATEGORY_TERMINALS

TAXONOMY = Path(__file__).parents[2] / "src" / "vca" / "schemas" / "taxonomy.json"
# Golden-netlist-only names in the taxonomy, never detection labels.
GOLDEN_ONLY = {"Res", "Cap", "Diso_amp", "Dido_amp", "Siso_amp"}


def test_every_image2net_detection_label_maps():
    entries = json.loads(TAXONOMY.read_text())["entries"]
    labels = {e["source_label"] for e in entries if e["dataset_name"] == "Image2Net"}
    for label in labels - GOLDEN_ONLY:
        assert from_image2net(label) in DETECTOR_CLASSES


def test_style_variants_merge_but_body_terminal_variants_do_not():
    assert from_image2net("resistor2") == "resistor"
    assert from_image2net("nmos-cross") == "nmos"
    assert from_image2net("nmos-bulk") == "nmos-bulk"


def test_cghd_mapping():
    assert from_cghd("voltage.battery") == "voltage-lines"
    assert from_cghd("operational_amplifier") == "single-end-amp"
    assert from_cghd("text") is None
    assert from_cghd("transistor.bjt") == MASK  # polarity unknown
    assert from_cghd("never-seen") == MASK


def test_netlist_categories_are_schema_categories():
    assert set(NETLIST_CATEGORY) == set(DETECTOR_CLASSES)
    for category in NETLIST_CATEGORY.values():
        assert category is None or category in CATEGORY_TERMINALS
