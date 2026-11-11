"""Orientation and mirroring of detected symbols from the M2 classifiers.

Rotation is predicted on the crop as found. Mirroring is predicted on the
crop turned to the frame the mirror dataset was drawn in (BJT: base left,
the "l" frame; amplifiers: output down, the "d" frame), as in Image2Net.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image

from vca.netting.extract import Detection

# Detector class -> (rotation task, mirror task, mirror frame).
TASKS: dict[str, tuple[str, str | None, str | None]] = {
    "nmos": ("mos", None, None),
    "nmos-bulk": ("mos", None, None),
    "pmos": ("mos", None, None),
    "pmos-bulk": ("mos", None, None),
    "npn": ("bjt_d", "bjt_m", "l"),
    "pnp": ("bjt_d", "bjt_m", "l"),
    "diode": ("diode", None, None),
    "voltage-lines": ("voltagelines", None, None),
    "single-end-amp": ("amp_d", "amp_m", "d"),
    "diff-amp": ("amp_d", "amp_m", "d"),
    "single-input-single-end-amp": ("amp_d", None, None),
}

# np.rot90 turns that map an "l"-frame crop to each orientation.
_TURNS = {"l": 0, "d": 1, "r": 2, "u": 3}

# (image, task) -> (label, probability)
Classifier = Callable[[Image.Image, str], tuple[str, float]]


def to_frame(crop: Image.Image, orientation: str, frame: str) -> Image.Image:
    """Turn a crop seen in ``orientation`` so it is seen in ``frame``."""
    turns = (_TURNS[frame] - _TURNS[orientation]) % 4
    return Image.fromarray(np.rot90(np.asarray(crop), turns))


def orient(
    image: Image.Image,
    detections: list[Detection],
    classify: Classifier,
    margin: float = 0.05,
) -> tuple[list[Detection], list[dict]]:
    """Fill in ``orientation``/``mirrored``; also return per-detection scores."""
    rgb = image.convert("RGB")
    out, scores = [], []
    for d in detections:
        task = TASKS.get(d.detector_class)
        if task is None:
            out.append(d)
            scores.append({})
            continue
        rotation_task, mirror_task, frame = task
        x1, y1, x2, y2 = d.box
        mx, my = (x2 - x1) * margin, (y2 - y1) * margin
        crop = rgb.crop((x1 - mx, y1 - my, x2 + mx, y2 + my))
        orientation, p_rot = classify(crop, rotation_task)
        info = {"orientation": orientation, "orientation_p": p_rot}
        mirrored = None
        if mirror_task:
            label, p_mirror = classify(to_frame(crop, orientation, frame), mirror_task)
            mirrored = label == "1"
            info.update(mirrored=mirrored, mirrored_p=p_mirror)
        out.append(replace(d, orientation=orientation, mirrored=mirrored))
        scores.append(info)
    return out, scores


class YoloClassifiers:
    """Classifier backed by the trained ``orientation_<task>`` weights."""

    def __init__(self, weights: dict[str, Path], device: str = "cpu"):
        from ultralytics import YOLO

        self.models = {task: YOLO(str(path)) for task, path in weights.items()}
        self.device = device

    @staticmethod
    def weights_in(results_dir: Path) -> dict[str, Path]:
        """Latest run of each ``results_dir/orientation_<task>/<run>/``."""
        weights = {}
        for task_dir in sorted(Path(results_dir).glob("orientation_*")):
            runs = sorted(task_dir.glob("*/weights/best.pt"))
            if runs:
                weights[task_dir.name.removeprefix("orientation_")] = runs[-1]
        return weights

    @classmethod
    def from_results(cls, results_dir: Path, device: str = "cpu") -> YoloClassifiers:
        return cls(cls.weights_in(results_dir), device)

    def __call__(self, crop: Image.Image, task: str) -> tuple[str, float]:
        if task not in self.models:
            raise KeyError(f"no trained orientation model for task {task!r}")
        return self._predict(crop, task)

    def _predict(self, crop: Image.Image, task: str) -> tuple[str, float]:
        (result,) = self.models[task].predict(
            np.asarray(crop)[:, :, ::-1], device=self.device, verbose=False
        )
        top = int(result.probs.top1)
        return result.names[top], float(result.probs.top1conf)
