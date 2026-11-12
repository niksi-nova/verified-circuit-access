import os

# Must run before ultralytics is imported anywhere in the test session:
# it reads this into a module-level constant at import time. Disables
# ultralytics' PIL.Image.open monkey-patch's `pip install` auto-update
# (a network call the API tests must never trigger). See
# src/vca/api/__init__.py for the same guard in the real process.
os.environ.setdefault("YOLO_AUTOINSTALL", "False")

from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402


def _pattern(path: Path, seed: int, size=(120, 80), fmt="PNG") -> Path:
    """Write a random black/white block image; same seed = same drawing."""
    rng = np.random.default_rng(seed)
    blocks = rng.integers(0, 2, (8, 12), dtype=np.uint8) * 255
    Image.fromarray(blocks).resize(size, Image.NEAREST).save(path, fmt)
    return path


@pytest.fixture
def pattern():
    return _pattern
