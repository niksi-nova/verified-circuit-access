"""End-to-end M2 inference: schematic image -> netlist with evidence.

detector (components, rails, ports) -> crossing model (hops / junctions)
-> orientation classifiers -> net extraction -> rule checks.

Every stage's confidence is kept per component so the verifier can learn
which predictions to trust. The stages are injectable callables, so tests
and ablations (ground-truth boxes, no crossing model, convention-only
orientation) use the same code path.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from vca.detect.classes import NETLIST_CATEGORY
from vca.netting.extract import Crossing, Detection, NetExtraction, extract_netlist
from vca.netting.orient import Classifier, orient
from vca.schemas.netlist import Netlist
from vca.verify.rules import RuleReport, check

Detector = Callable[[Image.Image], list[Detection]]
CrossingModel = Callable[[Image.Image], list[Crossing]]
StageHook = Callable[[str], None]

# The stage boundaries a caller can observe, in call order. Purely
# informational (e.g. for a progress UI); the pipeline's own control flow
# never depends on them.
STAGES: tuple[str, ...] = (
    "read_image",
    "detect_components",
    "detect_crossings",
    "orientation",
    "netting",
    "rule_checks",
)


@dataclass
class PipelineResult:
    netlist: Netlist
    detections: list[Detection]
    crossings: list[Crossing]
    orientation_scores: list[dict]
    extraction: NetExtraction
    rules: RuleReport
    component_features: list[dict] = field(default_factory=list)


@dataclass
class Pipeline:
    detect: Detector
    crossings: CrossingModel | None = None
    classify: Classifier | None = None
    detect_plain_crossings: bool = True

    def __call__(
        self, image: Image.Image, on_stage: StageHook | None = None
    ) -> PipelineResult:
        """``on_stage``, if given, is called with each name in ``STAGES``
        as that stage starts. Optional and side-effect-free from the
        pipeline's point of view — it never influences the result."""
        notify = on_stage or (lambda stage: None)

        notify("read_image")
        image = image.convert("RGB")

        notify("detect_components")
        detections = self.detect(image)

        notify("detect_crossings")
        crossings = self.crossings(image) if self.crossings else []

        notify("orientation")
        if self.classify is not None:
            detections, scores = orient(image, detections, self.classify)
        else:
            scores = [{} for _ in detections]

        notify("netting")
        extraction = extract_netlist(
            image,
            detections,
            crossings,
            detect_plain_crossings=self.detect_plain_crossings,
        )

        notify("rule_checks")
        rules = check(extraction)
        return PipelineResult(
            netlist=extraction.netlist,
            detections=detections,
            crossings=crossings,
            orientation_scores=scores,
            extraction=extraction,
            rules=rules,
            component_features=component_features(
                detections, scores, extraction, rules
            ),
        )


def component_features(
    detections: list[Detection],
    scores: list[dict],
    extraction: NetExtraction,
    rules: RuleReport,
) -> list[dict]:
    """One row per netlist component: evidence for the verifier."""
    # extract_netlist keeps netlist components in detection order.
    parts = [
        (d, s)
        for d, s in zip(detections, scores, strict=True)
        if NETLIST_CATEGORY.get(d.detector_class)
    ]
    fanout = {n.name: len(n.endpoints) for n in extraction.netlist.nets}
    rows = []
    for component, report, (d, s) in zip(
        extraction.netlist.components, extraction.components, parts, strict=True
    ):
        box = component.bbox
        distances = list(report.terminal_distance.values())
        rows.append(
            {
                "component_id": component.id,
                "detector_class": d.detector_class,
                "category": component.canonical_category,
                "detector_score": d.score,
                "box_area": box.width * box.height,
                "box_aspect": box.width / max(box.height, 1e-6),
                "orientation": report.layout.orientation,
                "orientation_source": report.layout.orientation_source,
                "orientation_p": s.get("orientation_p"),
                "mirror_source": report.layout.mirror_source,
                "mirrored_p": s.get("mirrored_p"),
                "terminals": len(report.layout.anchors),
                "unconnected_terminals": len(report.unconnected_terminals),
                "extra_contacts": report.extra_contacts,
                "max_terminal_distance": max(distances) if distances else None,
                "mean_terminal_distance": (
                    sum(distances) / len(distances) if distances else None
                ),
                "min_net_fanout": min(
                    (fanout[n] for n in report.terminal_nets.values()), default=0
                ),
                "rules": rules.per_component[component.id],
            }
        )
    return rows


class YoloDetector:
    """Component detector (Ultralytics detect weights, M2 class names)."""

    def __init__(self, weights: Path, *, conf=0.25, imgsz=1024, device="cpu"):
        from ultralytics import YOLO

        self.model = YOLO(str(weights))
        self.conf, self.imgsz, self.device = conf, imgsz, device

    def __call__(self, image: Image.Image) -> list[Detection]:
        # Class-agnostic NMS: one symbol gets one class, not one box per
        # class the detector hesitates between.
        (result,) = self.model.predict(
            image,
            conf=self.conf,
            imgsz=self.imgsz,
            device=self.device,
            agnostic_nms=True,
            verbose=False,
        )
        names = result.names
        return [
            Detection(names[int(c)], tuple(float(v) for v in xyxy), float(p))
            for xyxy, c, p in zip(
                result.boxes.xyxy.tolist(),
                result.boxes.cls.tolist(),
                result.boxes.conf.tolist(),
                strict=True,
            )
        ]


class YoloCrossings:
    """Crossing model (Ultralytics OBB weights: hop / dot_junction / t_junction)."""

    def __init__(self, weights: Path, *, conf=0.25, imgsz=1024, device="cpu"):
        from ultralytics import YOLO

        self.model = YOLO(str(weights))
        self.conf, self.imgsz, self.device = conf, imgsz, device

    def __call__(self, image: Image.Image) -> list[Crossing]:
        (result,) = self.model.predict(
            image, conf=self.conf, imgsz=self.imgsz, device=self.device, verbose=False
        )
        names = result.names
        return [
            Crossing(names[int(c)], tuple(float(v) for v in xyxy), float(p))
            for xyxy, c, p in zip(
                result.obb.xyxy.tolist(),
                result.obb.cls.tolist(),
                result.obb.conf.tolist(),
                strict=True,
            )
        ]
