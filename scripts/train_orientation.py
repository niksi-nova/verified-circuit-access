"""Train every orientation/mirroring classifier in data/m2/orientation/.

Horizontal flipping is switched off: it turns an "l" crop into an "r" one
and flips the mirror state, so with Ultralytics' default (0.5) half the
flipped samples carry the wrong label.

Runs one after another (they are small); results land in
results/m2/orientation_<task>/<run_id>/. Extra arguments are passed to
``vca.training`` (e.g. --device 0 --epochs 30).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vca.training import main as train  # noqa: E402

DATA = ROOT / "data" / "m2" / "orientation"


def main(extra: list[str]) -> int:
    defaults = ["--device", "cpu", "--epochs", "60", "--batch", "64", "--workers", "4"]
    defaults += ["--fliplr", "0"]
    tasks = sorted(p.name for p in DATA.iterdir() if p.is_dir())
    for i, task in enumerate(tasks, start=1):
        print(f"=== [{i}/{len(tasks)}] orientation_{task}", flush=True)
        train(
            ["classify", "--data", str(DATA / task), "--name", f"orientation_{task}"]
            + ["--output-dir", str(ROOT / "results" / "m2")]
            + defaults
            + extra
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
