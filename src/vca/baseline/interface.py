"""Validated VLM prediction interface with retries."""

import json
import sys
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from vca.baseline.errors import VLMExhaustedError
from vca.baseline.provider import VLMProvider
from vca.schemas.netlist import Netlist


class VLMInterface:
    """Call a VLM provider and validate its netlist response."""

    def __init__(
        self,
        provider: VLMProvider,
        max_retries: int = 3,
        log_stream: TextIO | None = None,
    ) -> None:
        if not 1 <= max_retries <= 10:
            raise ValueError("max_retries must be between 1 and 10.")

        self.provider = provider
        self.max_retries = max_retries
        self.log_stream = log_stream if log_stream is not None else sys.stderr

    def predict(self, image_path: str | Path) -> Netlist:
        """Predict a netlist, retrying when the response is invalid."""
        correction_context: str | None = None
        final_error: Exception | str = "No attempt was made"

        for attempt in range(1, self.max_retries + 1):
            raw_response = ""

            try:
                raw_response = self.provider.call(
                    image_path,
                    correction_context=correction_context,
                )

                netlist = Netlist.model_validate_json(raw_response)

                self._log(
                    attempt,
                    raw_response,
                    "validation succeeded",
                )
                return netlist

            except (ValidationError, ValueError) as error:
                final_error = error
                correction_context = (
                    "Your previous response failed netlist validation. "
                    "Correct these errors and return valid Netlist JSON only:\n"
                    f"{error}"
                )

                self._log(
                    attempt,
                    raw_response,
                    f"validation failed: {error}",
                )

            except Exception as error:
                final_error = error
                correction_context = (
                    "Your previous request failed. Please return valid "
                    f"Netlist JSON. Error: {error}"
                )

                self._log(
                    attempt,
                    raw_response,
                    f"provider call failed: {error}",
                )

        raise VLMExhaustedError(
            image_path=image_path,
            retries=self.max_retries,
            final_error=final_error,
        )

    def _log(
        self,
        attempt: int,
        raw_response: str,
        outcome: str,
    ) -> None:
        """Log attempt metadata without exposing API credentials."""
        truncated_response = raw_response[:500]

        if len(raw_response) > 500:
            truncated_response += "... [truncated]"

        log_entry = {
            "attempt": attempt,
            "raw_response": truncated_response,
            "outcome": outcome,
        }

        print(json.dumps(log_entry), file=self.log_stream)