"""FastAPI app for the local analysis engine. 127.0.0.1 only, no external
network calls. See scripts/serve_api.py for how this is run.
"""

from __future__ import annotations

import re
import threading
import traceback
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from vca.api.engine import Engine, EngineStartupError
from vca.api.jobs import JobManager
from vca.api.storage import MAX_UPLOAD_BYTES, RunStore, UploadError, validate_upload
from vca.outputs.spice import SpiceRequest, available, simulate

ROOT = Path(__file__).resolve().parents[3]
UPLOADS_DIR = ROOT / "demo" / "uploads"


class AppState:
    engine: Engine | None = None
    engine_state: str = "starting"  # starting | ready | offline
    engine_error: str | None = None
    jobs: JobManager | None = None
    store: RunStore | None = None


state = AppState()


def _load_engine() -> None:
    try:
        state.engine = Engine(ROOT)
        state.store = RunStore(UPLOADS_DIR)
        state.jobs = JobManager(state.engine, state.store)
        state.engine_state = "ready"
    except EngineStartupError as e:
        state.engine_state = "offline"
        state.engine_error = str(e)
    except Exception:
        traceback.print_exc()
        state.engine_state = "offline"
        state.engine_error = "The analysis engine failed to start. See server logs."


@asynccontextmanager
async def lifespan(_app: FastAPI):
    threading.Thread(target=_load_engine, daemon=True).start()
    yield


app = FastAPI(title="verified-circuit-access analysis engine", lifespan=lifespan)


def _require_engine() -> tuple[Engine, JobManager, RunStore]:
    if state.engine_state != "ready" or state.engine is None:
        raise HTTPException(
            status_code=503,
            detail=state.engine_error or "The analysis engine is still starting.",
        )
    return state.engine, state.jobs, state.store  # type: ignore[return-value]


@app.get("/api/health")
def health():
    body = {
        "status": state.engine_state,
        "version": version("verified-circuit-access"),
        "models_loaded": state.engine_state == "ready",
        "engine_ready": state.engine_state == "ready",
    }
    runs = state.store.list_runs() if state.store is not None else []
    body["outputs"] = {
        "braille": any(run.get("braille") for run in runs),
        "tactile": any(run.get("tactile") for run in runs),
        "ngspice_available": available(),
    }
    if state.engine is not None:
        info = state.engine.info()
        body["runs"] = {
            "pipeline_run": info.pipeline_run,
            "verifier_run": info.verifier_run,
            "device": info.device,
            "models": state.engine.model_runs,
        }
    if state.engine_error:
        body["error"] = state.engine_error
    return body


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    use_saved: bool = Form(True),
):
    _, jobs, _ = _require_engine()
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        validated = validate_upload(data)
    except UploadError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    job = jobs.submit(
        validated.sha256, validated.extension, use_saved=use_saved, data=data
    )
    return {
        "job_id": job.id,
        "sha256": validated.sha256,
        "status": job.status,
        "from_saved": job.from_saved,
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    _, jobs, _ = _require_engine()
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id.")

    body = {
        "id": job.id,
        "sha256": job.sha256,
        "status": job.status,
        "stage": job.stage,
        "elapsed_seconds": job.elapsed_seconds(),
        "from_saved": job.from_saved,
        "warnings": job.warnings,
    }
    if job.status == "error":
        body["error"] = job.error
    if job.status == "done" and job.result is not None:
        body["result"] = _public_result(job.result, job.sha256)
        body["saved_timestamp"] = job.saved_timestamp
    return JSONResponse(body)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    _, jobs, _ = _require_engine()
    ok = jobs.cancel(job_id)
    return {"cancelled": ok}


@app.get("/api/runs")
def list_runs():
    _, _, store = _require_engine()
    return store.list_runs()


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str):
    _check_run_id(run_id)
    _, jobs, _ = _require_engine()
    try:
        ok = jobs.delete_run(run_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    if not ok:
        raise HTTPException(status_code=404, detail="Unknown run id.")
    return {"deleted": True}


EXAMPLES = {"002", "003", "014", "015", "019", "095"}
LAYERS = {"layer1", "layer2", "layer3", "all"}


def _check_run_id(run_id: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{64}", run_id):
        raise HTTPException(status_code=404, detail="Unknown run id.")


def _saved_run(run_id: str) -> tuple[RunStore, dict]:
    _check_run_id(run_id)
    _, _, store = _require_engine()
    meta = store.load_meta(run_id)
    if not meta:
        raise HTTPException(
            status_code=404, detail="This saved analysis was not found."
        )
    return store, meta


@app.get("/api/examples/{example_id}")
def example_image(example_id: str):
    path = ROOT / "data" / "image2net" / "images" / f"{example_id}.png"
    if example_id not in EXAMPLES or not path.is_file():
        raise HTTPException(status_code=404, detail="This example image was not found.")
    return FileResponse(path, media_type="image/png")


def _public_result(record: dict, run_id: str) -> dict:
    # Older saved runs may have a null evaluation and an obsolete image URL.
    result = dict(record, image_url=f"/api/runs/{run_id}/image")
    result.pop("evaluation", None)
    return result


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    store, meta = _saved_run(run_id)
    result = store.load_result(run_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail="This saved analysis was not found."
        )
    return {
        "result": _public_result(result, run_id),
        "from_saved": True,
        "saved_timestamp": meta["timestamp"],
    }


@app.get("/api/runs/{run_id}/image")
def run_image(run_id: str):
    store, meta = _saved_run(run_id)
    return FileResponse(store.input_path(run_id, meta["extension"]))


@app.get("/api/runs/{run_id}/text/{layer}")
def run_text(run_id: str, layer: str):
    store, _ = _saved_run(run_id)
    if layer not in LAYERS:
        raise HTTPException(status_code=404, detail="Unknown text layer.")
    return FileResponse(
        store.dir_for(run_id) / "text" / f"{layer}.txt",
        media_type="text/plain",
        filename=f"{run_id[:12]}.{layer}.txt",
    )


@app.post("/api/calculate")
def calculate(request: SpiceRequest):
    try:
        return simulate(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
