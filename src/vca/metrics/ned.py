"""Normalized netlist edit distance (Image2Net NED).

GED on the canonical component-net graph with unit costs, divided by the
number of devices + nets + ports in the ground truth, as in Image2Net's
official ``validation/`` script and paper.
"""

from vca.metrics.alignment import align, ned_from_alignment
from vca.schemas.netlist import Netlist


def compute_ned(
    predicted: Netlist,
    ground_truth: Netlist,
    timeout: float = 30.0,
) -> float | None:
    """Return normalized GED, or None if undefined or no path was found."""
    return ned_from_alignment(
        align(predicted, ground_truth, timeout=timeout),
        ground_truth,
    )
