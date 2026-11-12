"""Make print-sized vector diagrams from predicted components and terminal nets."""

from __future__ import annotations

import math
import os
from html import escape
from textwrap import wrap

from vca.netting.terminals import terminal_layout
from vca.schemas.netlist import Netlist

PAGE_SIZES = {"A4": (210, 297), "Letter": (215.9, 279.4)}
SYMBOLS = {
    "resistor": "M-4 0h1l1-2 2 4 2-4 1 2h1",
    "capacitor": "M-4 0h3m0-3v6m2-6v6m0-3h3",
    "voltage": "M-4 0h2m0-3v6m3-2v4m0-2h3",
    "current": "M-4 0h8m-3-2 3 2-3 2",
    "ground": "M0-3v3m-4 0h8m-6 2h4m-3 2h2",
    "nmos": "M-4 0h2m0-3v6m2-6v6m0-5h3v-2m-3 7h3v2",
    "pmos": "M-4 0h1m0 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0m4-3v6m0-5h3v-2m-3 7h3v2",
    "diff-amp": "M-4-3v6l8-3z",
}
Point = tuple[float, float]
Box = tuple[float, float, float, float]


def _text(x: float, y: float, label: str, size: float = 4) -> str:
    return f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}">{escape(label)}</text>'


def _intersects(a: Box, b: Box, gap: float = 0) -> bool:
    return (
        max(a[0], b[0]) <= min(a[2], b[2]) + gap
        and max(a[1], b[1]) <= min(a[3], b[3]) + gap
    )


def _bounds(a: Point, b: Point) -> Box:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])


def _route(
    graph: Netlist, boxes: dict[str, Box], features: dict, clearance: float
) -> list[tuple[Point, ...]] | None:
    # Each port lies on the outline of its own component box.
    ports = {}
    for part in graph.components:
        category = part.canonical_category
        feature = features.get(part.id, {})
        x1, y1, x2, y2 = boxes[part.id]
        if len(part.terminals) == 1:
            layout = {part.terminals[0].name: (0.5, 0)}
        else:
            try:
                layout = terminal_layout(
                    feature.get("detector_class", category),
                    category,
                    boxes[part.id],
                    feature.get("orientation"),
                    feature.get("mirrored"),
                ).anchors
            except (KeyError, ValueError):
                return None
        for terminal, (x, y) in layout.items():
            anchor = (x1 + x * (x2 - x1), y1 + y * (y2 - y1))
            lead = clearance + 1
            if x in {0, 1}:
                stub = (anchor[0] + lead * (2 * x - 1), anchor[1])
            else:
                stub = (anchor[0], anchor[1] + lead * (2 * y - 1))
            ports[part.id, terminal] = (anchor, stub)

    used: list[Box] = []
    routes = []
    for net in graph.nets:
        endpoints = [(e.component_id, e.terminal_name) for e in net.endpoints]
        if any(end not in ports for end in endpoints):
            return None
        net_segments = []
        for first, second in zip(endpoints, endpoints[1:]):
            start, a = ports[first]
            end, b = ports[second]
            x, y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            choices = (
                (a, (b[0], a[1]), b),
                (a, (a[0], b[1]), b),
                (a, (x, a[1]), (x, b[1]), b),
                (a, (a[0], y), (b[0], y), b),
            )
            for path in choices:
                segments = [_bounds(s, t) for s, t in zip(path, path[1:]) if s != t]
                if not segments:
                    continue
                leads = [_bounds(start, a), _bounds(end, b)]
                if any(
                    _intersects(segment, box, clearance)
                    for segment in segments
                    for box in boxes.values()
                ) or any(
                    _intersects(lead, box, clearance)
                    for lead, owner in zip(leads, (first[0], second[0]), strict=True)
                    for name, box in boxes.items()
                    if name != owner
                ):
                    continue
                if any(
                    _intersects(lead, wire, clearance)
                    for lead in leads
                    for wire in used
                ):
                    continue
                routes.append((start, *path, end))
                segments.extend(leads)
                net_segments.extend(segments)
                break
            else:
                return None
        used.extend(net_segments)
    return routes


def render(
    graph: Netlist,
    image_size: tuple[int, int] | None,
    component_features: list[dict],
    page: str = "A4",
    thickness: float = 1.1,
) -> dict:
    width, height = PAGE_SIZES[page]
    if not math.isfinite(thickness) or not 0.6 <= thickness <= 3:
        raise ValueError("Tactile line thickness must be between 0.6 and 3 mm.")
    margin = 12
    features = {row["component_id"]: row for row in component_features}
    part_key = [f"{part.id}: {part.canonical_category}" for part in graph.components]
    key = wrap("   /   ".join(part_key), 76)
    boxes = {}
    paths = None
    if image_size and graph.components and all(part.bbox for part in graph.components):
        image_w, image_h = image_size
        space_y = height - 55 - len(key) * 5
        if image_w > 0 and image_h > 0 and space_y > 30:
            scale = min((width - 2 * margin) / image_w, space_y / image_h)
            for part in graph.components:
                box = part.bbox
                x = margin + box.x * scale
                y = 25 + box.y * scale
                boxes[part.id] = (x, y, x + box.width * scale, y + box.height * scale)
            clear = thickness + 1.5
            items = list(boxes.values())
            if all(
                x2 - x1 >= 13 and y2 - y1 >= 9 for x1, y1, x2, y2 in items
            ) and not any(
                _intersects(a, b, clear)
                for i, a in enumerate(items)
                for b in items[i + 1 :]
            ):
                paths = _route(graph, boxes, features, clear)

    logical_height = height
    if paths is None:
        title = "Parts and connections"
        body = [
            _text(
                margin,
                22,
                "Wire layout omitted because a clear route could not be drawn.",
            )
        ]
        rows = ["Parts key", *key, "", "Nets (component.terminal)"]
        for net in graph.nets:
            ends = ", ".join(
                f"{e.component_id}.{e.terminal_name}" for e in net.endpoints
            )
            rows.extend(wrap(f"{net.name}: {ends}", 76, subsequent_indent="  "))
        for i, row in enumerate(rows):
            body.append(_text(margin, 35 + i * 5.4, row))
        logical_height = max(height, 48 + len(rows) * 5.4)
    else:
        title = "Raised circuit diagram"
        body = []
        for path in paths:
            points = " ".join(f"{x:.2f},{y:.2f}" for x, y in path)
            body.append(f'<polyline points="{points}" />')
        for part in graph.components:
            x1, y1, x2, y2 = boxes[part.id]
            body.append(
                f'<rect x="{x1:.2f}" y="{y1:.2f}" width="{x2 - x1:.2f}" '
                f'height="{y2 - y1:.2f}" fill="white"/>'
            )
            symbol = SYMBOLS.get(part.canonical_category)
            if symbol and y2 - y1 >= 15:
                center = (x1 + x2) / 2
                body.append(
                    f'<path d="{symbol}" '
                    f'transform="translate({center:.2f} {y1 + 5:.2f})"/>'
                )
            body.append(_text(x1 + 1.8, y2 - 2, part.id))
        endpoints = {point for path in paths for point in (path[0], path[-1])}
        body.extend(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="0.9" fill="black"/>'
            for x, y in sorted(endpoints)
        )
        body.append(_text(margin, height - 19 - len(key) * 5, "Parts key"))
        body.extend(
            _text(margin, height - 14 - (len(key) - i) * 5, row)
            for i, row in enumerate(key)
        )
    label = "Not validated by a tactile-graphics expert"
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}mm" height="{height}mm" '
        f'viewBox="0 0 {width} {logical_height}" role="img" aria-label="{title}">'
        f"<title>{title}</title><desc>{label}</desc>"
        '<rect width="100%" height="100%" fill="white"/>'
        "<style>text{font-family:monospace;stroke:none;fill:black}</style>"
        f'<g fill="none" stroke="black" stroke-width="{thickness}" '
        'stroke-linecap="round" stroke-linejoin="round">'
        f"{_text(margin, 15, title, 6)}{''.join(body)}"
        f"{_text(margin, logical_height - 8, label, 3.5)}</g></svg>"
    )
    return {"kind": "connections" if paths is None else "diagram", "svg": svg}


def tactile_output(
    netlist: dict, image_size: tuple[int, int] | None, features: list[dict]
):
    graph = Netlist.model_validate(netlist)
    thickness = float(os.environ.get("VCA_TACTILE_LINE_MM", "1.1"))
    return {
        page: render(graph, image_size, features, page=page, thickness=thickness)
        for page in PAGE_SIZES
    }
