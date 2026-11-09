from pathlib import Path

import pytest

from vca.data.cghd import (
    DatasetGatedError,
    load_ltspice_asc,
    load_pascal_voc,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("approved", [False, True])
def test_load_pascal_voc_always_gated(approved):
    with pytest.raises(DatasetGatedError):
        load_pascal_voc(
            FIXTURES_DIR / "pascal_voc_sample.xml",
            approved=approved,
        )


@pytest.mark.parametrize("approved", [False, True])
def test_load_ltspice_asc_always_gated(approved):
    with pytest.raises(DatasetGatedError):
        load_ltspice_asc(
            FIXTURES_DIR / "ltspice_sample.asc",
            approved=approved,
        )