"""Store evaluation metrics and run configuration."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class ResultsStore:
    """Persist metrics and configuration for an evaluation run."""

    @staticmethod
    def _get_git_sha() -> str | None:
        """Return the current Git SHA, or None if unavailable."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    @staticmethod
    def _serialize_result(result: Any) -> str:
        """Serialize a Pydantic model or JSON-compatible result."""
        if isinstance(result, BaseModel):
            return result.model_dump_json(indent=2)

        return json.dumps(result, indent=2, default=str)

    @classmethod
    def save(
        cls,
        result: Any,
        run_id: str,
        config: dict[str, Any],
        output_dir: str | Path,
    ) -> Path:
        """Save metrics and configuration, avoiding run ID collisions."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        metrics_path = output_dir / f"{run_id}_metrics.json"
        config_path = output_dir / f"{run_id}_metrics.config.json"

        if metrics_path.exists() or config_path.exists():
            timestamp = datetime.now(UTC).strftime(
                "%Y%m%dT%H%M%SZ"
            )
            output_dir = output_dir / f"{run_id}_{timestamp}"
            output_dir.mkdir(parents=True, exist_ok=True)

            metrics_path = output_dir / f"{run_id}_metrics.json"
            config_path = output_dir / f"{run_id}_metrics.config.json"

        config_with_provenance = dict(config)
        config_with_provenance["git_sha"] = cls._get_git_sha()

        metrics_path.write_text(
            cls._serialize_result(result),
            encoding="utf-8",
        )
        config_path.write_text(
            json.dumps(config_with_provenance, indent=2, default=str),
            encoding="utf-8",
        )

        return metrics_path