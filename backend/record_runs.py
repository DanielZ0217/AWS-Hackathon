"""Record a REAL run of every visit into the frontend, for the "Recorded replay" fallback.

    .venv/bin/python -m backend.record_runs        (needs AWS credentials in the environment)

Each file holds the exact events a live run produced (real model output, real guardrail check).
The frontend replays them with their original timing, labeled as a recording. Re-run this whenever
the patient data, prompts, or red-flag rules change.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .cases import build_cases
from .events import RunLog
from .guardrail import Guard
from .pipeline import run_pipeline
from .store import DEMO_PATIENT, LocalStore, load_patient

OUT = Path(__file__).resolve().parent.parent / "frontend" / "src" / "recorded"


async def main() -> None:
    store = LocalStore()
    cases = build_cases(store, load_patient(store, DEMO_PATIENT))
    guard = Guard(enabled=True)
    await asyncio.to_thread(guard.ensure)
    if not guard.ready:
        raise SystemExit(f"The guardrail is not ready ({guard.error}); refusing to record a run without it.")

    OUT.mkdir(parents=True, exist_ok=True)
    for case in cases.values():
        log = RunLog(f"run-recorded-{case.id.lower()}", case.id)
        await run_pipeline(log, case, "bedrock", guard)
        record = {"id": case.id, "label": case.label, "description": case.description, "events": log.events}
        (OUT / f"{case.id}.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
        print(f"recorded {case.id}: {len(log.events)} events, ended with {log.events[-1]['type']}")


if __name__ == "__main__":
    asyncio.run(main())
