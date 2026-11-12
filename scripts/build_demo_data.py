"""Build the demo data/explanation layer from a real pipeline + verifier run.

No LLM calls, no ground truth in flags. Reads a pipeline run's
``predictions/*.json`` and a verifier run's ``oof.json``/``model.joblib``,
and writes ``demo/data/circuits.json`` plus plain-text layers per circuit.

    uv run python scripts/build_demo_data.py \\
        --pipeline-run results/m2/pipeline/20261111T171400Z \\
        --verifier-run results/m2/verifier/20261111T171904Z \\
        --images-dir data/image2net/images \\
        --out demo/data
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vca.explain.build import (  # noqa: E402
    build_circuit_record,
    image_dimensions,
    text_layers,
    validate_record,
    verifier_note,
)
from vca.explain.status import build_status  # noqa: E402
from vca.explain.verifier_source import verifier_probs  # noqa: E402
from vca.outputs.braille import braille_output  # noqa: E402


def load_predictions(pipeline_run: Path) -> dict[str, dict]:
    predictions = {}
    for path in sorted((pipeline_run / "predictions").glob("*.json")):
        predictions[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return predictions


def ensure_gitignored(out_dir: Path) -> None:
    gitignore = ROOT / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    rel = out_dir.resolve().relative_to(ROOT).as_posix() + "/"
    if rel not in text.splitlines():
        with gitignore.open("a", encoding="utf-8") as f:
            if text and not text.endswith("\n"):
                f.write("\n")
            f.write(f"{rel}\n")
        print(f"added {rel} to .gitignore")


def link_images(images_dir: Path, out_dir: Path) -> None:
    target = out_dir / "images"
    if target.is_symlink() or target.exists():
        if target.resolve() == images_dir.resolve():
            print(f"images symlink already correct: {target} -> {images_dir}")
            return
        target.unlink() if target.is_symlink() else None
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        target.symlink_to(images_dir.resolve())
        print(f"created symlink {target} -> {images_dir.resolve()}")
    except OSError as e:
        print(f"could not symlink ({e}); copy the images directory manually")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pipeline-run", type=Path, required=True)
    parser.add_argument("--verifier-run", type=Path, required=True)
    parser.add_argument(
        "--images-dir", type=Path, default=ROOT / "data/image2net/images"
    )
    parser.add_argument("--out", type=Path, default=ROOT / "demo/data")
    args = parser.parse_args(argv)

    predictions = load_predictions(args.pipeline_run)
    probs_by_circuit, probs_source = verifier_probs(predictions, args.verifier_run)
    print(f"verifier probability source: {probs_source}")

    verifier_config = json.loads(
        (args.verifier_run / "config.json").read_text(encoding="utf-8")
    )
    verifier_metrics = json.loads(
        (args.verifier_run / "metrics.json").read_text(encoding="utf-8")
    )
    note = verifier_note(verifier_metrics, verifier_config["threshold"])

    records = []
    for circuit_id in sorted(predictions):
        prediction = predictions[circuit_id]
        image_size = image_dimensions(args.images_dir, prediction["image"])
        record = build_circuit_record(
            prediction, probs_by_circuit.get(circuit_id, {}), note, image_size
        )
        braille = braille_output(text_layers(record)["all"])
        if braille:
            record["braille"] = braille
            brf_dir = args.out / "braille"
            brf_dir.mkdir(parents=True, exist_ok=True)
            (brf_dir / f"{circuit_id}.brf").write_bytes(braille["brf"].encode("ascii"))
        records.append(record)

    problems = [p for record in records for p in validate_record(record)]
    if problems:
        for p in problems:
            print("VALIDATION PROBLEM:", p, file=sys.stderr)
        return 1

    zero_blocks = sum(
        1
        for r in records
        if not any(s["components"] for s in r["explanation"]["layer2_blocks"])
    )
    zero_flags = sum(1 for r in records if r["flagged_count"] == 0)
    flagged_dist = Counter(r["flagged_count"] for r in records)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "circuits.json").write_text(
        json.dumps(records, indent=1, sort_keys=False), encoding="utf-8"
    )

    text_dir = args.out / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        layers = text_layers(record)
        for name in ("layer1", "layer2", "layer3", "all"):
            (text_dir / f"{record['id']}.{name}.txt").write_text(
                layers[name] + "\n", encoding="utf-8"
            )

    status = build_status(args.pipeline_run, args.verifier_run, note)
    (args.out / "status.json").write_text(
        json.dumps(status, indent=1), encoding="utf-8"
    )

    link_images(args.images_dir, args.out)
    ensure_gitignored(args.out)

    print(f"circuits: {len(records)}")
    print(f"circuits with 0 blocks found: {zero_blocks}")
    print(f"circuits with 0 flagged components: {zero_flags}")
    print(f"flagged_count distribution: {dict(sorted(flagged_dist.items()))}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
