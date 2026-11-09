"""
Normalized Edit Distance (NED) for circuit netlists.

Reference: Image2Net, arXiv:2508.13157, Section II-B.

Paper formula:
    NED = GED / (N_devices + N_nets + N_ports)

The paper describes unit-cost graph edit operations (insertions,
deletions, and substitutions).

Normalization uses the ground-truth graph's device, net, and port count.

Verification note:
    The official validation entry point appears to report raw GED.
    The paper's normalization is not confirmed in that entry point.

Empty ground-truth graphs have a zero denominator. Their behavior
requires explicit project-level handling after reference verification.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vca.schemas.netlist import Netlist


def compute_ned(
    predicted: "Netlist",
    ground_truth: "Netlist",
) -> float | None:
    """Compute normalized edit distance between two circuit netlists."""
    raise NotImplementedError(
        "NED verification is incomplete. Verify the paper formula, "
        "official implementation, and empty-netlist behavior before "
        "implementing compute_ned."
    )
