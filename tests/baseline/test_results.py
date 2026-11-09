"""Tests for evaluation results storage."""

import json
import re
from pathlib import Path

from vca.baseline.results import ResultsStore


def test_save_creates_expected_files(tmp_path: Path):
    result = {"accuracy": 0.95}
    config = {"seed": 42}

    metrics_path = ResultsStore.save(
        result=result,
        run_id="test_run",
        config=config,
        output_dir=tmp_path,
    )

    config_path = tmp_path / "test_run_metrics.config.json"

    assert metrics_path == tmp_path / "test_run_metrics.json"
    assert metrics_path.exists()
    assert config_path.exists()

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    saved_config = json.loads(config_path.read_text(encoding="utf-8"))

    assert metrics == result
    assert saved_config["seed"] == 42
    assert "git_sha" in saved_config


def test_save_collision_preserves_original_files(tmp_path: Path):
    first_result = {"accuracy": 0.80}
    second_result = {"accuracy": 0.95}
    config = {"seed": 42}

    first_path = ResultsStore.save(
        result=first_result,
        run_id="duplicate_run",
        config=config,
        output_dir=tmp_path,
    )

    second_path = ResultsStore.save(
        result=second_result,
        run_id="duplicate_run",
        config=config,
        output_dir=tmp_path,
    )

    assert first_path.exists()
    assert second_path.exists()
    assert first_path != second_path

    # The original result must not be overwritten.
    original = json.loads(first_path.read_text(encoding="utf-8"))
    assert original == first_result

    # The second result should be stored in a timestamped directory.
    timestamped_dir = second_path.parent
    assert timestamped_dir != tmp_path
    assert re.fullmatch(
        r"duplicate_run_\d{8}T\d{6}Z",
        timestamped_dir.name,
    )

    second = json.loads(second_path.read_text(encoding="utf-8"))
    assert second == second_result

    second_config = (
        timestamped_dir / "duplicate_run_metrics.config.json"
    )
    assert second_config.exists()