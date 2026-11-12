"""Read-only view over a predicted netlist, built for the explanation layer.

Works on the plain dicts found in a pipeline prediction's ``netlist`` field
(the same shape as ``vca.schemas.netlist.Netlist.model_dump(mode="json")``),
not on the pydantic model, so test fixtures can be tiny hand-written dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# A row-grouping tolerance for reading order: two boxes whose vertical
# centers are closer than this fraction of the median box height are
# treated as being "on the same row" of the drawing.
ROW_TOLERANCE_FRACTION = 0.6

_GROUND_NAMES = {"gnd", "ground"}


def _is_ground_net(raw_name: str) -> bool:
    return raw_name.strip().lower() in _GROUND_NAMES


def _is_supply_net(raw_name: str) -> bool:
    return raw_name.strip().lower().startswith("vdd")


@dataclass
class CircuitGraph:
    """Component/net lookups plus a deterministic reading order and net
    display names, derived only from the predicted netlist (no ground
    truth)."""

    netlist: dict
    components: dict[str, dict] = field(default_factory=dict)
    reading_order: list[str] = field(default_factory=list)
    terminal_net: dict[tuple[str, str], str] = field(default_factory=dict)
    net_endpoints: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    net_label: dict[str, str] = field(default_factory=dict)

    @classmethod
    def build(cls, netlist: dict) -> CircuitGraph:
        graph = cls(netlist=netlist)
        graph.components = {c["id"]: c for c in netlist["components"]}
        graph.reading_order = _reading_order(netlist["components"])

        for net in netlist["nets"]:
            endpoints = [
                (e["component_id"], e["terminal_name"]) for e in net["endpoints"]
            ]
            graph.net_endpoints[net["name"]] = endpoints
            for endpoint in endpoints:
                graph.terminal_net[endpoint] = net["name"]

        graph.net_label = _net_labels(
            netlist["nets"], netlist["components"], graph.reading_order
        )
        return graph

    def net_of(self, component_id: str, terminal_name: str) -> str | None:
        return self.terminal_net.get((component_id, terminal_name))

    def label_of(self, raw_net_name: str) -> str:
        return self.net_label.get(raw_net_name, raw_net_name)

    def other_endpoints(
        self, raw_net_name: str, exclude: tuple[str, str]
    ) -> list[tuple[str, str]]:
        return [e for e in self.net_endpoints.get(raw_net_name, []) if e != exclude]


def _reading_order(components: list[dict]) -> list[str]:
    """Top-left to bottom-right reading order.

    Components are bucketed into rows by vertical center, using a
    tolerance of ``ROW_TOLERANCE_FRACTION`` times the median box height
    (components with no bbox form their own row, in id order, after every
    boxed component). Within a row, components are sorted left to right by
    the x of their box; rows are then sorted top to bottom.
    """
    boxed = [c for c in components if c.get("bbox")]
    unboxed = [c for c in components if not c.get("bbox")]

    if not boxed:
        return [c["id"] for c in unboxed]

    heights = sorted(c["bbox"]["height"] for c in boxed)
    median_height = heights[len(heights) // 2]
    tolerance = max(median_height * ROW_TOLERANCE_FRACTION, 1e-6)

    centers = [
        (c["id"], c["bbox"]["y"] + c["bbox"]["height"] / 2, c["bbox"]["x"])
        for c in boxed
    ]
    centers.sort(key=lambda row: row[1])

    rows: list[list[tuple[str, float, float]]] = []
    for item in centers:
        if rows and abs(item[1] - rows[-1][-1][1]) <= tolerance:
            rows[-1].append(item)
        else:
            rows.append([item])

    ordered: list[str] = []
    for row in rows:
        for comp_id, _, _ in sorted(row, key=lambda r: r[2]):
            ordered.append(comp_id)
    ordered.extend(c["id"] for c in unboxed)
    return ordered


def _net_labels(
    nets: list[dict], components: list[dict], reading_order: list[str]
) -> dict[str, str]:
    """Deterministic display names: literal ground/VDD nets get fixed
    names; everything else is numbered "net N" in the order its first
    endpoint is reached by walking components in reading order, then
    terminals in the order each component lists them, so two runs over
    the same prediction produce the same numbering."""
    names_by_raw = {net["name"]: net for net in nets}
    labels: dict[str, str] = {}
    for raw_name in names_by_raw:
        if _is_ground_net(raw_name):
            labels[raw_name] = "ground"
        elif _is_supply_net(raw_name):
            labels[raw_name] = "supply"

    endpoint_to_net = {
        (e["component_id"], e["terminal_name"]): net["name"]
        for net in nets
        for e in net["endpoints"]
    }
    order_rank = {comp_id: i for i, comp_id in enumerate(reading_order)}
    terminal_rank = {
        (c["id"], t["name"]): i
        for c in components
        for i, t in enumerate(c["terminals"])
    }

    def endpoint_sort_key(item):
        (comp_id, terminal_name), _ = item
        return (
            order_rank.get(comp_id, len(reading_order)),
            terminal_rank.get((comp_id, terminal_name), 0),
            terminal_name,
        )

    counter = 1
    for (comp_id, terminal_name), net_name in sorted(
        endpoint_to_net.items(), key=endpoint_sort_key
    ):
        if net_name in labels:
            continue
        labels[net_name] = f"net {counter}"
        counter += 1

    return labels
