
from unittest.mock import patch

from vca.metrics.summary import compute_metrics
from vca.schemas.annotation import AnnotationRecord, BoundingBox
from vca.schemas.netlist import (
    Component,
    Net,
    NetEndpoint,
    Netlist,
    Terminal,
)


def make_netlist() -> Netlist:
    return Netlist(
        components=[
            Component(
                id="C1",
                canonical_category="resistor",
                terminals=[Terminal(name="1")],
            ),
            Component(
                id="C2",
                canonical_category="capacitor",
                terminals=[Terminal(name="1")],
            ),
        ],
        nets=[
            Net(
                name="N1",
                endpoints=[
                    NetEndpoint(component_id="C1", terminal_name="1"),
                    NetEndpoint(component_id="C2", terminal_name="1"),
                ],
            )
        ],
    )


def make_annotation() -> AnnotationRecord:
    return AnnotationRecord(
        id=1,
        image_id=1,
        category_id=22,
        bbox=BoundingBox(x=10, y=10, width=10, height=10),
        source_label="resistor",
        dataset_id="Image2Net",
    )


def test_empty_summary():
    summary = compute_metrics([], [])

    assert summary.per_pair == []
    assert summary.macro_ned is None
    assert summary.macro_graph_isomorphism_accuracy is None
    assert summary.macro_component_precision is None
    assert summary.macro_component_recall is None
    assert summary.macro_connection_precision is None
    assert summary.macro_connection_recall is None


@patch("vca.metrics.summary.compute_ned", return_value=0.0)
def test_single_perfect_pair(mock_ned):
    netlist = make_netlist()
    annotations = [make_annotation()]

    summary = compute_metrics(
        pairs=[(netlist, netlist)],
        annotation_pairs=[(annotations, annotations)],
    )

    assert len(summary.per_pair) == 1
    assert summary.per_pair[0].ned == 0.0
    assert summary.per_pair[0].graph_isomorphism is True
    assert summary.per_pair[0].component_precision == 1.0
    assert summary.per_pair[0].component_recall == 1.0
    assert summary.per_pair[0].connection_precision == 1.0
    assert summary.per_pair[0].connection_recall == 1.0

    assert summary.macro_ned == 0.0
    assert summary.macro_graph_isomorphism_accuracy == 1.0
    assert summary.macro_component_precision == 1.0
    assert summary.macro_component_recall == 1.0
    assert summary.macro_connection_precision == 1.0
    assert summary.macro_connection_recall == 1.0

    mock_ned.assert_called_once_with(netlist, netlist)


@patch("vca.metrics.summary.compute_ned", return_value=0.0)
def test_summary_json_roundtrip(mock_ned):
    netlist = make_netlist()
    annotations = [make_annotation()]

    summary = compute_metrics(
        pairs=[(netlist, netlist)],
        annotation_pairs=[(annotations, annotations)],
    )

    restored = type(summary).model_validate_json(summary.model_dump_json())

    assert restored == summary


def test_mismatched_pair_counts_raise():
    netlist = make_netlist()

    try:
        compute_metrics(
            pairs=[(netlist, netlist)],
            annotation_pairs=[],
        )
    except ValueError as exc:
        assert "same number of circuits" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
