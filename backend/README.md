# Backend (prototype)

A small FastAPI service that runs one **synthetic** patient through the care-team pipeline and streams
the events to the frontend. Your teammate's LangGraph harness can replace the orchestration: the event
stream (`/api/runs/{id}/events`) is the interface the frontend depends on.

## Run it
From the repo root, with the Workshop credentials exported in the same shell (never put them in a file):

```bash
# 1) backend (real Bedrock)
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

# 2) frontend (second terminal)
cd frontend && npm run build && npm run preview -- --port 4173   # or: npm run dev
# open http://localhost:4173
```

- Offline / no credentials: `BACKEND_MODE=mock .venv/bin/python -m uvicorn backend.app:app --port 8000`
- Models: `SPECIALIST_MODEL` and `DOCTOR_MODEL` (default `us.anthropic.claude-sonnet-4-6`).
- Tests (offline): `.venv/bin/python -m unittest backend.test_pipeline -v`
- Health: `curl localhost:8000/api/health` shows the mode and whether the guardrail is ready.

## What is code and what is a model
| Step | Decided by |
| --- | --- |
| Which specialist gets which input | plain code (the input type) |
| Low / normal / high for each lab value | plain code (reference ranges in the fixtures) |
| **Red-flag stop** (SpO2 < 90) | plain code, `core/safety.py`. No model is asked for guidance once a flag fires |
| Explaining each specialist's data | Strands agent on Bedrock (Sonnet 4.6), JSON output validated by pydantic |
| Combining findings into the summary | Strands agent on Bedrock (Sonnet 4.6) |
| Personal details / dosing advice in the summary | Bedrock Guardrail `caregiver-demo-guardrail`: PII is masked, dosing and prescribing topics are denied (the section is withheld) |

A failed specialist, or a missing input, becomes a visible `worker.failed` step and a partial result.

## Files
`fixtures.py` synthetic patients (edit here) · `events.py` event log · `specialists.py` agents and prompts ·
`guardrail.py` guardrail create/apply · `pipeline.py` the run · `app.py` HTTP API · `test_pipeline.py` offline tests

## Known limits
- **The patients are invented** and need a clinical read before the demo. Reference ranges are illustrative.
- Imaging is a written impression, not an image. Heart rhythm is summary numbers, not an ECG trace.
- Only one red-flag rule exists (the organizers' hypoxia example). Add more in `core/safety.py`.
- No review-confirm/resume action: a paused run stays paused.
- Runs are kept in memory; restarting the backend forgets them.
