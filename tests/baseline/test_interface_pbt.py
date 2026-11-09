
"""Property-based tests for VLM retry behavior."""

from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from baseline.mock_provider import MockProvider
from vca.baseline.errors import VLMExhaustedError
from vca.baseline.interface import VLMInterface


# Feature: m1-data-audit-baseline, Property 7: VLM retry cycle
@given(max_retries=st.integers(min_value=1, max_value=10))
@settings(max_examples=100)
def test_invalid_json_exhausts_exactly_max_retries(
    max_retries: int,
) -> None:
    with patch.dict("os.environ", {"MOCK_VLM_API_KEY": "test-key"}):
        provider = MockProvider(["not valid JSON"])
        interface = VLMInterface(
            provider,
            max_retries=max_retries,
        )

        with pytest.raises(VLMExhaustedError) as exc_info:
            interface.predict("circuit.png")

        assert provider.call_count == max_retries
        assert exc_info.value.retries == max_retries
        assert exc_info.value.image_path.name == "circuit.png"
