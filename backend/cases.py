"""The cases the app offers: one per visit of the demo patient."""
from __future__ import annotations

from dataclasses import dataclass

from . import redflags
from .store import FileStore, Patient, Visit


@dataclass(frozen=True)
class Case:
    id: str
    label: str
    description: str
    store: FileStore
    patient: Patient
    visit: Visit


def build_cases(store: FileStore, patient: Patient) -> dict[str, Case]:
    cases: dict[str, Case] = {}
    total = len(patient.visits)
    for visit in patient.visits:
        ecg, _ = redflags.ecg_flags(visit)
        critical = bool(ecg or redflags.xray_flags(visit))
        if critical:
            description = "A critical finding is flagged, so care guidance pauses for a healthcare professional to review."
        elif visit.index > 0:
            description = "No critical flags. The summary explains the findings and how they changed since the earlier visit."
        else:
            description = "No critical flags. The summary explains the findings in plain language."
        case_id = f"{patient.patient_id}-v{visit.index + 1}"
        cases[case_id] = Case(
            id=case_id,
            label=f"Visit {visit.index + 1} of {total} (day {visit.day})",
            description=description,
            store=store,
            patient=patient,
            visit=visit,
        )
    return cases


def preset_summaries(cases: dict[str, Case]) -> list[dict[str, str]]:
    return [{"id": c.id, "label": c.label, "description": c.description} for c in cases.values()]
