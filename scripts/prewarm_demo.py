"""Run the six demo examples fresh through the loopback API and report timings."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "data/image2net/images"
EXAMPLES = ("002", "003", "014", "015", "019", "095")
FIDELITY_IDS = ("015", "036", "097")
API = "http://127.0.0.1:8000/api"


def request(path: str, **kwargs):
    with urlopen(Request(f"{API}/{path}", **kwargs), timeout=10) as response:
        return json.load(response)


def analyze(image: Path) -> tuple[dict, dict]:
    boundary = uuid.uuid4().hex
    data = b"".join(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="use_saved"\r\n\r\n'
            f"false\r\n--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="image.png"\r\n'
            "Content-Type: image/png\r\n\r\n".encode(),
            image.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        )
    )
    job = request(
        "analyze",
        data=data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        state = request(f"jobs/{job['job_id']}")
        if state["status"] == "done":
            if state["from_saved"]:
                raise RuntimeError("The engine unexpectedly reused a saved analysis.")
            meta = next(
                run for run in request("runs") if run["sha256"] == job["sha256"]
            )
            return state["result"], meta
        if state["status"] in {"error", "cancelled"}:
            raise RuntimeError(state.get("error", state["status"]))
        time.sleep(0.2)
    request(f"jobs/{job['job_id']}/cancel", method="POST")
    raise RuntimeError(f"Timed out analysing {image.name}.")


def compare(circuit_id: str, live: dict, predictions: Path) -> None:
    saved = json.loads((predictions / f"{circuit_id}.json").read_text())["netlist"]
    live_parts = {row["id"]: row for row in live["components"]}
    saved_parts = {row["id"]: row for row in saved["components"]}
    shared = live_parts.keys() & saved_parts.keys()
    categories = [
        (i, saved_parts[i]["canonical_category"], live_parts[i]["category"])
        for i in sorted(shared)
        if live_parts[i]["category"] != saved_parts[i]["canonical_category"]
    ]
    boxes = [
        i for i in sorted(shared) if live_parts[i]["bbox"] != saved_parts[i]["bbox"]
    ]
    max_delta = max(
        (
            abs(live_parts[i]["bbox"][key] - saved_parts[i]["bbox"][key])
            for i in boxes
            if live_parts[i]["bbox"] is not None and saved_parts[i]["bbox"] is not None
            for key in live_parts[i]["bbox"]
        ),
        default=0.0,
    )
    live_nets = {
        n["id"]: (tuple(sorted(n["components"])), n["fanout"]) for n in live["nets"]
    }
    saved_nets = {
        n["name"]: (
            tuple(sorted({e["component_id"] for e in n["endpoints"]})),
            len(n["endpoints"]),
        )
        for n in saved["nets"]
    }
    print(
        f"{circuit_id}: parts saved/live={len(saved_parts)}/{len(live_parts)}; "
        f"nets saved/live={len(saved_nets)}/{len(live_nets)}; "
        f"verifier={live['verifier_source']}"
    )
    print(
        f"  Missing parts: {sorted(saved_parts.keys() - live_parts.keys())}; "
        f"extra parts: {sorted(live_parts.keys() - saved_parts.keys())}; "
        f"category changes (saved, live): {categories}"
    )
    print(f"  Changed boxes: {boxes}; largest coordinate delta: {max_delta:.6f}px")
    for key in sorted(saved_nets.keys() | live_nets.keys()):
        if saved_nets.get(key) != live_nets.get(key):
            print(
                f"  Net {key}: saved={saved_nets.get(key)}, live={live_nets.get(key)}"
            )
    if live_nets == saved_nets:
        print("  Every net name, component membership and terminal count matches.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fidelity", action="store_true", help="compare validation runs"
    )
    args = parser.parse_args()
    try:
        health = request("health")
        if not health["engine_ready"]:
            raise RuntimeError("The local analysis engine is not ready.")
        if args.fidelity:
            predictions = ROOT / health["runs"]["pipeline_run"] / "predictions"
            for circuit_id in FIDELITY_IDS:
                result, _ = analyze(IMAGES / f"{circuit_id}.png")
                compare(circuit_id, result, predictions)
        else:
            print(f"{'Example':<10} {'CPU seconds':>12}", flush=True)
            for circuit_id in EXAMPLES:
                _, meta = analyze(IMAGES / f"{circuit_id}.png")
                print(f"{circuit_id:<10} {meta['duration_seconds']:>12.2f}", flush=True)
    except HTTPError as error:
        parser.exit(1, f"Engine returned HTTP {error.code}: {error.read().decode()}\n")
    except (URLError, RuntimeError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
