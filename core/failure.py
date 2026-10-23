"""Explicit failure handling: a failed step becomes a flagged gap, not a crash or a guess.

Standalone (stdlib only) so it can be pasted into whatever the team builds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

REEVAL_MESSAGE = "Step failed; clinical re-evaluation requested. No recommendation made from this input."


@dataclass
class StepResult:
    ok: bool
    value: Any = None
    reason: str | None = None  # exception type + message when ok is False

    @property
    def message(self) -> str | None:
        return None if self.ok else REEVAL_MESSAGE


def guarded(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> StepResult:
    """Call fn; on any exception return ok=False with the reason instead of raising.

    Callers should record the result (e.g. in their trace/log) and carry the gap forward to
    the patient-facing output rather than silently dropping it.
    """
    try:
        return StepResult(ok=True, value=fn(*args, **kwargs))
    except Exception as exc:  # noqa: BLE001 - deliberately broad: a bad input must not crash the demo
        return StepResult(ok=False, reason=f"{type(exc).__name__}: {exc}")
