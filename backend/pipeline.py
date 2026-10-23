"""One run: intake, routing, parallel specialists, the red-flag gate, the doctor, the guardrail, the summary.

Routing is deterministic (the input type decides the specialist), the red-flag gate is plain code,
and every step becomes an event in the log. A failed step becomes a visible gap, never a crash.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from . import specialists
from .cases import Case
from .events import RunLog
from .guardrail import Guard

DOCTOR = "doctor_synthesis"

WORKERS = {
    "radiology": {"task": "task-radiology", "need": "need-1", "label": "Chest image", "question": "What does the chest X-ray show?"},
    "ecg": {"task": "task-ecg", "need": "need-2", "label": "Heart rhythm", "question": "What does the heart tracing (ECG) show?"},
}
ALL_NEEDS = ["need-1", "need-2", "need-3"]
PROTOTYPE_LIMIT = "Prototype output. Not clinical clearance."
PROVENANCE_LIMIT = (
    "This virtual patient combines an ECG and a chest X-ray from two different real people. "
    "The ECG report was written by a machine and not confirmed by a cardiologist."
)


@dataclass
class Outcome:
    worker: str
    ok: bool
    output: specialists.SpecialistOutput | None = None
    flags: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _Shared:
    review_raised: bool = False


def _worker_fields(worker: str) -> dict[str, Any]:
    meta = WORKERS[worker]
    return {"node": worker, "task_id": meta["task"], "need_ids": [meta["need"]]}


async def run_pipeline(log: RunLog, case: Case, mode: str, guard: Guard) -> None:
    """Never raises. Always ends the log with exactly one terminal event."""
    try:
        await _run(log, case, mode, guard)
    except Exception as exc:  # noqa: BLE001 - nothing may crash the demo
        if not log.done:
            await log.emit(
                "run.failed",
                "The review could not be completed",
                visibility="patient",
                payload={
                    "outcome": "failed",
                    "limitations": ["The review could not be completed. A clinician should look at the results directly.", PROVENANCE_LIMIT],
                    "error_category": type(exc).__name__,
                },
            )


async def _run(log: RunLog, case: Case, mode: str, guard: Guard) -> None:
    patient, visit = case.patient, case.visit
    await log.emit(
        "run.started",
        f"Run started for virtual patient {patient.patient_id}, visit {visit.index + 1}",
        visibility="patient",
        payload={"preset_id": case.id, "patient_id": patient.patient_id, "visit": visit.index + 1, "day": visit.day},
    )
    await log.emit("intake.started", "Organizing the request")
    await log.emit(
        "intake.decomposed",
        "Organized request into 3 questions",
        need_ids=ALL_NEEDS,
        payload={
            "needs": [{"need_id": m["need"], "question": m["question"]} for m in WORKERS.values()]
            + [{"need_id": "need-3", "question": "Explain the combined picture in plain language."}]
        },
    )

    # Routing is deterministic: the type of input decides the specialist. No model is needed.
    for worker, meta in WORKERS.items():
        await log.emit(
            "routing.assigned",
            f'{meta["question"]} Assigned to {meta["label"]}.',
            **_worker_fields(worker),
            source_worker="orchestrator",
            destination_worker=worker,
            payload={"question": meta["question"], "reason": f"The need concerns the supplied {meta['label'].lower()} data."},
        )
    for worker, meta in WORKERS.items():
        await log.emit(
            "worker.started",
            f'{meta["label"]}: review started',
            **_worker_fields(worker),
            source_worker="orchestrator",
            destination_worker=worker,
            status="running",
        )

    shared = _Shared()
    outcomes = await asyncio.gather(*(_run_worker(log, w, case, mode, shared) for w in WORKERS))

    failed = [o.worker for o in outcomes if not o.ok]
    flags = [f for o in outcomes for f in o.flags]

    # A red flag stops everything: no model is asked for guidance, and no summary is produced.
    if flags:
        await log.emit(
            "doctor.review_completed",
            "Doctor: human review required",
            node=DOCTOR,
            source_worker=DOCTOR,
            payload={"decision": "human_review", "reason": "A red flag is unresolved. No guidance will be produced."},
        )
        await log.emit(
            "run.paused",
            "Paused for human review",
            visibility="patient",
            payload={
                "outcome": "needs_human_review",
                "resumable": False,
                "flag_ids": [f["flag_id"] for f in flags],
                "limitations": ["No guidance was produced because a critical finding needs review.", PROVENANCE_LIMIT],
            },
        )
        return

    good = {o.worker: o.output for o in outcomes if o.ok and o.output}
    earlier = [
        {
            "day": v.day,
            "heart_rate_bpm": v.ecg.get("hr_bpm"),
            "ecg_machine_report": v.ecg.get("machine_report"),
            "xray_reference_labels": v.xray.get("labels", []),
        }
        for v in patient.visits[: visit.index]
    ]
    doctor = await specialists.run_doctor(good, failed, earlier, mode)
    out: specialists.DoctorOutput = doctor.output
    decision = "clarify" if failed else out.decision
    await log.emit(
        "doctor.review_completed",
        "Doctor: partial picture, some parts could not be reviewed" if failed else "Doctor: enough support for a qualified explanation",
        node=DOCTOR,
        source_worker=DOCTOR,
        payload={"decision": decision, "reason": out.reason, "model_call": doctor.call},
    )

    # Second safety layer: the guardrail checks every patient-facing section.
    await log.emit("guidance.started", "Checking the summary with the safety filter", source_worker=DOCTOR)
    checked = [await guard.check(s.text) for s in out.sections]
    withheld = sum(r.action == "withheld" for r in checked)
    masked = sum(r.action == "masked" for r in checked)
    unavailable = any(r.action == "unavailable" for r in checked)
    await log.emit(
        "guidance.checked",
        "Safety filter was not available for this run" if unavailable else "Safety filter check finished",
        payload={
            "passed": None if unavailable else withheld == 0,
            "withheld_sections": withheld,
            "masked_sections": masked,
            "guardrail": {"id": guard.guardrail_id, "version": guard.version, "available": not unavailable},
        },
    )

    await log.emit("answer.started", "Preparing your summary", visibility="patient")
    for index, (section, result) in enumerate(zip(out.sections, checked), start=1):
        if result.action == "withheld":
            continue
        await log.emit(
            "answer.section",
            f"Section ready: {section.title}",
            visibility="patient",
            evidence_ids=[f"ev-{w}-1" for w in section.based_on if w in good],
            payload={"section_id": f"section-{index}", "order": index, "title": section.title, "text": result.text, "rendering": "model"},
        )
    await log.emit("answer.completed", "Summary ready", visibility="patient")

    limitations = [PROTOTYPE_LIMIT, PROVENANCE_LIMIT]
    limitations += [f"{WORKERS[w]['label']} could not be reviewed." for w in failed]
    if withheld:
        limitations.append(f"{withheld} section(s) were withheld by the safety filter.")
    if unavailable:
        limitations.append("The safety filter was not available for this run.")

    if failed:
        await log.emit("run.partial", "Run finished with a partial result", visibility="patient", payload={"outcome": "partial", "limitations": limitations})
    else:
        await log.emit("run.completed", "Run completed with stated limitations", visibility="patient", payload={"outcome": "completed", "limitations": limitations})


async def _run_worker(log: RunLog, worker: str, case: Case, mode: str, shared: _Shared) -> Outcome:
    meta = WORKERS[worker]
    common = {**_worker_fields(worker), "source_worker": worker, "destination_worker": DOCTOR}
    try:
        # Reading files and drawing the ECG are blocking, so they run in a thread.
        spec = await asyncio.to_thread(specialists.build_input, worker, case, mode != "mock")
        result = await specialists.run_specialist(spec, mode)
    except specialists.MissingInput as exc:
        await log.emit(
            "worker.failed",
            f'{meta["label"]}: couldn\'t be reviewed',
            **common,
            status="failed",
            payload={"error_category": "missing_input", "limitation": str(exc), "next_action": "Clinical re-evaluation requested."},
        )
        return Outcome(worker, ok=False)
    except Exception as exc:  # noqa: BLE001
        await log.emit(
            "worker.failed",
            f'{meta["label"]}: couldn\'t be reviewed',
            **common,
            status="failed",
            payload={
                "error_category": "analysis_unavailable",
                "limitation": f'The {meta["label"].lower()} could not be analyzed.',
                "next_action": "Clinical re-evaluation requested.",
                "detail": type(exc).__name__,
            },
        )
        return Outcome(worker, ok=False)

    output: specialists.SpecialistOutput = result.output
    flags = [
        {
            "flag_id": f"flag-{f['field']}",
            "description": f["message"],
            "supporting_observation_ids": [f"obs-{worker}-{f['field']}"],
            "requires_human_review": True,
        }
        for f in spec.flags
    ]
    limitations = output.limitations + [f"Missing value: {g['field']} ({g['reason']})" for g in spec.gaps]
    await log.emit(
        "worker.completed",
        f'{meta["label"]}: {output.summary}',
        **common,
        status="succeeded",
        evidence_ids=[f"ev-{worker}-1"],
        payload={
            "limitations": limitations,
            "uncertainty": output.uncertainty,
            "findings": [f.model_dump() for f in output.findings],
            "red_flags": flags,
            "model_call": result.call,
        },
    )
    if flags and not shared.review_raised:
        shared.review_raised = True
        await log.emit(
            "review.required",
            "A critical finding needs review by a healthcare professional before any guidance is given",
            visibility="patient",
            source_worker="orchestrator",
            payload={"flag_ids": [f["flag_id"] for f in flags], "resumable": False},
        )
    return Outcome(worker, ok=True, output=output, flags=flags)
