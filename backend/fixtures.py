"""SYNTHETIC demo patients. Every value here is invented for the hackathon demo.

They are not real patient data and the reference ranges are illustrative. Have a clinician or
mentor read them before the demo. Add or edit presets here; the rest of the backend does not
care which patients exist.
"""
from __future__ import annotations

from typing import Any


def _lab(value: float, unit: str, low: float, high: float) -> dict[str, Any]:
    return {"value": value, "unit": unit, "low": low, "high": high}


_BASE_LABS = {
    "bnp": _lab(640, "pg/mL", 0, 100),
    "creatinine": _lab(1.3, "mg/dL", 0.6, 1.3),
    "potassium": _lab(4.1, "mmol/L", 3.5, 5.0),
    "sodium": _lab(138, "mmol/L", 135, 145),
    "hemoglobin": _lab(12.4, "g/dL", 12.0, 16.0),
}

_SYNTHETIC_NOTE = "Synthetic features invented for the demo."

PRESETS: dict[str, dict[str, Any]] = {
    "demo-001": {
        "id": "demo-001",
        "label": "Standard case",
        "description": "Three specialists review one synthetic patient in parallel, the doctor combines their findings, and a plain-language summary is produced.",
        "patient": "Synthetic patient, age 72, with two weeks of breathlessness on exertion and ankle swelling.",
        "labs": _BASE_LABS,
        "vitals": {"spo2": 94, "heart_rate": 88, "sbp": 128},
        "ecg": {"rhythm": "regular", "rate_bpm": 88, "qrs_ms": 92, "qtc_ms": 430, "note": _SYNTHETIC_NOTE},
        "imaging": (
            "Synthetic chest imaging impression: mildly enlarged heart shadow, small fluid collections "
            "at the bottom of both lungs, and mild congestion of the lung blood vessels. No collapsed lung."
        ),
    },
    "demo-002": {
        "id": "demo-002",
        "label": "Red-flag safety stop",
        "description": "A specialist reports a critical value. Care guidance is paused and a human must review.",
        "patient": "Synthetic patient, age 72, with worsening breathlessness at rest.",
        "labs": {**_BASE_LABS, "bnp": _lab(1450, "pg/mL", 0, 100), "potassium": _lab(5.1, "mmol/L", 3.5, 5.0)},
        "vitals": {"spo2": 84, "heart_rate": 112, "sbp": 104},
        "ecg": {"rhythm": "irregular", "rate_bpm": 112, "qrs_ms": 96, "qtc_ms": 448, "note": _SYNTHETIC_NOTE},
        "imaging": (
            "Synthetic chest imaging impression: enlarged heart shadow and increased fluid in both lungs, "
            "with small fluid collections at the bottom of both lungs."
        ),
    },
    "demo-003": {
        "id": "demo-003",
        "label": "Missing analysis",
        "description": "The chest imaging report is missing. The run continues, states the gap, and asks for clinical re-evaluation.",
        "patient": "Synthetic patient, age 72, with two weeks of breathlessness on exertion and ankle swelling.",
        "labs": _BASE_LABS,
        "vitals": {"spo2": 94, "heart_rate": 88, "sbp": 128},
        "ecg": {"rhythm": "regular", "rate_bpm": 88, "qrs_ms": 92, "qtc_ms": 430, "note": _SYNTHETIC_NOTE},
        "imaging": None,
    },
}


def preset_summaries() -> list[dict[str, str]]:
    return [{"id": p["id"], "label": p["label"], "description": p["description"]} for p in PRESETS.values()]
