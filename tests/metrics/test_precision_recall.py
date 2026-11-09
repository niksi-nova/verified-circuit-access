
from vca.metrics.precision_recall import (
    component_precision,
    component_recall,
    connection_precision,
    connection_recall,
)
from vca.schemas.annotation import AnnotationRecord, BoundingBox
from vca.schemas.netlist import (
    Component,
    Net,
    NetEndpoint,
    Netlist,
    Terminal,
)


def make_annotation(
    annotation_id: int,
    source_label: str = "resistor",
    x: float = 10,
) -> AnnotationRecord:
    return AnnotationRecord(
        id=annotation_id,
        image_id=1,
        category_id=1,
        bbox=BoundingBox(x=x, y=10, width=10, height=10),
        source_label=source_label,
        dataset_id="Image2Net",
    )


def make_netlist(
    component_ids: tuple[str, str] = ("C1", "C2"),
    net_name: str = "N1",
) -> Netlist:
    c1, c2 = component_ids

    return Netlist(
        components=[
            Component(
                id=c1,
                canonical_category="resistor",
                terminals=[Terminal(name="1")],
            ),
            Component(
                id=c2,
                canonical_category="capacitor",
                terminals=[Terminal(name="1")],
            ),
        ],
        nets=[
            Net(
                name=net_name,
                endpoints=[
                    NetEndpoint(component_id=c1, terminal_name="1"),
                    NetEndpoint(component_id=c2, terminal_name="1"),
                ],
            )
        ],
    )


def test_perfect_component_match():
    annotations = [make_annotation(1)]
    assert component_precision(annotations, annotations) == 1.0
    assert component_recall(annotations, annotations) == 1.0


def test_component_no_overlap():
    predicted = [make_annotation(1, x=100)]
    ground_truth = [make_annotation(2, x=10)]

    assert component_precision(predicted, ground_truth) == 0.0
    assert component_recall(predicted, ground_truth) == 0.0


def test_component_category_mismatch():
    predicted = [make_annotation(1, source_label="resistor")]
    ground_truth = [make_annotation(2, source_label="capacitor")]

    assert component_precision(predicted, ground_truth) == 0.0
    assert component_recall(predicted, ground_truth) == 0.0


def test_empty_component_inputs():
    assert component_precision([], []) is None
    assert component_recall([], []) is None


def test_one_missed_component():
    predicted = [make_annotation(1)]
    ground_truth = [make_annotation(2), make_annotation(3, x=100)]

    assert component_recall(predicted, ground_truth) == 0.5


def test_perfect_connection_match():
    predicted = make_netlist()
    ground_truth = make_netlist()

    assert connection_precision(predicted, ground_truth) == 1.0
    assert connection_recall(predicted, ground_truth) == 1.0


def test_connection_component_ids_can_be_renamed():
    predicted = make_netlist(("P1", "P2"))
    ground_truth = make_netlist(("G1", "G2"))

    assert connection_precision(predicted, ground_truth) == 1.0
    assert connection_recall(predicted, ground_truth) == 1.0


def test_connection_net_names_are_ignored():
    predicted = make_netlist(net_name="predicted_net")
    ground_truth = make_netlist(net_name="ground_truth_net")

    assert connection_precision(predicted, ground_truth) == 1.0
    assert connection_recall(predicted, ground_truth) == 1.0


def test_connection_no_overlap():
    predicted = make_netlist(("P1", "P2"))
    ground_truth = make_netlist(("G1", "G2"))

    # Different component categories make the graphs incompatible.
    predicted.components[0].canonical_category = "inductor"

    assert connection_precision(predicted, ground_truth) == 0.0
    assert connection_recall(predicted, ground_truth) == 0.0


def test_empty_connection_inputs():
    empty = Netlist(components=[], nets=[])
    nonempty = make_netlist()

    assert connection_precision(empty, nonempty) is None
    assert connection_recall(empty, nonempty) == 0.0