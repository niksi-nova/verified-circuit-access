"""Exceptions used by the VLM baseline."""

from pathlib import Path


class VLMExhaustedError(RuntimeError):
    """Raised when all VLM prediction retries are exhausted."""

    def __init__(
        self,
        image_path: str | Path,
        retries: int,
        final_error: Exception | str,
    ) -> None:
        self.image_path = Path(image_path)
        self.retries = retries
        self.final_error = final_error

        super().__init__(
            f"VLM failed after {retries} retries for "
            f"{self.image_path}: {final_error}"
        )


class VLMConfigError(RuntimeError):
    """Raised when required VLM configuration is missing."""

    def __init__(self, variable_name: str) -> None:
        self.variable_name = variable_name

        super().__init__(
            f"Required environment variable '{variable_name}' is not set."
        )


class ApprovalRequiredError(RuntimeError):
    """Raised when explicit approval is required for an operation."""