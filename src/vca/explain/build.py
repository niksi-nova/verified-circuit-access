"""Assemble one demo circuit record from a pipeline prediction.

Pulls together the graph, block rules, flags and sentence templates; adds
the evaluation-only block (copied, never recomputed, from the saved
``score``); and runs the validation pass described in STEP C.6.
"""

from __future__ import annotations

from pathlib import Path

from vca.explain.blocks import find_blocks
from vca.explain.flags import circuit_flags, component_flags
from vca.explain.graph import CircuitGraph
from vca.explain.templates import build_layer1, build_layer2, build_layer3


def verifier_note(verifier_metrics: dict, threshold: float) -> str:
    key = f"flag@{threshold}"
    flag = verifier_metrics["verifier_oof"][key]
    auroc = verifier_metrics["verifier_oof"]["auroc"]
    recall = flag["recall"]
    one_in = round(1 / recall) if recall > 0 else None
    catch_phrase = f"about 1 in {one_in}" if one_in else "very few"
    return (
        "The error checker is an early version: it catches "
        f"{catch_phrase} errors at its default setting "
        f"(AUROC {round(auroc, 2)}, from the recorded verifier run)."
    )


def build_circuit_record(
    prediction: dict,
    verifier_probs: dict[str, float],
    note: str,
    image_size: tuple[int, int] | None,
    circuit_id: str | None = None,
    score: dict | None = None,
) -> dict:
    """``circuit_id``/``score`` are optional: a live analysis of a new
    image has no golden netlist, so there is no ``score`` to copy an
    evaluation block from. The saved-data build path (``circuit_id`` left
    as ``None``) keeps reading both from ``prediction["score"]`` for
    backward compatibility with the batch build script."""
    if score is None and "score" in prediction:
        score = prediction["score"]
    if circuit_id is None:
        circuit_id = prediction["score"]["circuit_id"]

    netlist = prediction["netlist"]
    graph = CircuitGraph.build(netlist)

    rows_by_id = {c["component_id"]: c for c in prediction["components"]}
    component_flag_rows = {
        comp_id: component_flags(
            graph, rows_by_id[comp_id], verifier_probs.get(comp_id)
        )
        for comp_id in graph.reading_order
    }
    circuit_level_flags = circuit_flags(prediction["rules"])
    blocks = find_blocks(graph)

    layer1 = build_layer1(graph, circuit_level_flags)
    layer2 = build_layer2(graph, blocks)
    layer3 = build_layer3(graph, component_flag_rows)

    flagged_count = sum(
        1 for f in component_flag_rows.values() if f["level"] == "needs check"
    )

    components_out = []
    for comp_id in graph.reading_order:
        comp = graph.components[comp_id]
        components_out.append(
            {
                "id": comp_id,
                "category": comp["canonical_category"],
                "bbox": comp.get("bbox"),
                "flags": component_flag_rows[comp_id],
            }
        )

    nets_out = [
        {
            "id": raw_name,
            "label": graph.label_of(raw_name),
            "fanout": len(endpoints),
            "components": sorted({comp_id for comp_id, _ in endpoints}),
        }
        for raw_name, endpoints in graph.net_endpoints.items()
    ]

    evaluation = None
    if score is not None:
        evaluation = {
            "evaluation_only": True,
            "ned": score["ned"],
            "ned_lower_bound": score["ned_lower_bound"],
            "graph_isomorphic": score["graph_isomorphism"],
            "connection_precision": score["connection_precision"],
            "connection_recall": score["connection_recall"],
            "true_error_count": len(score["errors"]),
            "true_error_component_ids": sorted(
                {
                    e["pred_component"]
                    for e in score["errors"]
                    if e.get("pred_component")
                }
            ),
            "note": note,
        }

    record = {
        "id": circuit_id,
        "image": prediction["image"],
        "image_width": image_size[0] if image_size else None,
        "image_height": image_size[1] if image_size else None,
        "components": components_out,
        "nets": nets_out,
        "flags": {
            "circuit": circuit_level_flags,
            "flagged_count": flagged_count,
        },
        "explanation": {
            "layer1_overview": layer1,
            "layer2_blocks": layer2,
            "layer3_details": layer3,
        },
        "flagged_count": flagged_count,
        "evaluation": evaluation,
    }
    return record


def validate_record(record: dict) -> list[str]:
    """Checks STEP C.6 asks for: every source id exists, no empty layer."""
    problems = []
    component_ids = {c["id"] for c in record["components"]}
    net_ids = {n["id"] for n in record["nets"]}

    for layer_name in ("layer1_overview", "layer2_blocks", "layer3_details"):
        sentences = record["explanation"][layer_name]
        if not sentences:
            problems.append(f"{record['id']}: {layer_name} is empty")
        for sentence in sentences:
            for cid in sentence["components"]:
                if cid not in component_ids:
                    problems.append(
                        f"{record['id']}: {layer_name} references unknown "
                        f"component {cid}"
                    )
            for nid in sentence["nets"]:
                if nid not in net_ids:
                    problems.append(
                        f"{record['id']}: {layer_name} references unknown net {nid}"
                    )
    return problems


def text_layers(record: dict) -> dict[str, str]:
    def render(sentences: list[dict]) -> str:
        return "\n".join(s["text"] for s in sentences)

    layer1 = render(record["explanation"]["layer1_overview"])
    layer2 = render(record["explanation"]["layer2_blocks"])
    layer3 = render(record["explanation"]["layer3_details"])
    return {
        "layer1": layer1,
        "layer2": layer2,
        "layer3": layer3,
        "all": "\n\n".join([layer1, layer2, layer3]),
    }


def image_dimensions(images_dir: Path, image_name: str) -> tuple[int, int] | None:
    path = Path(images_dir) / image_name
    if not path.exists():
        return None
    from PIL import Image

    with Image.open(path) as img:
        return img.size
