"""HTTP API. Run from the repo root:  .venv/bin/python -m uvicorn backend.app:app --port 8000

  GET  /api/health                 mode and guardrail status
  GET  /api/presets                the synthetic patients
  POST /api/runs {"preset_id"}     start a run, returns {"run_id"}
  GET  /api/runs/{id}/events       Server-Sent Events; supports reconnecting via Last-Event-ID
BACKEND_MODE=mock skips Bedrock entirely (offline demo).
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

from .events import RunLog
from .fixtures import PRESETS, preset_summaries
from .guardrail import Guard
from .pipeline import run_pipeline

MODE = os.environ.get("BACKEND_MODE", "bedrock")  # "bedrock" or "mock"
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
    return {"mode": MODE, "guardrail": {"ready": guard.ready, "id": guard.guardrail_id, "error": guard.error}}


@app.get("/api/presets")
async def presets() -> list[dict]:
    return preset_summaries()


@app.post("/api/runs")
async def start_run(body: RunRequest) -> dict:
    preset = PRESETS.get(body.preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"unknown preset {body.preset_id!r}")
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    log = RunLog(run_id, preset["id"])
    RUNS[run_id] = log
    task = asyncio.create_task(run_pipeline(log, preset, MODE, guard))
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
