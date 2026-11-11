"""Command line entry point for the M1 VLM baseline evaluation.

Example:
    python -m vca.baseline.cli --data-approved --vlm-approved
    python -m vca.baseline.cli --data-approved --vlm-approved --limit 5
    python -m vca.baseline.cli --data-approved --vlm-approved \\
        --predictions-dir results/baseline/<run_id>/predictions   # re-score
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from vca.baseline.anthropic_provider import (
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    AnthropicProvider,
)
from vca.baseline.errors import VLMConfigError
from vca.baseline.evaluation import run_evaluation
from vca.baseline.interface import VLMInterface

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "image2net"


def _dataset_commit(manifest_path: Path) -> str | None:
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        return entries[0]["source_commit"]
    except (OSError, ValueError, LookupError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-approved", action="store_true")
    parser.add_argument("--vlm-approved", action="store_true")
    parser.add_argument("--image-dir", type=Path, default=DATA / "images")
    parser.add_argument("--netlist-dir", type=Path, default=DATA / "golden")
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "results" / "baseline"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--effort",
        default=DEFAULT_EFFORT,
        choices=["low", "medium", "high", "xhigh", "max"],
    )
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--ned-timeout", type=float, default=30.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--predictions-dir",
        type=Path,
        default=None,
        help="Re-score saved predictions from an earlier run instead of "
        "calling the VLM for circuits that already have one.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        provider = AnthropicProvider(model=args.model, effort=args.effort)
    except VLMConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    result = run_evaluation(
        image_dir=args.image_dir,
        netlist_dir=args.netlist_dir,
        vlm=VLMInterface(provider, max_retries=args.max_retries),
        output_dir=args.output_dir,
        data_approved=args.data_approved,
        vlm_approved=args.vlm_approved,
        random_seed=args.seed,
        ned_timeout=args.ned_timeout,
        limit=args.limit,
        predictions_dir=args.predictions_dir,
        extra_config={
            "effort": args.effort,
            "max_retries": args.max_retries,
            "dataset_source": "github.com/LAD021/ci2n_datasets validation/",
            "dataset_commit": _dataset_commit(args.image_dir.parent / "manifest.json"),
        },
    )

    m = result.metrics

    def fmt(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.3f}"

    evaluated = len(m.per_pair)
    print(f"\nEvaluated {evaluated} circuits with {result.model_identifier}")
    print(f"  graph-isomorphism accuracy: {fmt(m.macro_graph_isomorphism_accuracy)}")
    print(f"  mean NED:                   {fmt(m.macro_ned)}")
    print(f"  component P / R:            {fmt(m.macro_component_precision)} / "
          f"{fmt(m.macro_component_recall)}")
    print(f"  connection P / R:           {fmt(m.macro_connection_precision)} / "
          f"{fmt(m.macro_connection_recall)}")
    print(f"  element errors:             {result.error_counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
