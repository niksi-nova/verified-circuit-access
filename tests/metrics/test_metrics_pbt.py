
"""Property-based tests for metric identity invariants."""

from hypothesis import given, settings
from hypothesis import strategies as st

from vca.metrics.graph_iso import are_isomorphic
from vca.metrics.precision_recall import (
    component_precision,
    component_recall,
    connection_precision,
    connection_recall,
)
from vca.schemas.annotation import AnnotationRecord, BoundingBox
from vca.schemas.netlist import Component, Net, NetEndpoint, Netlist, Terminal
from vca.schemas.taxonomy import TAXONOMY


@st.composite
def valid_netlist_cases(draw):
    """Generate a valid netlist and its corresponding annotations."""
    component_count = draw(st.integers(min_value=2, max_value=10))

    taxonomy_entries = draw(
        st.lists(
            st.sampled_from(TAXONOMY.entries),
            min_size=component_count,
            max_size=component_count,
        )
    )

    components = []
    annotations = []

    for index, entry in enumerate(taxonomy_entries):
        component_id = f"C{index + 1}"

        components.append(
            Component(
                id=component_id,
                canonical_category=entry.canonical_name,
                terminals=[
                    Terminal(name="T0"),
                    Terminal(name="T1"),
                ],
            )
        )

        annotations.append(
            AnnotationRecord(
                id=index + 1,
                image_id=1,
                category_id=entry.canonical_id,
                bbox=BoundingBox(
                    x=index * 20,
                    y=0,
                    width=10,
                    height=10,
                ),
                segmentation=[],
                orientation=None,
                source_label=entry.source_label,
                dataset_id=entry.dataset_name,
            )
        )

    # Connect the first terminal of every component to one net.
    endpoints = [
        NetEndpoint(
            component_id=f"C{index + 1}",
            terminal_name="T0",
        )
        for index in range(component_count)
    ]

    netlist = Netlist(
        schema_version="1.0.0",
        components=components,
        nets=[
            Net(
                name="N1",
                endpoints=endpoints,
            )
        ],
    )

    return netlist, annotations


# Feature: m1-data-audit-baseline, Property 6: Metrics identity invariant
@given(case=valid_netlist_cases())
@settings(max_examples=100)
def test_metrics_identity_invariant(case):
    netlist, annotations = case

    # Graph topology must match itself.
    assert are_isomorphic(netlist, netlist) is True

    # Identical annotations must have perfect component metrics.
    assert component_precision(annotations, annotations) == 1.0
    assert component_recall(annotations, annotations) == 1.0

    # Identical netlists must have perfect connection metrics.
    assert connection_precision(netlist, netlist) == 1.0
    assert connection_recall(netlist, netlist) == 1.0
