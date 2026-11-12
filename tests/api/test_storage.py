"""Test-only: upload validation, hashing and the run store's cache logic."""

from __future__ import annotations

import hashlib
import io

import pytest
from PIL import Image

from vca.api.storage import (
    MAX_UPLOAD_BYTES,
    MIN_SIDE,
    RunStore,
    UploadError,
    validate_upload,
)


def _png_bytes(width=200, height=150) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(width=200, height=150) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="JPEG")
    return buf.getvalue()


def test_valid_png_is_accepted_and_hashed_correctly():
    data = _png_bytes()
    result = validate_upload(data)
    assert result.extension == "png"
    assert result.sha256 == hashlib.sha256(data).hexdigest()
    assert result.width == 200
    assert result.height == 150


def test_valid_jpeg_is_accepted():
    result = validate_upload(_jpeg_bytes())
    assert result.extension == "jpg"


def test_truncated_jpeg_pixels_are_rejected():
    with pytest.raises(UploadError, match="valid image"):
        validate_upload(_jpeg_bytes()[:-30])


def test_empty_file_is_rejected():
    with pytest.raises(UploadError, match="empty"):
        validate_upload(b"")


def test_oversized_file_is_rejected():
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (MAX_UPLOAD_BYTES + 1)
    with pytest.raises(UploadError, match="larger"):
        validate_upload(oversized)


def test_non_image_bytes_are_rejected_without_calling_pil():
    with pytest.raises(UploadError, match="PNG and JPEG"):
        validate_upload(b"not an image, just plain text" * 10)


def test_too_small_image_is_rejected():
    with pytest.raises(UploadError, match="too small"):
        validate_upload(_png_bytes(width=MIN_SIDE - 1, height=MIN_SIDE - 1))


def test_truncated_png_header_is_rejected_as_invalid():
    # Starts with the real PNG magic bytes but has no valid image data.
    with pytest.raises(UploadError, match="valid image"):
        validate_upload(b"\x89PNG\r\n\x1a\n" + b"garbage")


def test_client_filename_never_used(tmp_path):
    """The run store keys everything by sha256, never a filename."""
    store = RunStore(tmp_path)
    data = _png_bytes()
    result = validate_upload(data)
    path = store.save_input(result.sha256, result.extension, data)
    assert path.name == f"input.{result.extension}"
    assert result.sha256 in str(path)


class TestRunStoreCache:
    def test_exists_false_before_any_result_saved(self, tmp_path):
        store = RunStore(tmp_path)
        assert store.exists("abc123") is False

    def test_save_and_load_result_round_trips(self, tmp_path):
        store = RunStore(tmp_path)
        record = {"id": "abc123", "components": []}
        store.save_result("abc123", record, {"layer1": "text"}, {"sha256": "abc123"})
        assert store.exists("abc123") is True
        assert store.load_result("abc123") == record
        assert (tmp_path / "abc123" / "text" / "layer1.txt").exists()

    def test_list_runs_sorted_newest_first(self, tmp_path):
        store = RunStore(tmp_path)
        store.save_result(
            "old", {"id": "old"}, {}, {"timestamp": "2026-01-01T00:00:00"}
        )
        store.save_result(
            "new", {"id": "new"}, {}, {"timestamp": "2026-06-01T00:00:00"}
        )
        runs = store.list_runs()
        assert [r["timestamp"] for r in runs] == [
            "2026-06-01T00:00:00",
            "2026-01-01T00:00:00",
        ]

    def test_delete_removes_run_and_reports_success(self, tmp_path):
        store = RunStore(tmp_path)
        store.save_result("abc123", {"id": "abc123"}, {}, {})
        assert store.delete("abc123") is True
        assert store.exists("abc123") is False

    def test_delete_unknown_run_returns_false(self, tmp_path):
        store = RunStore(tmp_path)
        assert store.delete("does-not-exist") is False

    def test_save_input_does_not_overwrite_existing(self, tmp_path):
        store = RunStore(tmp_path)
        store.save_input("abc", "png", b"first")
        store.save_input("abc", "png", b"second")
        assert store.input_path("abc", "png").read_bytes() == b"first"
