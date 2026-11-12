"""Run DC calculations with ngspice using a validated, generated deck."""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, FiniteFloat

from vca.schemas.netlist import Netlist

PARTS = {"resistor": "R", "voltage": "V", "current": "I"}
MARKERS = {"ground", "port", "vdd"}
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?"


class SpiceRequest(BaseModel):
    netlist: Netlist
    values: dict[str, FiniteFloat]
    operation: Literal["resistance", "voltages"]
    reference: str
    target: str | None = None


def available() -> bool:
    return shutil.which("ngspice") is not None


def simulate(request: SpiceRequest) -> dict:
    if not available():
        raise ValueError("ngspice is unavailable. Calculation not run.")
    graph = request.netlist
    if len(graph.components) > 200 or len(graph.nets) > 400:
        raise ValueError("This circuit is too large for the local calculation.")
    unsupported = sorted(
        {
            c.canonical_category
            for c in graph.components
            if c.canonical_category not in PARTS and c.canonical_category not in MARKERS
        }
    )
    if unsupported:
        raise ValueError(f"Not supported yet: {', '.join(unsupported)}.")
    nodes = {net.name: f"n{i}" for i, net in enumerate(graph.nets, 1)}
    resistance = request.operation == "resistance"
    if request.reference not in nodes or (
        resistance
        and (request.target not in nodes or request.target == request.reference)
    ):
        raise ValueError(
            "Select a reference net and, for resistance, a different test net."
        )
    nodes[request.reference] = "0"
    terminal_nodes = {
        (end.component_id, end.terminal_name): nodes[net.name]
        for net in graph.nets
        for end in net.endpoints
    }
    deck = ["Braille Press: teacher-entered DC circuit"]
    adjacency: dict[str, set[str]] = {node: set() for node in nodes.values()}
    for index, component in enumerate(graph.components, 1):
        category = component.canonical_category
        if category in MARKERS:
            continue
        value = request.values.get(component.id)
        if value is None or (category == "resistor" and value <= 0):
            raise ValueError(f"Enter a valid value for {component.id}.")
        terminals = [t.name for t in component.terminals]
        if category in {"voltage", "current"}:
            order = ["Positive", "Negative"] if category == "voltage" else ["In", "Out"]
            if set(terminals) != set(order):
                raise ValueError(f"Source polarity is unclear for {component.id}.")
            terminals = order
        ends = [terminal_nodes.get((component.id, name)) for name in terminals]
        if len(ends) != 2 or any(node is None for node in ends):
            raise ValueError(f"Check the two terminal connections for {component.id}.")
        a, b = ends
        if a == b and category == "voltage" and value != 0 and not resistance:
            raise ValueError(f"Voltage source {component.id} is shorted.")
        if a == b or (resistance and category == "current"):
            continue
        if category != "current":
            adjacency[a].add(b)
            adjacency[b].add(a)
        if resistance and category == "voltage":
            value = 0.0
        deck.append(f"{PARTS[category]}{index} {a} {b} {value:.16g}")

    connected = {"0"}
    frontier = ["0"]
    while frontier:
        for neighbor in adjacency[frontier.pop()] - connected:
            connected.add(neighbor)
            frontier.append(neighbor)
    if resistance and nodes[request.target] not in connected:
        raise ValueError("There is no DC path between the selected nets.")
    if set(nodes.values()) != connected or len(deck) == 1:
        raise ValueError(
            "The circuit has floating nets. Check its connections and reference."
        )

    measurements = {}
    if resistance:
        target = nodes[request.target]
        deck.extend(
            [
                "* Independent sources deactivated; inject 1 A into the test net",
                f"Itest 0 {target} 1",
            ]
        )
        measurements["equivalent resistance"] = f"v({target}) / 1"
    else:
        measurements = {
            name: "0" if node == "0" else f"v({node})" for name, node in nodes.items()
        }
    deck.extend([".control", "set numdgt=12", "op"])
    for index, expression in enumerate(measurements.values()):
        deck.extend([f"let reading{index} = {expression}", f"print reading{index}"])
    deck.extend(["quit", ".endc", ".end", ""])
    source = "\n".join(deck)
    try:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "circuit.cir"
            path.write_text(source, encoding="ascii")
            run = subprocess.run(
                ["ngspice", "-n", "-b", path.name],
                cwd=folder,
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("ngspice could not complete the calculation.") from exc
    if run.returncode or re.search(r"error|singular|failed", run.stderr, re.I):
        raise ValueError(
            "ngspice could not solve this circuit. Check the values and wiring."
        )
    values = {}
    for index, label in enumerate(measurements):
        match = re.search(
            rf"^reading{index}\s*=\s*({NUMBER})\s*$", run.stdout, re.M | re.I
        )
        if not match or not math.isfinite(float(match[1])):
            raise ValueError("ngspice did not return a finite reading.")
        values[label] = float(match[1])
    return {
        "unit": "Ω" if resistance else "V",
        "values": values,
        "deck": source,
        "nodes": nodes,
    }
