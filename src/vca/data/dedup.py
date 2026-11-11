"""Near-duplicate image detection, used to keep evaluation images out of
training sets.

Image2Net's detection set contains copies (exact and re-encoded) of some
validation circuits, so exact hashing alone is not enough. A 16x16
average hash is cheap and catches re-encodes and small rescales.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

import numpy as np
from PIL import Image

HASH_SIZE = 16


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def average_hash(path: Path, size: int = HASH_SIZE) -> np.ndarray:
    with Image.open(path) as image:
        pixels = np.asarray(image.convert("L").resize((size, size)), dtype=float)
    return (pixels > pixels.mean()).ravel()


def find_overlaps(
    candidates: Iterable[Path],
    references: Iterable[Path],
    max_distance: int = 10,
) -> dict[Path, tuple[Path, int]]:
    """Map each candidate that duplicates a reference to (reference, distance).

    Distance 0 with equal SHA-256 is an exact copy; otherwise it is the
    Hamming distance between average hashes.
    """
    references = list(references)
    if not references:
        return {}
    ref_sha = {sha256(p): p for p in references}
    ref_hashes = np.stack([average_hash(p) for p in references])

    overlaps: dict[Path, tuple[Path, int]] = {}
    for path in candidates:
        exact = ref_sha.get(sha256(path))
        if exact is not None:
            overlaps[path] = (exact, 0)
            continue
        distances = (ref_hashes != average_hash(path)).sum(axis=1)
        best = int(distances.argmin())
        if distances[best] <= max_distance:
            overlaps[path] = (references[best], int(distances[best]))
    return overlaps


def group_near_duplicates(paths: list[Path], max_distance: int = 10) -> list[int]:
    """Assign a group id to every path; near-duplicates share an id.

    Used before a random split so copies of one drawing land on the same side.
    """
    if not paths:
        return []
    hashes = np.stack([average_hash(p) for p in paths])
    parent = list(range(len(paths)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(paths)):
        distances = (hashes[i + 1 :] != hashes[i]).sum(axis=1)
        for offset in np.flatnonzero(distances <= max_distance):
            a, b = find(i), find(i + 1 + int(offset))
            if a != b:
                parent[b] = a
    return [find(i) for i in range(len(paths))]
