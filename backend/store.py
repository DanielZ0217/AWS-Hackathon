from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .schemas import WorkflowEvent


class Journal:
    """SQLite run/event journal. Events commit before subscribers are notified."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._conditions: dict[str, asyncio.Condition] = {}
        self._create_schema()

    def _create_schema(self):
        with self._lock, self._connection:
            self._connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    state_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence),
                    UNIQUE (run_id, event_id)
                );
                CREATE INDEX IF NOT EXISTS events_run_sequence
                    ON events(run_id, sequence);
            """)

    def close(self):
        with self._lock:
            self._connection.close()

    def create_run(self, run_id: str, timestamp: str, request: dict[str, Any]):
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, "queued", timestamp, timestamp, json.dumps(request), "{}"),
            )

    def save_run(self, run_id: str, status: str, timestamp: str, state: dict[str, Any]):
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE runs SET status=?, updated_at=?, state_json=? WHERE run_id=?",
                (status, timestamp, json.dumps(state), run_id),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        return {
            "run_id": row["run_id"], "status": row["status"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "state": json.loads(row["state_json"]),
        }

    async def append(self, event: WorkflowEvent) -> WorkflowEvent:
        with self._lock, self._connection:
            existing = self._connection.execute(
                "SELECT event_json FROM events WHERE run_id=? AND event_id=?",
                (event.run_id, event.event_id),
            ).fetchone()
            if existing:
                return WorkflowEvent.model_validate_json(existing["event_json"])
            row = self._connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS n FROM events WHERE run_id=?",
                (event.run_id,),
            ).fetchone()
            committed = event.model_copy(update={"sequence": int(row["n"]) + 1})
            self._connection.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?)",
                (committed.run_id, committed.sequence, committed.event_id,
                 committed.model_dump_json()),
            )
        condition = self._conditions.setdefault(event.run_id, asyncio.Condition())
        async with condition:
            condition.notify_all()
        return committed

    def events_after(self, run_id: str, sequence: int) -> list[WorkflowEvent]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT event_json FROM events WHERE run_id=? AND sequence>? ORDER BY sequence",
                (run_id, sequence),
            ).fetchall()
        return [WorkflowEvent.model_validate_json(row["event_json"]) for row in rows]

    async def wait_for_events(self, run_id: str, timeout: float = 15.0):
        condition = self._conditions.setdefault(run_id, asyncio.Condition())
        try:
            async with condition:
                await asyncio.wait_for(condition.wait(), timeout)
        except TimeoutError:
            return

