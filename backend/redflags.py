"""The red-flag stop. Plain code, no model: a critical finding must not depend on a prompt.

ILLUSTRATIVE rules for the hackathon, not clinical guidance. They work on the dataset's own
fields (heart rate, the ECG machine report text, the X-ray labels). Any flag means: no guidance
until a healthcare professional reviews. Add rules here.
"""
from __future__ import annotations

import re
from typing import Any

from core.safety import RedFlagRule, check

from .store import Visit

HEART_RATE_RULE = RedFlagRule("heart_rate", lambda v: v < 40 or v > 150, "Extreme heart rate")

# The ECG reports are machine-generated and often over-cautious. That is exactly why a match here
# does not conclude anything: it only sends the case to a human.
_ECG_INJURY = re.compile(r"acute st elevation|consider acute|injury", re.IGNORECASE)


def ecg_flags(visit: Visit) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (flags, gaps) for the ECG of one visit."""
    gate = check({"heart_rate": visit.ecg.get("hr_bpm")}, rules=(HEART_RATE_RULE,), required=("heart_rate",))
    flags = [{"field": f["field"], "message": f["message"], "value": f["value"]} for f in gate.flags]
    report = visit.ecg.get("machine_report") or ""
    match = _ECG_INJURY.search(report)
    if match:
        flags.append(
            {
                "field": "ecg_report",
                "message": "The ECG report mentions possible acute heart muscle injury",
                "value": match.group(0),
            }
        )
    return flags, gate.gaps


def xray_flags(visit: Visit) -> list[dict[str, Any]]:
    if "Edema" in visit.xray.get("labels", []):
        return [{"field": "xray_edema", "message": "The chest X-ray label shows fluid in the lungs (pulmonary edema)", "value": "Edema"}]
    return []
