"""A single-worker job queue: one analysis runs at a time, others wait.

Jobs are ephemeral and in-memory (lost on restart); saved *runs* on disk
(``RunStore``) are the durable record. A job that reuses a saved run
finishes immediately with ``from_saved=True``.
"""

from __future__ import annotations

import queue
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field, replace

from PIL import Image

from vca.api.engine import Engine, NoComponentsFoundError
from vca.api.storage import RunStore, now_iso
from vca.explain.build import text_layers


class JobCancelled(RuntimeError):
    pass


@dataclass
class Job:
    id: str
    sha256: str
    extension: str
    status: str = "queued"  # queued | running | done | error | cancelled
    stage: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    from_saved: bool = False
    saved_timestamp: str | None = None
    cancel_requested: bool = False
    result: dict | None = None

    def elapsed_seconds(self) -> float:
        start = self.started_at or self.created_at
        end = self.finished_at or time.time()
        return round(end - start, 1)


class JobManager:
    def __init__(self, engine: Engine, store: RunStore):
        self.engine = engine
        self.store = store
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._worker = threading.Thread(target=self._run_loop, daemon=True)
        self._worker.start()

    def submit(
        self, sha256: str, extension: str, use_saved: bool, data: bytes | None = None
    ) -> Job:
        with self._lock:
            if data is not None:
                self.store.save_input(sha256, extension, data)
            if use_saved and self.store.exists(sha256):
                meta = self.store.load_meta(sha256) or {}
                job = Job(
                    id=uuid.uuid4().hex,
                    sha256=sha256,
                    extension=extension,
                    status="done",
                    from_saved=True,
                    saved_timestamp=meta.get("timestamp"),
                    finished_at=time.time(),
                    warnings=meta.get("warnings", []),
                    result=self.store.load_result(sha256),
                )
                self._jobs[job.id] = job
                return job

            job = Job(id=uuid.uuid4().hex, sha256=sha256, extension=extension)
            self._jobs[job.id] = job
        self._queue.put(job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return replace(job) if job else None

    def delete_run(self, sha256: str) -> bool:
        with self._lock:
            if any(
                job.sha256 == sha256 and job.status in {"queued", "running"}
                for job in self._jobs.values()
            ):
                raise ValueError("Wait for the analysis to finish before deleting it.")
            return self.store.delete(sha256)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status in ("done", "error", "cancelled"):
                return False
            job.cancel_requested = True
            return True

    def _run_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            self._process(job_id)

    def _process(self, job_id: str) -> None:
        job = self._jobs[job_id]
        with self._lock:
            if job.cancel_requested:
                job.status = "cancelled"
                job.finished_at = time.time()
                return
            job.status = "running"
            job.started_at = time.time()

        def on_stage(stage: str) -> None:
            with self._lock:
                if job.cancel_requested:
                    raise JobCancelled()
                job.stage = stage

        try:
            on_stage("read_image")
            path = self.store.input_path(job.sha256, job.extension)
            with Image.open(path) as raw:
                image = raw.convert("RGB")
            record = self.engine.analyze(
                image, job.sha256, job.extension, on_stage=on_stage
            )
            duration = time.time() - (job.started_at or time.time())
            text = text_layers(record)
            meta = {
                "sha256": job.sha256,
                "timestamp": now_iso(),
                "duration_seconds": round(duration, 2),
                "verifier_source": record.get("verifier_source"),
                "warnings": record.get("warnings", []),
                "extension": job.extension,
                "braille": bool(record.get("braille")),
                "tactile": bool(record.get("tactile")),
            }
            with self._lock:
                if job.cancel_requested:
                    raise JobCancelled()
                self.store.save_result(job.sha256, record, text, meta)
                job.result = record
                job.saved_timestamp = meta["timestamp"]
                job.status = "done"
                job.finished_at = time.time()
                job.warnings = record.get("warnings", [])
        except JobCancelled:
            with self._lock:
                job.status = "cancelled"
                job.finished_at = time.time()
        except NoComponentsFoundError as e:
            with self._lock:
                job.status = "error"
                job.error = str(e)
                job.finished_at = time.time()
        except Exception:
            traceback.print_exc()
            with self._lock:
                job.status = "error"
                job.error = "Something went wrong analysing this image."
                job.finished_at = time.time()
