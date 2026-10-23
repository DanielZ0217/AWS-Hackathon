"""Deterministic red-flag gate. Plain Python, no LLM: safety must not depend on a prompt.

Standalone (stdlib only) so it can be pasted into whatever the team builds.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Mapping


@dataclass(frozen=True)
class RedFlagRule:
    name: str  # observation key, e.g. "spo2"; must match the team's field names
    test: Callable[[float], bool]  # True means the value is critical
    message: str


# TEMPLATE ONLY. The track guardrails mention "severe hypoxia" as an example red flag, so this
# is the single example rule. The key name and threshold are placeholders, not clinical
# guidance: replace or extend this once the team picks its scenario and data format.
DEFAULT_RULES: tuple[RedFlagRule, ...] = (
    RedFlagRule("spo2", lambda v: v < 90, "Severe hypoxia (SpO2 < 90%)"),
)


@dataclass
class GateResult:
    flags: list[dict] = field(default_factory=list)  # critical values found
    gaps: list[dict] = field(default_factory=list)   # missing / unreadable values

    @property
    def halted(self) -> bool:
        """True if recommendations must stop until a human confirms."""
        return bool(self.flags)

    @property
    def needs_reevaluation(self) -> bool:
        return bool(self.gaps)


def check(
    observations: Mapping[str, object],
    rules: tuple[RedFlagRule, ...] = DEFAULT_RULES,
    required: tuple[str, ...] = (),
) -> GateResult:
    """Run every rule. A missing or unparseable value is a gap, never treated as normal.

    `required` lists keys that must be present; absence is reported as a gap even if no rule
    covers that key.
    """
    result = GateResult()

    for key in required:
        if observations.get(key) is None:
            result.gaps.append({"field": key, "reason": "missing"})

    for rule in rules:
        raw = observations.get(rule.name)
        if raw is None:
            continue  # absence only matters if the key is in `required`
        try:
            value = float(raw)
        except (TypeError, ValueError):
            result.gaps.append({"field": rule.name, "reason": f"unreadable value {raw!r}"})
            continue
        if not math.isfinite(value):
            result.gaps.append({"field": rule.name, "reason": f"non-finite value {raw!r}"})
            continue
        if rule.test(value):
            result.flags.append({"field": rule.name, "value": value, "message": rule.message})

    return result
