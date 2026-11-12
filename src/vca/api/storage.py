"""Upload validation and the on-disk layout of a saved run.

Every run lives at ``demo/uploads/<sha256>/`` — never the client's
filename, which is discarded after format sniffing. Nothing here talks to
the network.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_FORMATS = {"PNG": "png", "JPEG": "jpg"}
MIN_SIDE = 64
MAX_SIDE = 8000

# Checked on the raw bytes before any PIL call. Ultralytics (loaded by the
# engine for YOLO) monkey-patches PIL.Image.open to attempt installing a
# HEIF plugin via pip whenever a file can't be identified — a network
# call we must never make, and a confusing crash for a plain bad upload.
# Rejecting unrecognised bytes by magic number up front means
# Image.open is only ever called on content real PNG/JPEG headers.
_MAGIC_BYTES = {
    b"\x89PNG\r\n\x1a\n": "PNG",
    b"\xff\xd8\xff": "JPEG",
}


class UploadError(ValueError):
    """A plain-language, user-facing validation failure."""


@dataclass
class ValidatedUpload:
    sha256: str
    extension: str
    width: int
    height: int


def _sniff_format(data: bytes) -> str | None:
    for magic, fmt in _MAGIC_BYTES.items():
        if data.startswith(magic):
            return fmt
    return None


def validate_upload(data: bytes) -> ValidatedUpload:
    if len(data) == 0:
        raise UploadError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError(
            f"The image is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    fmt = _sniff_format(data)
    if fmt not in ALLOWED_FORMATS:
        raise UploadError("Only PNG and JPEG images are accepted.")

    try:
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
            if width < MIN_SIDE or height < MIN_SIDE:
                raise UploadError(
                    f"The image is too small (minimum {MIN_SIDE}x{MIN_SIDE}px)."
                )
            if width > MAX_SIDE or height > MAX_SIDE:
                raise UploadError(
                    f"The image is too large (maximum {MAX_SIDE}x{MAX_SIDE}px)."
                )
            img.verify()
        with Image.open(io.BytesIO(data)) as img:
            img.load()
    except UploadError:
        raise
    except (
        OSError,
        ModuleNotFoundError,
        Image.DecompressionBombError,
        SyntaxError,
        ValueError,
    ):
        raise UploadError("This doesn't look like a valid image file.") from None

    return ValidatedUpload(
        sha256=hashlib.sha256(data).hexdigest(),
        extension=ALLOWED_FORMATS[fmt],
        width=width,
        height=height,
    )


class RunStore:
    """One directory per sha256 under ``uploads_dir``."""

    def __init__(self, uploads_dir: Path):
        self.root = Path(uploads_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def dir_for(self, sha256: str) -> Path:
        return self.root / sha256

    def exists(self, sha256: str) -> bool:
        return (
            self.load_meta(sha256) is not None and self.load_result(sha256) is not None
        )

    def input_path(self, sha256: str, extension: str) -> Path:
        return self.dir_for(sha256) / f"input.{extension}"

    def save_input(self, sha256: str, extension: str, data: bytes) -> Path:
        run_dir = self.dir_for(sha256)
        run_dir.mkdir(parents=True, exist_ok=True)
        path = self.input_path(sha256, extension)
        if not path.exists():
            path.write_bytes(data)
        return path

    def save_result(
        self,
        sha256: str,
        record: dict,
        text_layers: dict[str, str],
        meta: dict,
    ) -> None:
        run_dir = self.dir_for(sha256)
        run_dir.mkdir(parents=True, exist_ok=True)

        text_dir = run_dir / "text"
        text_dir.mkdir(exist_ok=True)
        for name, text in text_layers.items():
            (text_dir / f"{name}.txt").write_text(text + "\n", encoding="utf-8")
        for name, value in (("result", record), ("meta", meta)):
            temp = run_dir / f"{name}.tmp"
            temp.write_text(json.dumps(value, indent=1), encoding="utf-8")
            temp.replace(run_dir / f"{name}.json")

    def load_result(self, sha256: str) -> dict | None:
        path = self.dir_for(sha256) / "result.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def load_meta(self, sha256: str) -> dict | None:
        path = self.dir_for(sha256) / "meta.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def list_runs(self) -> list[dict]:
        runs = []
        for run_dir in sorted(self.root.iterdir()):
            meta = self.load_meta(run_dir.name)
            if meta:
                runs.append(meta)
        runs.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
        return runs

    def delete(self, sha256: str) -> bool:
        run_dir = self.dir_for(sha256)
        if not run_dir.exists():
            return False
        shutil.rmtree(run_dir)
        return True


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
