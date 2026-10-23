# Layers 01-05 streaming backend

This package implements the runtime boundary from patient intake through validated patient-facing sections. Layer 00 remains independently owned and connects through `KnowledgeProvider` plus the request's pinned `knowledge_snapshot`.

## Run locally

```powershell
$projectPython = if (Test-Path .venv-win\Scripts\python.exe) { ".\.venv-win\Scripts\python.exe" } elseif (Test-Path .venv\Scripts\python.exe) { ".\.venv\Scripts\python.exe" } else { ".\.venv\bin\python.exe" }
& $projectPython -m pip install -r backend\requirements.txt
& $projectPython -m uvicorn backend.app:app --reload
```

Create a demo run:

```powershell
$body = @{
  patient_text = "I have been more short of breath on stairs this week. Explain how these reports fit together and what I should ask my doctor."
  artifacts = @(
    @{ artifact_id="lab"; filename="labs.json"; media_type="application/json"; storage_reference="sample-data/s3/patient/fictional-001/labs.json"; modality="lab_report"; modality_source="user_label" },
    @{ artifact_id="xray"; filename="chest-xray-report.md"; media_type="text/markdown"; storage_reference="sample-data/s3/patient/fictional-001/chest-xray-report.md"; modality="radiology_image"; modality_source="user_label" },
    @{ artifact_id="ecg"; filename="ecg-report.md"; media_type="text/markdown"; storage_reference="sample-data/s3/patient/fictional-001/ecg-report.md"; modality="ecg_image"; modality_source="user_label" }
  )
  requested_outcomes = @("understand_tests", "combined_explanation")
  knowledge_snapshot = @{ corpus_version="local-demo-v1" }
} | ConvertTo-Json -Depth 6

$run = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/runs -ContentType application/json -Body $body
curl.exe -N "http://127.0.0.1:8000$($run.events_url)"
```

## Frontend contract

- `POST /api/runs` accepts `multipart/form-data`: `patient_text`, JSON-array fields `requested_outcomes` and `artifact_modalities`, plus repeated `files`. It returns URLs under `/api` for the browser client.
- Supported uploads are PNG, JPEG, WebP, GIF, JSON, Markdown, and plain text. Images are sent to the assigned Nova specialist as multimodal Converse content.
- `POST /v1/runs` starts backend-owned work and returns `run_id`, `status_url`, and `events_url`.
- `GET /v1/runs/{run_id}/events` is SSE. Each durable event has an integer `id`, named `event`, and JSON `data` matching `WorkflowEvent`.
- Reconnect with `Last-Event-ID` or `?cursor=<sequence>` to replay everything after the last received event.
- `GET /v1/runs/{run_id}` returns the compact current state and validated answer sections.
- `POST /v1/runs/{run_id}/cancel` stops scheduling new work.

Local Vite origins are enabled through `FRONTEND_ORIGINS`. The frontend only needs the API base URL; it should POST a run, open the returned `events_url` with `EventSource`, and recover with the latest event ID after a disconnect.

## Run with the frontend

```powershell
# terminal 1, repository root
& .\.venv-win\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

# terminal 2
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to FastAPI on port 8000.

The runtime validates state, runs the lab/radiology/ECG diagnostic workers concurrently on Nova Pro, retrieves from the managed Layer 00 Bedrock Knowledge Base, applies the Doctor red-flag gate, and streams only validated template sections. Model responses are accepted only after JSON schema validation. Set `WORKFLOW_RETRIEVAL_MODE=local` and omit `WORKFLOW_MODEL_MODE=bedrock` for offline tests. Sonnet-backed intake, routing, Doctor review, guidance review, and patient-language generation remain the next integration slice.

