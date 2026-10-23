"""The three specialists and the doctor. Each is a Strands agent on Bedrock (Sonnet 4.6 by default).

Numbers are judged by plain Python (reference ranges, the red-flag gate), never by the model: the
model only explains values that code has already marked low, normal or high.
`mode="mock"` skips the model entirely and builds the answer from the same data, for offline use.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

SPECIALIST_MODEL = os.environ.get("SPECIALIST_MODEL", "us.anthropic.claude-sonnet-4-6")
DOCTOR_MODEL = os.environ.get("DOCTOR_MODEL", "us.anthropic.claude-sonnet-4-6")
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


class MissingInput(Exception):
    """The patient record has no data for this specialist. Reported, never guessed."""


class ModelOutputError(Exception):
    """The model's reply could not be read as the expected JSON."""


# --- output shapes -----------------------------------------------------------


class Finding(BaseModel):
    statement: str
    evidence: str = ""


class SpecialistOutput(BaseModel):
    summary: str
    findings: list[Finding] = []
    uncertainty: list[str] = []
    limitations: list[str] = []


class Section(BaseModel):
    title: str
    text: str
    based_on: list[str] = []


class DoctorOutput(BaseModel):
    decision: Literal["proceed", "clarify"]
    reason: str
    sections: list[Section]


@dataclass
class SpecialistInput:
    worker: str
    prompt_data: dict[str, Any]  # what the model is shown
    observations: dict[str, float]  # what the red-flag gate checks
    required: tuple[str, ...] = ()


@dataclass
class ModelResult:
    output: Any
    call: dict[str, Any]  # model, tokens, duration: the "model call" shown in technical details


# --- building each specialist's input (plain Python) ----------------------------


def _lab_status(value: float, low: float, high: float) -> str:
    return "low" if value < low else "high" if value > high else "normal"


def build_input(worker: str, preset: dict[str, Any]) -> SpecialistInput:
    if worker == "lab":
        labs = preset.get("labs")
        if not labs:
            raise MissingInput("No laboratory results were supplied.")
        rows = [
            {
                "name": name,
                "value": lab["value"],
                "unit": lab["unit"],
                "reference_range": f'{lab["low"]} to {lab["high"]}',
                "status": _lab_status(lab["value"], lab["low"], lab["high"]),
            }
            for name, lab in labs.items()
        ]
        return SpecialistInput(
            "lab",
            {"labs": rows},
            {name: lab["value"] for name, lab in labs.items()},
            required=("potassium", "sodium", "creatinine"),
        )
    if worker == "radiology":
        impression = preset.get("imaging")
        if not impression:
            raise MissingInput("No chest imaging report was supplied.")
        return SpecialistInput("radiology", {"imaging_impression": impression}, {})
    if worker == "ecg":
        ecg, vitals = preset.get("ecg"), preset.get("vitals")
        if not ecg and not vitals:
            raise MissingInput("No heart rhythm or vital sign data was supplied.")
        return SpecialistInput(
            "ecg",
            {"ecg_features": ecg, "vital_signs": vitals},
            dict(vitals or {}),
            required=("spo2",),
        )
    raise ValueError(f"unknown worker {worker!r}")


# --- prompts --------------------------------------------------------------------

_COMMON = """You are a specialist assistant in a hackathon prototype that explains SYNTHETIC patient data to a caregiver.
You are not a doctor. Do not diagnose, and do not mention medicines, doses, or treatment changes.
Use ONLY the data provided and never invent values. If something is missing or unclear, say so under "limitations".
Use cautious wording such as "may" or "could". Write in plain language a 12-year-old could follow.
Reply with a single JSON object and nothing else (no markdown), exactly in this form:
{"summary": "<one plain sentence>", "findings": [{"statement": "<plain sentence>", "evidence": "<the value or phrase it rests on>"}], "uncertainty": ["<what is uncertain>"], "limitations": ["<what you could not tell>"]}
Give at most 3 findings."""

PROMPTS = {
    "lab": _COMMON + "\nYour job: explain the laboratory results. Code has already marked each value low, normal or high; do not re-judge them.",
    "radiology": _COMMON + "\nYour job: explain the chest imaging impression. You were given a written impression, not the image itself; say so under limitations.",
    "ecg": _COMMON + "\nYour job: explain the heart rhythm features and vital signs. These are summary numbers, not the full ECG trace; say so under limitations.",
}

_DOCTOR_PROMPT = """You are the doctor-style synthesizer in a hackathon prototype that explains SYNTHETIC patient data to a caregiver. You are not a doctor.
You receive the findings from several specialists (and a list of any parts that could not be reviewed). Combine them into a short summary.
Rules: use ONLY what the specialists reported; never invent values; no diagnosis; no medicine names, doses, or treatment changes; cautious wording ("may", "could"); plain language a 12-year-old could follow.
If any part could not be reviewed, say plainly that the summary does not cover it.
Reply with a single JSON object and nothing else (no markdown), exactly in this form:
{"decision": "proceed" or "clarify", "reason": "<one sentence>", "sections": [{"title": "...", "text": "<2 to 4 short sentences>", "based_on": ["lab", "radiology", "ecg"]}]}
Use exactly these four section titles, in this order: "What was reviewed", "What the findings may mean", "Everyday habits to discuss", "Questions to ask your doctor".
"Everyday habits to discuss" may only suggest nutrition and gentle-movement topics to talk about with the care team, not instructions.
The last section must remind the reader this is a prototype, not medical advice. "based_on" lists only the specialists a section rests on."""

# --- talking to the model ------------------------------------------------------


def _parse_json(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ModelOutputError("the model reply had no JSON object")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ModelOutputError(f"the model reply was not valid JSON: {exc}") from exc


async def _ask(model_id: str, system_prompt: str, user_prompt: str, max_tokens: int) -> tuple[str, dict[str, Any]]:
    from strands import Agent  # imported here so mock mode needs no AWS libraries
    from strands.models import BedrockModel

    agent = Agent(
        model=BedrockModel(model_id=model_id, region_name=REGION, temperature=0.2, max_tokens=max_tokens),
        system_prompt=system_prompt,
        callback_handler=None,  # no console output
    )
    started = time.perf_counter()
    result = await agent.invoke_async(user_prompt)
    usage = result.metrics.accumulated_usage
    call = {
        "model": model_id,
        "input_tokens": usage.get("inputTokens"),
        "output_tokens": usage.get("outputTokens"),
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
    return str(result), call


async def run_specialist(spec: SpecialistInput, mode: str) -> ModelResult:
    if mode == "mock":
        return ModelResult(_mock_specialist(spec), {"model": "mock", "input_tokens": None, "output_tokens": None, "duration_ms": 0})
    text, call = await _ask(SPECIALIST_MODEL, PROMPTS[spec.worker], json.dumps(spec.prompt_data, indent=2), 800)
    try:
        return ModelResult(SpecialistOutput.model_validate(_parse_json(text)), call)
    except ValidationError as exc:
        raise ModelOutputError(f"the model reply did not match the expected shape: {exc.error_count()} problem(s)") from exc


async def run_doctor(results: dict[str, SpecialistOutput], missing: list[str], mode: str) -> ModelResult:
    if mode == "mock":
        return ModelResult(_mock_doctor(results, missing), {"model": "mock", "input_tokens": None, "output_tokens": None, "duration_ms": 0})
    payload = {
        "specialists": {worker: out.model_dump() for worker, out in results.items()},
        "could_not_be_reviewed": missing,
    }
    text, call = await _ask(DOCTOR_MODEL, _DOCTOR_PROMPT, json.dumps(payload, indent=2), 1500)
    try:
        return ModelResult(DoctorOutput.model_validate(_parse_json(text)), call)
    except ValidationError as exc:
        raise ModelOutputError(f"the model reply did not match the expected shape: {exc.error_count()} problem(s)") from exc


# --- mock mode (no model): built from the same data ----------------------------


def _mock_specialist(spec: SpecialistInput) -> SpecialistOutput:
    if spec.worker == "lab":
        odd = [r for r in spec.prompt_data["labs"] if r["status"] != "normal"]
        names = ", ".join(f'{r["name"]} ({r["status"]})' for r in odd)
        summary = f"These values are outside the usual range: {names}." if odd else "All lab values are in the usual range."
        return SpecialistOutput(
            summary=summary,
            findings=[Finding(statement=f'{r["name"]} is {r["status"]}.', evidence=f'{r["value"]} {r["unit"]}') for r in odd[:3]],
            uncertainty=["A single set of lab values cannot show a trend."],
            limitations=["Mock mode: no model was used."],
        )
    if spec.worker == "radiology":
        return SpecialistOutput(
            summary="The written chest imaging report lists findings worth discussing with a clinician.",
            findings=[Finding(statement=spec.prompt_data["imaging_impression"], evidence="imaging impression")],
            uncertainty=["The image itself was not reviewed."],
            limitations=["Mock mode: no model was used."],
        )
    vitals = spec.prompt_data.get("vital_signs") or {}
    return SpecialistOutput(
        summary=f'Oxygen level {vitals.get("spo2", "unknown")} and heart rate {vitals.get("heart_rate", "unknown")} were reviewed.',
        findings=[Finding(statement="Heart rhythm and vital signs were reviewed.", evidence=json.dumps(vitals))],
        uncertainty=["Summary numbers do not replace the full ECG trace."],
        limitations=["Mock mode: no model was used."],
    )


def _mock_doctor(results: dict[str, SpecialistOutput], missing: list[str]) -> DoctorOutput:
    names = {"lab": "lab results", "radiology": "chest imaging", "ecg": "heart rhythm and vital signs"}
    reviewed = ", ".join(names[w] for w in results)
    gap = f" The {', '.join(names[w] for w in missing)} could not be reviewed, so this summary does not cover it." if missing else ""
    return DoctorOutput(
        decision="clarify" if missing else "proceed",
        reason="Part of the review is missing." if missing else "All specialists returned usable findings.",
        sections=[
            Section(title="What was reviewed", text=f"The care team reviewed: {reviewed}.{gap}", based_on=list(results)),
            Section(title="What the findings may mean", text="Some results may be worth discussing with a clinician. Nothing here is a diagnosis.", based_on=list(results)),
            Section(title="Everyday habits to discuss", text="Ask your care team about food and gentle movement that suit you.", based_on=[]),
            Section(title="Questions to ask your doctor", text="Bring these results to a healthcare professional. This is a prototype and not medical advice.", based_on=[]),
        ],
    )
