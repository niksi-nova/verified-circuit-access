from pathlib import Path


class DatasetGatedError(RuntimeError):
    """Raised when access to a gated dataset is not permitted."""


def load_pascal_voc(
    path: Path,
    *,
    approved: bool = False,
):
    """CGHD PASCAL VOC loader stub for M1."""
    raise DatasetGatedError(
        "CGHD is gated and stub-only in M1. "
        "PASCAL VOC parsing is not implemented."
    )


def load_ltspice_asc(
    path: Path,
    *,
    approved: bool = False,
):
    """CGHD LTspice loader stub for M1."""
    raise DatasetGatedError(
        "CGHD is gated and stub-only in M1. "
        "LTspice parsing is not implemented."
    )