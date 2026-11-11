
"""Tests for the circuit evaluation framework."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

import vca.baseline.evaluation as evaluation_module
from vca.baseline.errors import ApprovalRequiredError
from vca.baseline.evaluation import run_evaluation
from vca.baseline.interface import VLMInterface
from vca.baseline.provider import VLMProvider
from vca.data.image2net import load_validation_netlist


class LocalMockProvider(VLMProvider):
    """Mock VLM provider that returns a configured response."""

    required_env_var = "MOCK_VLM_API_KEY"

    def __init__(self, response: str) -> None:
        super().__init__()
        self.response = response
        self.call_count = 0

    def call(
        self,
        image_path: str | Path,
        correction_context: str | None = None,
    ) -> str:
        self.call_count += 1
        return self.response


def _create_evaluation_inputs(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path, Path]:
    """Create handwritten circuit, netlist, and annotation fixtures."""
    image_dir = tmp_path / "images"
    netlist_dir = tmp_path / "netlists"
    output_dir = tmp_path / "output"

    image_dir.mkdir()
    netlist_dir.mkdir()

    image_path = image_dir / "circuit_001.png"
    Image.new("RGB", (300, 150), "white").save(image_path)

    ground_truth_data = [
        {
            "ckt_netlist": [
                {
                    "component_type": "RESISTOR",
                    "port_connection": {
                        "1": "N1",
                        "2": "N2",
                    },
                },
                {
                    "component_type": "RESISTOR",
                    "port_connection": {
                        "1": "N1",
                        "2": "N2",
                    },
                },
            ]
        }
    ]

    netlist_path = netlist_dir / "circuit_001.json"
    netlist_path.write_text(
        json.dumps(ground_truth_data),
        encoding="utf-8",
    )

    fixture_path = (
        Path(__file__).parents[1]
        / "data"
        / "fixtures"
        / "labelme_sample.json"
    )

    annotation_path = netlist_dir / "circuit_001_labelme.json"
    annotation_path.write_bytes(fixture_path.read_bytes())

    return (
        image_dir,
        netlist_dir,
        output_dir,
        image_path,
        netlist_path,
        annotation_path,
    )


def _load_ground_truth(netlist_path: Path):
    """Load the single ground-truth netlist from the fixture."""
    return load_validation_netlist(netlist_path)[0]


def _make_missing_component_prediction(ground_truth):
    """Return a netlist-only prediction missing one component."""
    return ground_truth.model_copy(
        update={
            "components": ground_truth.components[:1],
            "nets": [],
        }
    )


@pytest.mark.parametrize(
    ("data_approved", "vlm_approved"),
    [
        (False, False),
        (False, True),
        (True, False),
    ],
)
def test_evaluation_requires_both_approvals(
    tmp_path: Path,
    data_approved: bool,
    vlm_approved: bool,
) -> None:
    """Evaluation must stop before accessing data or calling the VLM."""
    vlm = Mock()
    missing_image_dir = tmp_path / "does_not_exist"

    with pytest.raises(ApprovalRequiredError):
        run_evaluation(
            image_dir=missing_image_dir,
            netlist_dir=tmp_path / "missing_netlists",
            vlm=vlm,
            output_dir=tmp_path / "output",
            data_approved=data_approved,
            vlm_approved=vlm_approved,
        )

    vlm.predict.assert_not_called()
    assert not missing_image_dir.exists()
    assert not (tmp_path / "output").exists()


def test_missing_netlist_is_skipped(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A circuit without a matching netlist should be skipped."""
    image_dir = tmp_path / "images"
    netlist_dir = tmp_path / "netlists"
    output_dir = tmp_path / "output"

    image_dir.mkdir()
    netlist_dir.mkdir()

    Image.new("RGB", (100, 100), "white").save(
        image_dir / "circuit_001.png"
    )

    vlm = Mock()
    vlm.provider = Mock()
    vlm.provider.model_identifier = "test-model"

    with caplog.at_level(logging.WARNING):
        result = run_evaluation(
            image_dir=image_dir,
            netlist_dir=netlist_dir,
            vlm=vlm,
            output_dir=output_dir,
            data_approved=True,
            vlm_approved=True,
        )

    assert len(result.circuits) == 1
    assert result.circuits[0].circuit_id == "circuit_001"
    assert result.circuits[0].skipped is True
    assert "Missing netlist" in result.circuits[0].skip_reason
    assert "ground-truth netlist not found" in caplog.text

    vlm.predict.assert_not_called()
    assert len(result.metrics.per_pair) == 0


def test_correct_prediction_is_classified_correct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An isomorphic VLM prediction should be classified as correct."""
    monkeypatch.setenv("MOCK_VLM_API_KEY", "test-key")

    (
        image_dir,
        netlist_dir,
        output_dir,
        _,
        netlist_path,
        _,
    ) = _create_evaluation_inputs(tmp_path)

    ground_truth = _load_ground_truth(netlist_path)

    provider = LocalMockProvider(
        response=ground_truth.model_dump_json()
    )
    vlm = VLMInterface(provider=provider)

    result = run_evaluation(
        image_dir=image_dir,
        netlist_dir=netlist_dir,
        vlm=vlm,
        output_dir=output_dir,
        data_approved=True,
        vlm_approved=True,
    )

    assert provider.call_count == 1
    assert len(result.circuits) == 1
    assert result.circuits[0].failure_categories == ["correct"]
    assert result.circuits[0].skipped is False
    assert result.metrics.per_pair[0].graph_isomorphism is True


def test_missing_component_is_classified_from_alignment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dropped component is reported as missed via graph alignment."""
    monkeypatch.setenv("MOCK_VLM_API_KEY", "test-key")

    image_dir = tmp_path / "images"
    netlist_dir = tmp_path / "netlists"
    output_dir = tmp_path / "output"

    image_dir.mkdir()
    netlist_dir.mkdir()

    Image.new("RGB", (100, 100), "white").save(
        image_dir / "circuit_001.png"
    )

    ground_truth_data = [
        {
            "ckt_netlist": [
                {
                    "component_type": "RESISTOR",
                    "port_connection": {
                        "1": "N1",
                        "2": "N2",
                    },
                },
                {
                    "component_type": "RESISTOR",
                    "port_connection": {
                        "1": "N1",
                        "2": "N2",
                    },
                },
            ]
        }
    ]

    netlist_path = netlist_dir / "circuit_001.json"
    netlist_path.write_text(
        json.dumps(ground_truth_data),
        encoding="utf-8",
    )

    ground_truth = _load_ground_truth(netlist_path)
    predicted_data = _make_missing_component_prediction(ground_truth)

    provider = LocalMockProvider(
        response=predicted_data.model_dump_json()
    )
    vlm = VLMInterface(provider=provider)

    result = run_evaluation(
        image_dir=image_dir,
        netlist_dir=netlist_dir,
        vlm=vlm,
        output_dir=output_dir,
        data_approved=True,
        vlm_approved=True,
    )

    assert provider.call_count == 1
    circuit = result.circuits[0]
    # One resistor is gone; the kept one lost its nets (prediction has none).
    assert circuit.failure_categories == ["missed_component", "wrong_connection"]
    assert result.metrics.per_pair[0].graph_isomorphism is False
    assert result.metrics.per_pair[0].component_recall == 0.5
    assert result.error_counts == {"missed_component": 1, "wrong_connection": 1}

    # Failures always get an overlay, even without ground-truth boxes.
    assert len(list(output_dir.rglob("*_overlay.png"))) == 1
    # The raw prediction is saved for re-scoring.
    assert len(list(output_dir.rglob("predictions/circuit_001.json"))) == 1


def test_overlay_and_manifest_are_generated_for_failure_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed prediction produces an overlay with a legend panel."""
    monkeypatch.setenv("MOCK_VLM_API_KEY", "test-key")

    (
        image_dir,
        netlist_dir,
        output_dir,
        image_path,
        netlist_path,
        annotation_path,
    ) = _create_evaluation_inputs(tmp_path)

    ground_truth = _load_ground_truth(netlist_path)
    predicted_data = _make_missing_component_prediction(ground_truth)

    provider = LocalMockProvider(
        response=predicted_data.model_dump_json()
    )
    vlm = VLMInterface(provider=provider)

    result = run_evaluation(
        image_dir=image_dir,
        netlist_dir=netlist_dir,
        vlm=vlm,
        output_dir=output_dir,
        data_approved=True,
        vlm_approved=True,
    )

    assert provider.call_count == 1
    assert "missed_component" in result.circuits[0].failure_categories

    # The overlay keeps the image width and adds a legend strip below it.
    overlays = list(output_dir.rglob("circuit_001_overlay.png"))
    assert len(overlays) == 1

    with Image.open(overlays[0]) as overlay:
        assert overlay.width == 300
        assert overlay.height > 150

    # Verify manifest.
    manifest_files = list(
        (output_dir / "results").rglob("*_manifest.json")
    )
    assert len(manifest_files) == 1

    manifest = json.loads(
        manifest_files[0].read_text(encoding="utf-8")
    )

    assert manifest["run_id"]

    entries = {
        entry["file_path"]: entry["sha256"]
        for entry in manifest["entries"]
    }

    assert str(image_path) in entries
    assert str(netlist_path) in entries
    assert str(annotation_path) in entries

    # Verify actual SHA-256 values, not just checksum length.
    assert entries[str(image_path)] == hashlib.sha256(
        image_path.read_bytes()
    ).hexdigest()

    assert entries[str(netlist_path)] == hashlib.sha256(
        netlist_path.read_bytes()
    ).hexdigest()

    assert entries[str(annotation_path)] == hashlib.sha256(
        annotation_path.read_bytes()
    ).hexdigest()

    assert all(len(checksum) == 64 for checksum in entries.values())


def test_repeated_run_preserves_metrics_config_and_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated run IDs must preserve each run's complete artifacts."""
    monkeypatch.setenv("MOCK_VLM_API_KEY", "test-key")

    class FixedDatetime(datetime):
        """Provide a deterministic evaluation run ID."""

        @classmethod
        def now(cls, tz=None):
            return cls(
                2026,
                11,
                9,
                12,
                0,
                0,
                tzinfo=tz,
            )

    monkeypatch.setattr(
        evaluation_module,
        "datetime",
        FixedDatetime,
    )

    (
        image_dir,
        netlist_dir,
        output_dir,
        _,
        netlist_path,
        _,
    ) = _create_evaluation_inputs(tmp_path)

    ground_truth = _load_ground_truth(netlist_path)

    provider = LocalMockProvider(
        response=ground_truth.model_dump_json()
    )
    vlm = VLMInterface(provider=provider)

    first_result = run_evaluation(
        image_dir=image_dir,
        netlist_dir=netlist_dir,
        vlm=vlm,
        output_dir=output_dir,
        data_approved=True,
        vlm_approved=True,
    )

    second_result = run_evaluation(
        image_dir=image_dir,
        netlist_dir=netlist_dir,
        vlm=vlm,
        output_dir=output_dir,
        data_approved=True,
        vlm_approved=True,
    )

    assert provider.call_count == 2
    assert first_result.circuits[0].failure_categories == ["correct"]
    assert second_result.circuits[0].failure_categories == ["correct"]

    results_dir = output_dir / "results"

    manifest_files = sorted(
        results_dir.rglob("*_manifest.json")
    )

    # Both manifests must survive even though both runs have the same run ID.
    assert len(manifest_files) == 2

    run_id = "evaluation_20261109T120000Z"

    for manifest_path in manifest_files:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )

        assert manifest["run_id"] == run_id

        # Each manifest must live beside its own metrics and config files.
        assert (
            manifest_path.parent / f"{run_id}_metrics.json"
        ).is_file()

        assert (
            manifest_path.parent / f"{run_id}_metrics.config.json"
        ).is_file()


def test_saved_predictions_can_be_rescored_without_vlm_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passing predictions_dir re-scores saved predictions offline."""
    monkeypatch.setenv("MOCK_VLM_API_KEY", "test-key")

    image_dir, netlist_dir, output_dir, _, netlist_path, _ = (
        _create_evaluation_inputs(tmp_path)
    )
    ground_truth = _load_ground_truth(netlist_path)

    first = LocalMockProvider(response=ground_truth.model_dump_json())
    run_evaluation(
        image_dir=image_dir,
        netlist_dir=netlist_dir,
        vlm=VLMInterface(provider=first),
        output_dir=output_dir,
        data_approved=True,
        vlm_approved=True,
    )
    saved = next(output_dir.rglob("predictions")).resolve()

    second = LocalMockProvider(response="not json")
    result = run_evaluation(
        image_dir=image_dir,
        netlist_dir=netlist_dir,
        vlm=VLMInterface(provider=second),
        output_dir=tmp_path / "rescored",
        data_approved=True,
        vlm_approved=True,
        predictions_dir=saved,
    )

    assert second.call_count == 0
    assert result.circuits[0].failure_categories == ["correct"]
