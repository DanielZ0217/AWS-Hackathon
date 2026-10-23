"""An append-only event log for one run, in the shape the frontend validates (WorkflowEvent)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

TERMINAL_TYPES = {"run.completed", "run.partial", "run.failed", "run.cancelled", "run.paused"}


class RunLog:
    def __init__(self, run_id: str, preset_id: str) -> None:
        self.run_id = run_id
        self.preset_id = preset_id
        self.events: list[dict[str, Any]] = []
        self.done = False
        self._cond = asyncio.Condition()

    async def emit(
        self,
        type_: str,
        summary: str,
        *,
        visibility: str = "demo_detail",
        node: str | None = None,
        task_id: str | None = None,
        need_ids: list[str] | None = None,
        status: str | None = None,
        source_worker: str | None = None,
        destination_worker: str | None = None,
        evidence_ids: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._cond:
            sequence = len(self.events) + 1
            event: dict[str, Any] = {
                "schema_version": "backend-0",
                "event_id": f"{self.run_id}-evt-{sequence:03d}",
                "run_id": self.run_id,
                "sequence": sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": f"trace-{self.run_id}",
                "type": type_,
                "summary": summary,
                "visibility": visibility,
                "node": node,
                "task_id": task_id,
                "need_ids": need_ids or [],
                "status": status,
                "source_worker": source_worker,
                "destination_worker": destination_worker,
                "artifact_ids": [],
                "evidence_ids": evidence_ids or [],
                "payload": payload or {},
            }
            self.events.append(event)
            if type_ in TERMINAL_TYPES:
                self.done = True
            self._cond.notify_all()
            return event

    async def wait_for_more(self, index: int, timeout: float) -> tuple[list[dict[str, Any]], bool]:
        """Events after `index`, waiting up to `timeout` seconds. Also says whether the run is over."""
        async with self._cond:
            try:
                await asyncio.wait_for(self._cond.wait_for(lambda: len(self.events) > index or self.done), timeout)
            except asyncio.TimeoutError:
                pass
            return self.events[index:], self.done
