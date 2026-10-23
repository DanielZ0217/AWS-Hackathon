"""A Bedrock Guardrail applied to the patient-facing text, as a second safety layer.

It is NOT the red-flag mechanism: guardrails filter text, they cannot judge a number. The red-flag
stop is plain code (core/safety.py). The guardrail catches what code cannot: personal details in
the text (masked, not blocked, so the run continues) and dosing or prescribing advice (denied).
If the guardrail cannot be created or called, the run still works and says it was unavailable.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any

REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
NAME = "caregiver-demo-guardrail"
BLOCKED_MESSAGE = "This part was withheld by a safety filter. Please ask a healthcare professional."


@dataclass
class GuardResult:
    action: str  # "allowed" | "masked" | "withheld" | "unavailable"
    text: str
    reason: str = ""


class Guard:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.guardrail_id: str | None = None
        self.version: str | None = None
        self.error: str | None = None

    # Run in a thread at startup: boto3 calls here are blocking.
    def ensure(self) -> None:
        if not self.enabled:
            return
        try:
            import boto3

            client = boto3.client("bedrock", region_name=REGION)
            existing = next((g for g in client.list_guardrails().get("guardrails", []) if g["name"] == NAME), None)
            if existing:
                self.guardrail_id = existing["id"]
                # Reuse the newest numbered version instead of creating another on every start.
                all_versions = client.list_guardrails(guardrailIdentifier=self.guardrail_id).get("guardrails", [])
                numbered = sorted((g["version"] for g in all_versions if str(g.get("version", "")).isdigit()), key=int)
                self.version = numbered[-1] if numbered else client.create_guardrail_version(guardrailIdentifier=self.guardrail_id)["version"]
                return

            created = client.create_guardrail(
                name=NAME,
                description="Caregiver demo: mask personal details and deny dosing or prescribing advice.",
                topicPolicyConfig={
                    "topicsConfig": [
                        {
                            "name": "Medication dosing and prescribing",
                            "definition": "Advice about specific medicines, doses, or starting, stopping or changing a prescription.",
                            "examples": [
                                "How much of this medicine should I take?",
                                "You should stop taking your heart pills.",
                                "Take 40 mg twice a day.",
                            ],
                            "type": "DENY",
                        }
                    ]
                },
                sensitiveInformationPolicyConfig={
                    "piiEntitiesConfig": [
                        {"type": kind, "action": "ANONYMIZE"} for kind in ("NAME", "EMAIL", "PHONE", "ADDRESS")
                    ]
                },
                blockedInputMessaging=BLOCKED_MESSAGE,
                blockedOutputsMessaging=BLOCKED_MESSAGE,
            )
            self.guardrail_id = created["guardrailId"]
            for _ in range(20):  # wait until it is ready
                if client.get_guardrail(guardrailIdentifier=self.guardrail_id).get("status") == "READY":
                    break
                time.sleep(1)
            self.version = client.create_guardrail_version(guardrailIdentifier=self.guardrail_id)["version"]
        except Exception as exc:  # noqa: BLE001 - the demo must keep working without it
            self.error = f"{type(exc).__name__}: {str(exc)[:200]}"
            self.guardrail_id = self.version = None

    @property
    def ready(self) -> bool:
        return self.guardrail_id is not None and self.version is not None

    def _apply(self, text: str) -> dict[str, Any]:
        import boto3

        runtime = boto3.client("bedrock-runtime", region_name=REGION)
        return runtime.apply_guardrail(
            guardrailIdentifier=self.guardrail_id,
            guardrailVersion=self.version,
            source="OUTPUT",
            content=[{"text": {"text": text}}],
        )

    async def check(self, text: str) -> GuardResult:
        if not self.ready:
            return GuardResult("unavailable", text, self.error or "guardrail is not enabled")
        try:
            response = await asyncio.to_thread(self._apply, text)
        except Exception as exc:  # noqa: BLE001
            return GuardResult("unavailable", text, f"{type(exc).__name__}")
        if response.get("action") != "GUARDRAIL_INTERVENED":
            return GuardResult("allowed", text)
        assessments = response.get("assessments") or []
        blocked_topics = [
            t["name"]
            for a in assessments
            for t in (a.get("topicPolicy") or {}).get("topics", [])
            if t.get("action") == "BLOCKED"
        ]
        if blocked_topics:
            return GuardResult("withheld", BLOCKED_MESSAGE, f"denied topic: {', '.join(blocked_topics)}")
        masked = (response.get("outputs") or [{}])[0].get("text", text)
        return GuardResult("masked", masked, "personal details were masked")
