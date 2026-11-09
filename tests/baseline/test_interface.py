"""Tests for the VLM interface."""

import json
from io import StringIO

import pytest

from baseline.mock_provider import MockProvider
from vca.baseline.errors import VLMConfigError, VLMExhaustedError
from vca.baseline.interface import VLMInterface


@pytest.fixture(autouse=True)
def mock_api_key(monkeypatch):
    """Provide a fake API key for mock-provider tests."""
    monkeypatch.setenv("MOCK_VLM_API_KEY", "test-key")


@pytest.fixture
def valid_netlist_json():
    """Return a valid empty netlist JSON response."""
    return json.dumps(
        {
            "schema_version": "1.0.0",
            "components": [],
            "nets": [],
        }
    )


def test_valid_response_succeeds_on_first_call(valid_netlist_json):
    provider = MockProvider([valid_netlist_json])
    interface = VLMInterface(provider)

    result = interface.predict("circuit.png")

    assert result.schema_version == "1.0.0"
    assert provider.call_count == 1


def test_invalid_response_exhausts_retries():
    provider = MockProvider(["not valid JSON"])
    interface = VLMInterface(provider, max_retries=3)

    with pytest.raises(VLMExhaustedError) as exc_info:
        interface.predict("circuit.png")

    assert provider.call_count == 3
    assert exc_info.value.retries == 3
    assert exc_info.value.image_path.name == "circuit.png"


def test_provider_fails_twice_then_succeeds(valid_netlist_json):
    provider = MockProvider(
        [
            "invalid JSON",
            "still invalid",
            valid_netlist_json,
        ]
    )
    interface = VLMInterface(provider, max_retries=3)

    result = interface.predict("circuit.png")

    assert result.schema_version == "1.0.0"
    assert provider.call_count == 3
    assert provider.call_arguments[1][1] is not None


@pytest.mark.parametrize("max_retries", [0, 11, -1])
def test_invalid_retry_count_raises(max_retries):
    provider = MockProvider(["{}"])

    with pytest.raises(ValueError):
        VLMInterface(provider, max_retries=max_retries)


def test_missing_env_var_raises_before_provider_call(monkeypatch):
    monkeypatch.delenv("MOCK_VLM_API_KEY", raising=False)

    with pytest.raises(VLMConfigError):
        MockProvider(["{}"])


def test_mock_provider_makes_no_http_requests(valid_netlist_json):
    provider = MockProvider([valid_netlist_json])
    interface = VLMInterface(provider)

    interface.predict("circuit.png")

    assert provider.call_count == 1


def test_attempts_are_logged(valid_netlist_json):
    provider = MockProvider([valid_netlist_json])
    log_stream = StringIO()
    interface = VLMInterface(provider, log_stream=log_stream)

    interface.predict("circuit.png")

    log = json.loads(log_stream.getvalue())

    assert log["attempt"] == 1
    assert log["outcome"] == "validation succeeded"
    assert valid_netlist_json[:500] == log["raw_response"]


def test_max_retries_is_total_attempt_count():
    provider = MockProvider(["bad response"])
    interface = VLMInterface(provider, max_retries=2)

    with pytest.raises(VLMExhaustedError):
        interface.predict("circuit.png")

    assert provider.call_count == 2