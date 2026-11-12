"""Test-only: JobManager queueing, saved-run reuse, and error paths.

Uses a mock engine (no real pipeline/weights) so these run fast and
without the ``train``/``api`` extras' heavy dependencies loaded.
"""

from __future__ import annotations

import threading
import time

from vca.api.engine import NoComponentsFoundError
from vca.api.jobs import JobManager
from vca.api.storage import RunStore


class FakeEngine:
    def __init__(self, behavior="ok"):
        self.behavior = behavior
        self.calls = 0

    def analyze(self, image, sha256, extension, on_stage=None):
        self.calls += 1
        if on_stage:
            on_stage("detect_components")
        if self.behavior == "no_components":
            raise NoComponentsFoundError("No components were found in this image.")
        if self.behavior == "crash":
            raise RuntimeError("boom")
        return {
            "id": sha256[:12],
            "image": f"input.{extension}",
            "components": [],
            "nets": [],
            "flags": {"circuit": {}, "flagged_count": 0},
            "explanation": {
                "layer1_overview": [{"text": "ok", "components": [], "nets": []}],
                "layer2_blocks": [{"text": "ok", "components": [], "nets": []}],
                "layer3_details": [{"text": "ok", "components": [], "nets": []}],
            },
            "flagged_count": 0,
            "evaluation": None,
            "verifier_source": "model",
            "warnings": [],
        }


def _wait_until(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _write_png(store: RunStore, sha256: str) -> None:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buf, format="PNG")
    store.save_input(sha256, "png", buf.getvalue())


def test_submit_runs_a_fresh_job_to_completion(tmp_path):
    store = RunStore(tmp_path)
    engine = FakeEngine()
    manager = JobManager(engine, store)
    _write_png(store, "sha-fresh")

    job = manager.submit("sha-fresh", "png", use_saved=True)
    assert job.from_saved is False
    assert _wait_until(lambda: manager.get(job.id).status == "done")
    assert engine.calls == 1
    assert store.exists("sha-fresh")


def test_submit_reuses_saved_result_without_calling_engine(tmp_path):
    store = RunStore(tmp_path)
    engine = FakeEngine()
    manager = JobManager(engine, store)
    store.save_result(
        "sha-cached", {"id": "sha-cached"}, {}, {"timestamp": "2026-01-01T00:00:00"}
    )

    job = manager.submit("sha-cached", "png", use_saved=True)
    assert job.status == "done"
    assert job.from_saved is True
    assert job.saved_timestamp == "2026-01-01T00:00:00"
    assert engine.calls == 0


def test_use_saved_false_forces_a_fresh_run_even_if_cached(tmp_path):
    store = RunStore(tmp_path)
    engine = FakeEngine()
    manager = JobManager(engine, store)
    store.save_result("sha-cached", {"id": "sha-cached"}, {}, {"timestamp": "old"})
    _write_png(store, "sha-cached")

    job = manager.submit("sha-cached", "png", use_saved=False)
    assert job.from_saved is False
    assert _wait_until(lambda: manager.get(job.id).status == "done")
    assert engine.calls == 1


def test_no_components_found_surfaces_as_a_plain_error(tmp_path):
    store = RunStore(tmp_path)
    engine = FakeEngine(behavior="no_components")
    manager = JobManager(engine, store)
    _write_png(store, "sha-empty")

    job = manager.submit("sha-empty", "png", use_saved=True)
    assert _wait_until(lambda: manager.get(job.id).status == "error")
    assert "No components" in manager.get(job.id).error
    assert store.exists("sha-empty") is False


def test_unexpected_exception_gives_a_generic_message_not_a_stack_trace(tmp_path):
    store = RunStore(tmp_path)
    engine = FakeEngine(behavior="crash")
    manager = JobManager(engine, store)
    _write_png(store, "sha-crash")

    job = manager.submit("sha-crash", "png", use_saved=True)
    assert _wait_until(lambda: manager.get(job.id).status == "error")
    error = manager.get(job.id).error
    assert "boom" not in error
    assert error == "Something went wrong analysing this image."


def test_jobs_run_one_at_a_time(tmp_path):
    """Two submissions for different images: the second must not start
    until the first finishes (single-worker queue)."""
    store = RunStore(tmp_path)

    order = []

    class SlowEngine:
        def analyze(self, image, sha256, extension, on_stage=None):
            order.append(("start", sha256))
            time.sleep(0.1)
            order.append(("end", sha256))
            return {
                "id": sha256,
                "components": [],
                "nets": [],
                "flags": {"circuit": {}, "flagged_count": 0},
                "explanation": {
                    "layer1_overview": [{"text": "x", "components": [], "nets": []}],
                    "layer2_blocks": [{"text": "x", "components": [], "nets": []}],
                    "layer3_details": [{"text": "x", "components": [], "nets": []}],
                },
                "flagged_count": 0,
                "evaluation": None,
            }

    engine = SlowEngine()
    manager = JobManager(engine, store)
    _write_png(store, "sha-a")
    _write_png(store, "sha-b")

    manager.submit("sha-a", "png", use_saved=True)
    job_b = manager.submit("sha-b", "png", use_saved=True)
    assert _wait_until(lambda: manager.get(job_b.id).status == "done", timeout=5)

    assert order == [
        ("start", "sha-a"),
        ("end", "sha-a"),
        ("start", "sha-b"),
        ("end", "sha-b"),
    ]


def test_cancel_before_processing_marks_job_cancelled(tmp_path):
    store = RunStore(tmp_path)

    class BlockingEngine:
        def __init__(self):
            self.gate = threading.Event()

        def analyze(self, image, sha256, extension, on_stage=None):
            self.gate.wait(timeout=2)
            return {
                "id": sha256,
                "components": [],
                "nets": [],
                "flags": {},
                "explanation": {},
            }

    engine = BlockingEngine()
    manager = JobManager(engine, store)
    _write_png(store, "sha-block")
    _write_png(store, "sha-cancel")

    # Occupy the single worker with a job that won't finish until we
    # release the gate, so the second job stays queued and cancellable.
    manager.submit("sha-block", "png", use_saved=True)
    job = manager.submit("sha-cancel", "png", use_saved=True)
    ok = manager.cancel(job.id)
    engine.gate.set()

    assert ok is True
    assert _wait_until(lambda: manager.get(job.id).status == "cancelled")


def test_cancel_unknown_job_returns_false(tmp_path):
    store = RunStore(tmp_path)
    manager = JobManager(FakeEngine(), store)
    assert manager.cancel("does-not-exist") is False
