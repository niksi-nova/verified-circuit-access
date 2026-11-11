from pathlib import Path

import numpy as np
import pytest
from PIL import Image


def _pattern(path: Path, seed: int, size=(120, 80), fmt="PNG") -> Path:
    """Write a random black/white block image; same seed = same drawing."""
    rng = np.random.default_rng(seed)
    blocks = rng.integers(0, 2, (8, 12), dtype=np.uint8) * 255
    Image.fromarray(blocks).resize(size, Image.NEAREST).save(path, fmt)
    return path


@pytest.fixture
def pattern():
    return _pattern
