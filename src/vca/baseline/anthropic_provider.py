"""Claude vision provider: circuit image in, Netlist JSON out.

One Messages API call per attempt, with the image as base64 and structured
outputs constraining the reply to the Netlist shape. Component boxes come
back normalised to [0, 1] and are converted to pixels here so the returned
JSON validates directly as ``vca.schemas.netlist.Netlist``.

Sampling parameters are not available on current Claude models, so runs are
not bit-for-bit repeatable; every raw prediction is saved by the evaluator.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import anthropic
from PIL import Image

from vca.baseline.provider import VLMProvider
from vca.schemas.ports import ALL_TERMINAL_NAMES, CATEGORY_TERMINALS

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"

MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

_STRING = {"type": "string"}
_NUMBER = {"type": "number"}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


NETLIST_SCHEMA: dict[str, Any] = _object(
    {
        "components": {
            "type": "array",
            "items": _object(
                {
                    "id": _STRING,
                    "canonical_category": {
                        "type": "string",
                        "enum": sorted(CATEGORY_TERMINALS),
                    },
                    "terminals": {
                        "type": "array",
                        "items": _object(
                            {
                                "name": {
                                    "type": "string",
                                    "enum": list(ALL_TERMINAL_NAMES),
                                }
                            }
                        ),
                    },
                    "bbox": _object(
                        {
                            "x": _NUMBER,
                            "y": _NUMBER,
                            "width": _NUMBER,
                            "height": _NUMBER,
                        }
                    ),
                }
            ),
        },
        "nets": {
            "type": "array",
            "items": _object(
                {
                    "name": _STRING,
                    "endpoints": {
                        "type": "array",
                        "items": _object(
                            {"component_id": _STRING, "terminal_name": _STRING}
                        ),
                    },
                }
            ),
        },
    }
)


def _terminal_table() -> str:
    return "\n".join(
        f"- {category}: {', '.join(terminals)}"
        for category, terminals in CATEGORY_TERMINALS.items()
    )


SYSTEM_PROMPT = f"""\
You convert an analog circuit schematic image into a netlist.

Components
- Emit one component for every drawn device, with a unique id (M1, R1, ...).
- Use exactly one of these categories, with exactly its terminal names:
{_terminal_table()}
- MOS transistors: include Body only when the symbol draws a separate body \
connection; otherwise list Drain, Gate and Source only.
- Diode: In is the anode, Out is the cathode.
- Current source: current flows from In to Out (the arrow points toward Out).
- Amplifiers: InP is the non-inverting (+) input, InN the inverting (-) input.
- Supply rails (VDD, VCC, VSS), ground symbols, and labelled pins or ports are \
NOT components. They are nets; name the net after its label (e.g. "VDD", \
"GND", "Vin", "Vout").

Nets
- A net is one electrically connected set of wires. Wires joined by a dot or \
a T-junction are the same net. Wires that cross without a dot are not \
connected.
- Every terminal of every component appears in exactly one net. A terminal \
with nothing attached gets a net of its own.
- Net names are free text; use the drawn label when one exists.

Location
- bbox is the component's bounding box as fractions of the image width and \
height: x and y are the top-left corner, all values in [0, 1].
"""


class AnthropicProvider(VLMProvider):
    """Netlist extraction with a Claude vision model."""

    required_env_var = "ANTHROPIC_API_KEY"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        effort: str = DEFAULT_EFFORT,
        max_tokens: int = 32000,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        super().__init__()
        self.model_identifier = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.client = client or anthropic.Anthropic()
        # One entry per API call: tokens, served model, stop reason.
        self.call_log: list[dict[str, Any]] = []

    def call(
        self,
        image_path: str | Path,
        correction_context: str | None = None,
    ) -> str:
        image_path = Path(image_path)
        media_type = MEDIA_TYPES.get(image_path.suffix.lower())
        if media_type is None:
            raise ValueError(f"Unsupported image type: {image_path.suffix}")

        image_data = base64.standard_b64encode(image_path.read_bytes()).decode()
        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data,
                },
            },
            {"type": "text", "text": "Extract the netlist of this circuit."},
        ]
        if correction_context:
            content.append({"type": "text", "text": correction_context})

        with self.client.messages.stream(
            model=self.model_identifier,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": NETLIST_SCHEMA},
            },
        ) as stream:
            message = stream.get_final_message()

        self.call_log.append(
            {
                "image": image_path.name,
                "served_model": message.model,
                "stop_reason": message.stop_reason,
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
                "request_id": message._request_id,
            }
        )

        if message.stop_reason == "refusal":
            raise RuntimeError(f"Model refused: {message.stop_details}")
        if message.stop_reason == "max_tokens":
            raise RuntimeError("Response hit max_tokens before finishing.")

        text = next(
            (block.text for block in message.content if block.type == "text"), ""
        )
        return self._to_pixel_bboxes(text, image_path)

    @staticmethod
    def _to_pixel_bboxes(text: str, image_path: Path) -> str:
        """Scale normalised boxes to pixels; leave invalid JSON untouched."""
        try:
            data = json.loads(text)
            components = data["components"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return text

        with Image.open(image_path) as image:
            width, height = image.size

        for component in components:
            box = component.get("bbox") if isinstance(component, dict) else None
            if not isinstance(box, dict):
                continue
            try:
                component["bbox"] = {
                    "x": float(box["x"]) * width,
                    "y": float(box["y"]) * height,
                    "width": float(box["width"]) * width,
                    "height": float(box["height"]) * height,
                }
            except (KeyError, TypeError, ValueError):
                component["bbox"] = None

        return json.dumps(data)
