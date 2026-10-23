from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .knowledge import build_knowledge_provider
from .models import BedrockModelGateway
from .schemas import RunCreated, RunRequest, RunView, WorkflowEvent
from .store import Journal
from .workflow import TERMINAL, WorkflowEngine


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("WORKFLOW_DATA_DIR", ROOT / ".runtime"))
journal = Journal(DATA_DIR / "workflow.sqlite3")
knowledge = build_knowledge_provider(ROOT)
models = BedrockModelGateway() if os.getenv("WORKFLOW_MODEL_MODE", "").lower() == "bedrock" else None
engine = WorkflowEngine(journal, knowledge, ROOT, models=models)
tasks: dict[str, asyncio.Task] = {}
UPLOAD_ROOT = (ROOT / ".runtime" / "uploads").resolve()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 3_750_000
ALLOWED_UPLOAD_TYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "application/json", "text/plain", "text/markdown",
}
ALLOWED_MODALITIES = {"lab_report", "radiology_image", "ecg_image"}
IMAGE_SUFFIXES = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    for task in tasks.values():
        if not task.done():
            task.cancel()
    journal.close()


app = FastAPI(title="Healthcare Agent Workflow", version="0.1.0", lifespan=lifespan)
frontend_origins = [value.strip() for value in os.getenv(
    "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if value.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Last-Event-ID"],
)


@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok", "layers": "01-05", "streaming": "sse"}


def _start_run(payload: RunRequest, run_id: str | None = None) -> RunCreated:
    run_id = run_id or f"run-{uuid4().hex}"
    now = WorkflowEvent.now()
    journal.create_run(run_id, now, payload.model_dump(mode="json"))
    tasks[run_id] = asyncio.create_task(engine.run(run_id, payload), name=run_id)
    return RunCreated(run_id=run_id, status="queued",
                      status_url=f"/v1/runs/{run_id}", events_url=f"/v1/runs/{run_id}/events")


@app.post("/v1/runs", response_model=RunCreated, status_code=status.HTTP_202_ACCEPTED)
async def create_run(payload: RunRequest):
    return _start_run(payload)


@app.post("/api/runs", response_model=RunCreated, status_code=status.HTTP_202_ACCEPTED)
async def create_uploaded_run(
    patient_text: str = Form(default=""),
    requested_outcomes: str = Form(default='["understand_tests","combined_explanation"]'),
    artifact_modalities: str = Form(default="[]"),
    files: list[UploadFile] = File(default=[]),
):
    if len(files) > 10:
        raise HTTPException(status_code=413, detail="at most 10 files are allowed")
    try:
        outcomes = json.loads(requested_outcomes)
        modalities = json.loads(artifact_modalities)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON form metadata") from exc
    if not isinstance(outcomes, list) or not isinstance(modalities, list):
        raise HTTPException(status_code=400, detail="form metadata must be JSON arrays")
    if modalities and len(modalities) != len(files):
        raise HTTPException(status_code=400, detail="one modality is required per file")

    run_id = f"run-{uuid4().hex}"
    directory = (UPLOAD_ROOT / run_id).resolve()
    if UPLOAD_ROOT not in directory.parents:
        raise HTTPException(status_code=400, detail="invalid upload path")
    directory.mkdir(parents=True, exist_ok=False)
    artifacts = []
    for index, upload in enumerate(files):
        media_type = (upload.content_type or "application/octet-stream").lower()
        if media_type not in ALLOWED_UPLOAD_TYPES:
            raise HTTPException(status_code=415, detail=f"unsupported upload type: {media_type}")
        content = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"file too large: {upload.filename}")
        if media_type.startswith("image/") and len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail=f"image exceeds Bedrock's upload limit: {upload.filename}")
        if not content:
            raise HTTPException(status_code=400, detail=f"empty file: {upload.filename}")
        suffix = IMAGE_SUFFIXES.get(media_type, Path(upload.filename or "upload.txt").suffix.lower())
        target = directory / f"artifact-{index + 1}{suffix}"
        target.write_bytes(content)
        modality = modalities[index] if modalities else (
            "radiology_image" if media_type.startswith("image/") else "lab_report")
        if modality not in ALLOWED_MODALITIES:
            raise HTTPException(status_code=400, detail=f"unsupported artifact modality: {modality}")
        artifacts.append({
            "artifact_id": f"artifact-{index + 1}",
            "filename": Path(upload.filename or target.name).name,
            "media_type": media_type,
            "storage_reference": str(target.relative_to(ROOT)),
            "modality": modality,
            "modality_source": "user_label" if modalities else "unknown",
        })
    payload = RunRequest(patient_text=patient_text, artifacts=artifacts,
                         requested_outcomes=outcomes,
                         knowledge_snapshot={"corpus_version": "managed-layer-00"})
    created = _start_run(payload, run_id)
    return created.model_copy(update={"status_url": f"/api/runs/{run_id}",
                                      "events_url": f"/api/runs/{run_id}/events"})


@app.get("/v1/runs/{run_id}", response_model=RunView)
@app.get("/api/runs/{run_id}", response_model=RunView)
async def get_run(run_id: str):
    record = journal.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return record


@app.post("/v1/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_run(run_id: str):
    record = journal.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    if record["status"] in TERMINAL:
        return {"run_id": run_id, "status": record["status"]}
    engine.cancel(run_id)
    task = tasks.get(run_id)
    if task and not task.done():
        task.cancel()
    return {"run_id": run_id, "status": "cancelling"}


def _parse_cursor(last_event_id: str | None, query_cursor: int | None) -> int:
    raw = last_event_id if last_event_id is not None else query_cursor
    if raw is None:
        return 0
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="event cursor must be an integer") from exc
    if value < 0:
        raise HTTPException(status_code=400, detail="event cursor cannot be negative")
    return value


@app.get("/v1/runs/{run_id}/events")
@app.get("/api/runs/{run_id}/events")
async def stream_events(request: Request, run_id: str, cursor: int | None = None,
                        last_event_id: str | None = Header(default=None, alias="Last-Event-ID")):
    if journal.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    start = _parse_cursor(last_event_id, cursor)

    async def event_stream():
        sequence = start
        while True:
            events = journal.events_after(run_id, sequence)
            for event in events:
                sequence = event.sequence
                data = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
                yield f"id: {sequence}\nevent: {event.type}\ndata: {data}\n\n"
            record = journal.get_run(run_id)
            if record and record["status"] in TERMINAL and not journal.events_after(run_id, sequence):
                break
            if await request.is_disconnected():
                break
            if not events:
                yield ": heartbeat\n\n"
                await journal.wait_for_events(run_id, timeout=15.0)

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

