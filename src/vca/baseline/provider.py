"""Abstract interface for VLM providers."""

import os
from abc import ABC, abstractmethod
from pathlib import Path

from vca.baseline.errors import VLMConfigError


class VLMProvider(ABC):
    """Base class for concrete VLM providers."""

    required_env_var: str

    def __init__(self) -> None:
        """Validate that the provider's required environment variable exists."""
        if not getattr(self, "required_env_var", None):
            raise NotImplementedError(
                "Concrete providers must define required_env_var."
            )

        if not os.getenv(self.required_env_var):
            raise VLMConfigError(self.required_env_var)

    @abstractmethod
    def call(
        self,
        image_path: str | Path,
        correction_context: str | None = None,
    ) -> str:
        """Send an image to the VLM and return its raw response."""
        raise NotImplementedError