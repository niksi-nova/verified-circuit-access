"""Mock VLM provider for testing."""

from pathlib import Path

from vca.baseline.provider import VLMProvider


class MockProvider(VLMProvider):
    """Return configured responses without making HTTP requests."""

    required_env_var = "MOCK_VLM_API_KEY"

    def __init__(
        self,
        responses: list[str],
    ) -> None:
        """Initialize the mock provider with pre-canned responses."""
        super().__init__()

        self.responses = responses
        self.call_count = 0
        self.call_arguments: list[
            tuple[str | Path, str | None]
        ] = []

    def call(
        self,
        image_path: str | Path,
        correction_context: str | None = None,
    ) -> str:
        self.call_count += 1
        self.call_arguments.append((image_path, correction_context))

        response_index = min(
            self.call_count - 1,
            len(self.responses) - 1,
        )

        return self.responses[response_index]