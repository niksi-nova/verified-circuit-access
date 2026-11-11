"""Tests for the Claude provider, using a fake client (no network)."""

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from vca.baseline.anthropic_provider import NETLIST_SCHEMA, AnthropicProvider
from vca.baseline.errors import VLMConfigError
from vca.baseline.interface import VLMInterface

PREDICTION = {
    "components": [
        {
            "id": "R1",
            "canonical_category": "resistor",
            "terminals": [{"name": "Pos"}, {"name": "Neg"}],
            "bbox": {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.25},
        }
    ],
    "nets": [
        {"name": "VDD", "endpoints": [{"component_id": "R1", "terminal_name": "Pos"}]},
        {"name": "GND", "endpoints": [{"component_id": "R1", "terminal_name": "Neg"}]},
    ],
}


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


class FakeMessages:
    def __init__(self, text: str, stop_reason: str = "end_turn"):
        self.text = text
        self.stop_reason = stop_reason
        self.requests: list[dict] = []

    def stream(self, **kwargs):
        self.requests.append(kwargs)
        message = SimpleNamespace(
            model=kwargs["model"],
            stop_reason=self.stop_reason,
            stop_details=None,
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
            content=[SimpleNamespace(type="text", text=self.text)],
            _request_id="req_test",
        )
        return FakeStream(message)


def make_provider(monkeypatch, text, stop_reason="end_turn"):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    messages = FakeMessages(text, stop_reason)
    provider = AnthropicProvider(client=SimpleNamespace(messages=messages))
    return provider, messages


@pytest.fixture
def image_path(tmp_path: Path) -> Path:
    path = tmp_path / "001.png"
    Image.new("RGB", (400, 200), "white").save(path)
    return path


def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(VLMConfigError):
        AnthropicProvider(client=SimpleNamespace(messages=None))


def test_request_carries_image_schema_and_effort(monkeypatch, image_path):
    provider, messages = make_provider(monkeypatch, json.dumps(PREDICTION))

    provider.call(image_path, correction_context="fix it")

    request = messages.requests[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["output_config"]["effort"] == "high"
    assert request["output_config"]["format"]["schema"] is NETLIST_SCHEMA
    content = request["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/png"
    assert content[-1]["text"] == "fix it"


def test_normalised_boxes_become_pixels(monkeypatch, image_path):
    provider, _ = make_provider(monkeypatch, json.dumps(PREDICTION))

    netlist = VLMInterface(provider).predict(image_path)

    bbox = netlist.components[0].bbox
    assert (bbox.x, bbox.y, bbox.width, bbox.height) == (40, 40, 200, 50)
    assert provider.call_log[0]["output_tokens"] == 200


def test_refusal_is_retried_then_exhausts(monkeypatch, image_path):
    from vca.baseline.errors import VLMExhaustedError

    provider, messages = make_provider(monkeypatch, "", stop_reason="refusal")

    with pytest.raises(VLMExhaustedError):
        VLMInterface(provider, max_retries=2, log_stream=io.StringIO()).predict(
            image_path
        )

    assert len(messages.requests) == 2


def test_schema_is_strict_everywhere():
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(NETLIST_SCHEMA)
