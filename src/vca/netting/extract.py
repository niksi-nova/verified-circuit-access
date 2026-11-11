"""Net extraction: from detections on a schematic image to a netlist.

Classical, SINA-style: the wires are what is left of the ink once every
detected symbol is blanked out, so connected components of that ink are
nets. Then:

1. Crossings. Hops (from the crossing model, or the detector's
   ``cross-line-curved`` class) are cut and their arms re-joined straight
   through (left-right, top-bottom). Plain four-way crossings without a dot
   are found from the image and treated the same way (textbook convention:
   no dot, no connection) unless a dot / T-junction detection covers them.
2. Rails. Every net touching a ``gnd`` symbol becomes one ``GND`` net, every
   net touching ``vdd`` one ``VDD`` net.
3. Terminals. Wire ends in a thin ring around a component box are matched
   to the terminal anchors of :mod:`vca.netting.terminals` by minimum total
   distance (Hungarian assignment).

Everything that did not fit cleanly (ring contacts left over, terminals
with no wire, guessed orientations, nets with a single terminal) is
returned in :class:`NetExtraction` for the verifier.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.optimize import linear_sum_assignment

from vca.detect.classes import NETLIST_CATEGORY
from vca.netting.terminals import TerminalLayout, terminal_layout
from vca.schemas.annotation import BoundingBox
from vca.schemas.netlist import Component, Net, NetEndpoint, Netlist, Terminal

Box = tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels

RAILS = {"gnd": "GND", "vdd": "VDD"}
_HOP_CLASSES = {"cross-line-curved"}
_EIGHT = np.ones((3, 3), dtype=bool)
_THROUGH_CLASSES = ("nmos", "pmos")  # gate buses are drawn through MOS symbols


@dataclass(frozen=True)
class Detection:
    detector_class: str
    box: Box
    score: float = 1.0
    orientation: str | None = None  # l / d / r / u
    mirrored: bool | None = None


@dataclass(frozen=True)
class Crossing:
    kind: str  # "hop", "dot_junction" or "t_junction"
    box: Box
    score: float = 1.0


@dataclass
class ComponentReport:
    component_id: str
    detector_class: str
    layout: TerminalLayout
    terminal_nets: dict[str, str] = field(default_factory=dict)
    terminal_distance: dict[str, float] = field(default_factory=dict)
    unconnected_terminals: list[str] = field(default_factory=list)
    extra_contacts: int = 0
    # (x, y, net, terminal or None) for every wire end kept at the box.
    contacts: list[tuple[float, float, str, str | None]] = field(default_factory=list)


@dataclass
class NetExtraction:
    netlist: Netlist
    components: list[ComponentReport]
    line_width: float
    crossings_cut: int
    single_terminal_nets: list[str]
    rail_conflicts: int = 0  # nets touching both a GND and a VDD symbol


def binarize(image: Image.Image) -> np.ndarray:
    """Ink mask (True = dark) by Otsu's threshold on the grey image."""
    grey = np.asarray(image.convert("L"), dtype=np.uint8)
    hist = np.bincount(grey.ravel(), minlength=256).astype(float)
    total = hist.sum()
    levels = np.arange(256)
    weight = np.cumsum(hist)
    mean = np.cumsum(hist * levels)
    with np.errstate(divide="ignore", invalid="ignore"):
        between = (mean[-1] * weight - mean * total) ** 2 / (weight * (total - weight))
    threshold = int(np.nanargmax(between))
    return grey <= threshold


def line_width(ink: np.ndarray) -> float:
    """Typical stroke width: the most common short run length of ink."""
    runs: Counter[int] = Counter()
    for axis_view in (ink, ink.T):
        padded = np.pad(axis_view, ((0, 0), (1, 1))).astype(np.int8)
        edges = np.diff(padded, axis=1)
        starts = np.nonzero(edges == 1)
        ends = np.nonzero(edges == -1)
        lengths = ends[1] - starts[1]
        runs.update(int(n) for n in lengths if n <= 15)
    return float(runs.most_common(1)[0][0]) if runs else 1.0


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _clip(box: Box, pad: float, shape: tuple[int, int]) -> tuple[int, int, int, int]:
    h, w = shape
    x1, y1, x2, y2 = box
    return (
        max(0, int(np.floor(x1 - pad))),
        max(0, int(np.floor(y1 - pad))),
        min(w, int(np.ceil(x2 + pad))),
        min(h, int(np.ceil(y2 + pad))),
    )


def _inside(point: tuple[float, float], box: Box, pad: float = 0) -> bool:
    x, y = point
    return box[0] - pad <= x <= box[2] + pad and box[1] - pad <= y <= box[3] + pad


def find_plain_crossings(ink: np.ndarray, lw: float, keep: list[Box]) -> list[Box]:
    """Four-way wire crossings without a dot (and not inside ``keep`` boxes)."""
    arm = max(8, int(round(5 * lw)))
    horizontal = ndimage.binary_opening(ink, structure=np.ones((1, 2 * arm + 1)))
    vertical = ndimage.binary_opening(ink, structure=np.ones((2 * arm + 1, 1)))
    labels, n = ndimage.label(horizontal & vertical, structure=_EIGHT)
    boxes = []
    h, w = ink.shape
    for sl in ndimage.find_objects(labels):
        if sl is None:
            continue
        y1, y2, x1, x2 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        cy, cx = (y1 + y2) / 2, (x1 + x2) / 2
        if any(_inside((cx, cy), b, lw) for b in keep):
            continue
        # Each arm must still be there a few strokes away from the crossing:
        # a T-junction's stem often overshoots the bar by a pixel or two.
        near = int(round(2 * lw)) + 1
        far = near + int(round(2 * lw)) + 2

        def band(mask, a, b, axis_slice, vertical_arm):
            if a < 0 or b < 0:
                return False
            return bool(
                mask[a:b, axis_slice].any()
                if vertical_arm
                else mask[axis_slice, a:b].any()
            )

        rows, cols = slice(y1, y2), slice(x1, x2)
        arms = (
            band(horizontal, x1 - far if x1 >= far else -1, x1 - near, rows, False),
            band(horizontal, x2 + near, min(w, x2 + far), rows, False)
            and x2 + near < w,
            band(vertical, y1 - far if y1 >= far else -1, y1 - near, cols, True),
            band(vertical, y2 + near, min(h, y2 + far), cols, True) and y2 + near < h,
        )
        if not all(arms):
            continue  # T or L junction: connected
        # A drawn dot fills the square around the crossing much more than two
        # crossing strokes do (about 7/16 of a 4-stroke-wide square).
        r = int(round(2 * lw)) + 1
        window = ink[
            max(0, int(cy) - r) : int(cy) + r + 1, max(0, int(cx) - r) : int(cx) + r + 1
        ]
        if window.mean() > 0.62:
            continue
        boxes.append((x1 - lw, y1 - lw, x2 + lw, y2 + lw))
    return boxes


def find_through_lines(
    ink: np.ndarray, box: tuple[int, int, int, int], lw: float
) -> list[tuple[str, int]]:
    """Thin straight lines crossing a whole (clipped) box: ("row", y) / ("col", x).

    Schematics often run a gate bus straight through a transistor symbol.
    Blanking the box cuts that bus in two; the line drawn through the
    symbol shows both halves are one wire. A symbol's own strokes (plates,
    channel, stubs) never span the box edge to edge in a single thin line.
    """
    x1, y1, x2, y2 = box
    half = max(1, int(lw // 2))
    away = int(np.ceil(lw)) + 2
    found: list[tuple[str, int]] = []
    for axis, view, lo, hi in (
        ("row", ink[:, x1:x2], y1, y2),
        ("col", ink[y1:y2, :].T, x1, x2),
    ):
        if view.shape[1] < 2:
            continue
        hits = []
        for c in range(lo + half, hi - half):
            if not view[c - half : c + half + 1].any(axis=0).all():
                continue
            near = [view[c + s].mean() for s in (-away, away) if 0 <= c + s < len(view)]
            if len(near) == 2 and max(near) < 0.5:
                hits.append(c)
        # One line covers several adjacent rows: keep each run's middle.
        runs: list[list[int]] = []
        for c in hits:
            if runs and c - runs[-1][-1] <= 1:
                runs[-1].append(c)
            else:
                runs.append([c])
        found += [(axis, run[len(run) // 2]) for run in runs]
    return found


def _side_labels(labels: np.ndarray, box: Box, reach: int) -> dict[str, set[int]]:
    """Wire labels just outside each side of a cut box."""
    h, w = labels.shape
    x1, y1, x2, y2 = _clip(box, 0, labels.shape)
    strips = {
        "left": labels[y1:y2, max(0, x1 - reach) : x1],
        "right": labels[y1:y2, x2 : min(w, x2 + reach)],
        "top": labels[max(0, y1 - reach) : y1, x1:x2],
        "bottom": labels[y2 : min(h, y2 + reach), x1:x2],
    }
    return {side: set(np.unique(s)) - {0} for side, s in strips.items()}


def extract_netlist(
    image: Image.Image,
    detections: list[Detection],
    crossings: list[Crossing] = (),
    *,
    detect_plain_crossings: bool = True,
) -> NetExtraction:
    ink = binarize(image)
    lw = line_width(ink)
    pad = max(1.0, lw)
    reach = int(round(3 * lw)) + 2

    components = [d for d in detections if NETLIST_CATEGORY.get(d.detector_class)]
    rails = [d for d in detections if d.detector_class in RAILS]
    hops = [c.box for c in crossings if c.kind == "hop"] + [
        d.box for d in detections if d.detector_class in _HOP_CLASSES
    ]
    joins = [c.box for c in crossings if c.kind != "hop"]
    symbols = [d for d in detections if d.detector_class not in _HOP_CLASSES]

    wires = ink.copy()
    for d in symbols:
        x1, y1, x2, y2 = _clip(d.box, pad, ink.shape)
        wires[y1:y2, x1:x2] = False
    if detect_plain_crossings:
        hops += find_plain_crossings(wires, lw, keep=joins + [d.box for d in symbols])
    for box in hops:
        x1, y1, x2, y2 = _clip(box, 0, ink.shape)
        wires[y1:y2, x1:x2] = False

    labels, n = ndimage.label(wires, structure=_EIGHT)
    uf = _UnionFind(n + 1)
    # Wires drawn straight through a transistor symbol are one wire.
    # component index -> (axis, coordinate) of each line drawn through it
    through: dict[int, list[tuple[str, int]]] = {}
    for index, d in enumerate(components):
        if not d.detector_class.startswith(_THROUGH_CLASSES):
            continue
        x1, y1, x2, y2 = _clip(d.box, pad, ink.shape)
        r = max(1, int(lw))
        for axis, c in find_through_lines(ink, (x1, y1, x2, y2), lw):
            if axis == "row":
                a = labels[c - r : c + r + 1, max(0, x1 - reach) : x1]
                b = labels[c - r : c + r + 1, x2 : x2 + reach]
            else:
                a = labels[max(0, y1 - reach) : y1, c - r : c + r + 1]
                b = labels[y2 : y2 + reach, c - r : c + r + 1]
            ends = [set(a[a > 0].tolist()), set(b[b > 0].tolist())]
            for la in ends[0]:
                for lb in ends[1]:
                    uf.union(la, lb)
            if ends[0] and ends[1]:
                through.setdefault(index, []).append((axis, c))
    for box in hops:
        sides = _side_labels(labels, box, reach)
        for a, b in (("left", "right"), ("top", "bottom")):
            for la in sides[a]:
                for lb in sides[b]:
                    uf.union(la, lb)

    def ring_contacts(box: Box) -> list[tuple[float, float, int, int]]:
        """(x, y, root label, size) of each wire end touching a box's ring."""
        ox1, oy1, ox2, oy2 = _clip(box, pad + reach, ink.shape)
        ix1, iy1, ix2, iy2 = _clip(box, pad, ink.shape)
        ring = np.zeros_like(wires[oy1:oy2, ox1:ox2])
        ring[:] = wires[oy1:oy2, ox1:ox2]
        ring[iy1 - oy1 : iy2 - oy1, ix1 - ox1 : ix2 - ox1] = False
        parts, m = ndimage.label(ring, structure=_EIGHT)
        found = []
        for k in range(1, m + 1):
            ys, xs = np.nonzero(parts == k)
            roots = Counter(uf.find(int(v)) for v in labels[oy1 + ys, ox1 + xs] if v)
            if roots:
                found.append(
                    (
                        float(xs.mean() + ox1),
                        float(ys.mean() + oy1),
                        roots.most_common(1)[0][0],
                        len(xs),
                    )
                )
        return found

    # Rails merge every net that touches them.
    rail_root: dict[int, str] = {}
    rails_touched: dict[int, set[str]] = {}
    for d in rails:
        for _, _, root, _ in ring_contacts(d.box):
            rail_root.setdefault(root, RAILS[d.detector_class])
            rails_touched.setdefault(root, set()).add(RAILS[d.detector_class])
    # One wire touching both a GND and a VDD symbol: a short or a misread.
    rail_conflicts = sum(len(r) > 1 for r in rails_touched.values())

    # A net matters if it reaches two anchors (terminals / rails / ports);
    # isolated ink near a box (designator text such as "M1") is ignored.
    contacts_by_component = [ring_contacts(d.box) for d in components]
    anchor_hits: Counter[int] = Counter()
    for contacts in contacts_by_component:
        for root in {c[2] for c in contacts}:
            anchor_hits[root] += 1
    for d in detections:
        if d.detector_class in ("port", "antenna"):
            for root in {c[2] for c in ring_contacts(d.box)}:
                anchor_hits[root] += 1
    for root in rail_root:
        anchor_hits[root] += 1
    sizes = ndimage.sum_labels(wires, labels, index=np.arange(n + 1))
    root_size: Counter[int] = Counter()
    for label in range(1, n + 1):
        root_size[uf.find(label)] += int(sizes[label])
    min_wire = 8 * lw

    reports: list[ComponentReport] = []
    endpoints: dict[str, list[NetEndpoint]] = {}
    net_names: dict[int, str] = {}

    def name_of(root: int) -> str:
        if root in rail_root:
            return rail_root[root]
        if root not in net_names:
            net_names[root] = f"net{len(net_names) + 1}"
        return net_names[root]

    built: list[Component] = []
    for index, (d, contacts) in enumerate(
        zip(components, contacts_by_component, strict=True)
    ):
        category = NETLIST_CATEGORY[d.detector_class]
        layout = terminal_layout(
            d.detector_class, category, d.box, d.orientation, d.mirrored
        )
        component_id = f"C{index + 1}"
        report = ComponentReport(component_id, d.detector_class, layout)
        contacts = [
            c for c in contacts if anchor_hits[c[2]] >= 2 or root_size[c[2]] >= min_wire
        ]
        names = list(layout.anchors)
        x1, y1, x2, y2 = d.box
        w, h = max(x2 - x1, 1.0), max(y2 - y1, 1.0)
        if contacts:

            def anchor_cost(cx: float, cy: float) -> list[float]:
                return [
                    float(np.hypot((cx - x1) / w - ax, (cy - y1) / h - ay))
                    for ax, ay in (layout.anchors[t] for t in names)
                ]

            # Both halves of a wire drawn through the symbol touch it: keep
            # the half that meets a terminal, drop the pass-through half.
            for axis, line in through.get(index, []):
                on_line = [
                    c
                    for c in contacts
                    if abs((c[1] if axis == "row" else c[0]) - line) <= 2 * lw
                ]
                if len({c[2] for c in on_line}) == 1 and len(on_line) > 1:
                    keep = min(on_line, key=lambda c: min(anchor_cost(c[0], c[1])))
                    contacts = [c for c in contacts if c not in on_line or c is keep]
            cost = np.array([anchor_cost(cx, cy) for cx, cy, _, _ in contacts])
            rows, cols = linear_sum_assignment(cost)
            for r, c in zip(rows, cols, strict=True):
                terminal = names[c]
                net = name_of(contacts[r][2])
                report.terminal_nets[terminal] = net
                report.terminal_distance[terminal] = round(float(cost[r, c]), 4)
                endpoints.setdefault(net, []).append(
                    NetEndpoint(component_id=component_id, terminal_name=terminal)
                )
            report.extra_contacts = len(contacts) - len(rows)
            assigned = dict(zip(rows.tolist(), cols.tolist(), strict=True))
            report.contacts = [
                (
                    round(cx, 1),
                    round(cy, 1),
                    name_of(root),
                    names[assigned[i]] if i in assigned else None,
                )
                for i, (cx, cy, root, _) in enumerate(contacts)
            ]
        report.unconnected_terminals = [
            t for t in names if t not in report.terminal_nets
        ]
        reports.append(report)
        built.append(
            Component(
                id=component_id,
                canonical_category=category,
                terminals=[Terminal(name=t) for t in names],
                bbox=BoundingBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1),
            )
        )

    nets = [Net(name=k, endpoints=v) for k, v in endpoints.items()]
    return NetExtraction(
        netlist=Netlist(components=built, nets=nets),
        components=reports,
        line_width=lw,
        crossings_cut=len(hops),
        single_terminal_nets=sorted(
            k for k, v in endpoints.items() if len(v) == 1 and k not in RAILS.values()
        ),
        rail_conflicts=rail_conflicts,
    )
