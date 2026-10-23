"""HTTP API. Run from the repo root:  .venv/bin/python -m uvicorn backend.app:app --port 8000

  GET  /api/health                 mode, data source, and guardrail status
  GET  /api/presets                the visits of the demo patient
  POST /api/runs {"preset_id"}     start a run, returns {"run_id"}
  GET  /api/runs/{id}/events       Server-Sent Events; supports reconnecting via Last-Event-ID
BACKEND_MODE=mock skips Bedrock entirely (offline). DATA_SOURCE=s3 reads the patient from S3.
The demo patient is hardcoded (DEMO_PATIENT, default VP01) and bundled with the repo.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .cases import Case, build_cases, preset_summaries
from .events import RunLog
from .guardrail import Guard
from .pipeline import run_pipeline
from .store import DEMO_PATIENT, FileStore, LocalStore, Patient, get_store, load_patient

MODE = os.environ.get("BACKEND_MODE", "bedrock")  # "bedrock" or "mock"


def _load() -> tuple[FileStore, Patient, str | None]:
    """Load the demo patient. If S3 is requested but fails, fall back to the bundled copy."""
    store = get_store()
    try:
        return store, load_patient(store, DEMO_PATIENT), None
    except Exception as exc:  # noqa: BLE001 - the demo must not depend on the network
        local = LocalStore()
        return local, load_patient(local, DEMO_PATIENT), f"{store.name} unavailable ({type(exc).__name__}); using the bundled copy"


STORE, PATIENT, DATA_NOTE = _load()
CASES: dict[str, Case] = build_cases(STORE, PATIENT)
guard = Guard(enabled=MODE == "bedrock")
RUNS: dict[str, RunLog] = {}
_TASKS: set[asyncio.Task] = set()  # keeps background tasks alive until they finish


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Create or find the guardrail in the background so startup is not blocked.
    task = asyncio.create_task(asyncio.to_thread(guard.ensure))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    yield


app = FastAPI(title="Care team backend (prototype)", lifespan=lifespan)


class RunRequest(BaseModel):
    preset_id: str


@app.get("/api/health")
async def health() -> dict:
    return {
        "mode": MODE,
        "patient": PATIENT.patient_id,
        "data_source": STORE.name,
        "data_note": DATA_NOTE,
        "guardrail": {"ready": guard.ready, "id": guard.guardrail_id, "error": guard.error},
    }


@app.get("/api/presets")
async def presets() -> list[dict]:
    return preset_summaries(CASES)


@app.post("/api/runs")
async def start_run(body: RunRequest) -> dict:
    case = CASES.get(body.preset_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"unknown preset {body.preset_id!r}")
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    log = RunLog(run_id, case.id)
    RUNS[run_id] = log
    task = asyncio.create_task(run_pipeline(log, case, MODE, guard))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, request: Request, after: int = 0) -> StreamingResponse:
    log = RUNS.get(run_id)
    if log is None:
        raise HTTPException(status_code=404, detail="unknown run")
    # A reconnecting browser sends Last-Event-ID (the last sequence it saw); resume after it.
    last_id = request.headers.get("last-event-id")
    index = int(last_id) if last_id and last_id.isdigit() else after

    async def stream() -> AsyncIterator[str]:
        nonlocal index
        while True:
            batch, done = await log.wait_for_more(index, timeout=15)
            for event in batch:
                yield f"id: {event['sequence']}\ndata: {json.dumps(event)}\n\n"
            index += len(batch)
            if done and index >= len(log.events):
                return
            if not batch:
                yield ": keepalive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
