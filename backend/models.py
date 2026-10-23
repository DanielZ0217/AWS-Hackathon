from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from pydantic import BaseModel, Field

from cloud.bedrock import Bedrock


class ModelObservation(BaseModel):
    artifact_id: str
    description: str = Field(min_length=1, max_length=1800)
    source_locator: str = Field(min_length=1, max_length=300)
    uncertainty: str = Field(min_length=1, max_length=600)


class SpecialistResult(BaseModel):
    observations: list[ModelObservation] = Field(max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=10)
    retrieval_query: str = Field(min_length=1, max_length=1200)


class BedrockModelGateway:
    """Validated JSON calls for agent roles; no hidden reasoning is requested or stored."""

    def __init__(self, cloud: Bedrock | None = None):
        self.cloud = cloud or Bedrock()

    async def specialist(self, role: str, question: str, artifacts: dict[str, str],
                         images: dict[str, tuple[str, bytes]] | None = None) -> SpecialistResult:
        if role not in {"lab", "radiology", "ecg"}:
            raise ValueError(f"Unsupported diagnostic specialist: {role}")
        system = (
            "You are an educational clinical evidence extraction specialist. Extract only explicit "
            "findings from the supplied reports. Do not diagnose, invent measurements, or provide care "
            "instructions. Preserve negation and uncertainty. Return JSON only with keys observations, "
            "limitations, retrieval_query. Each observation must have artifact_id, description, "
            "source_locator, uncertainty. Keep retrieval_query focused on authoritative background "
            "needed to explain the observed findings. artifact_id must exactly copy one of the keys in "
            "the artifacts object; never substitute a patient or report identifier."
        )
        images = images or {}
        payload = {"question": question, "specialty": role, "artifacts": artifacts,
                   "attached_image_ids": list(images)}
        content: list[dict[str, Any]] = [{"text": json.dumps(payload)}]
        for artifact_id, (image_format, image_bytes) in images.items():
            content.extend([
                {"text": f"The next image has artifact_id {artifact_id}."},
                {"image": {"format": image_format, "source": {"bytes": image_bytes}}},
            ])
        tool_name = "submit_specialist_result"
        tool_config = {
            "tools": [{"toolSpec": {
                "name": tool_name,
                "description": "Submit the validated specialist evidence extraction.",
                "inputSchema": {"json": SpecialistResult.model_json_schema()},
            }}],
            "toolChoice": {"tool": {"name": tool_name}},
        }
        last_error: Exception | None = None
        for attempt in range(2):
            attempt_system = system if attempt == 0 else (
                system + " Your previous response failed schema validation. Every field must be present; "
                "use a non-empty string for uncertainty and source_locator, and use only the supplied "
                "artifact keys. Return one JSON object with no markdown."
            )
            response = await asyncio.to_thread(
                self.cloud.converse,
                role,
                [{"role": "user", "content": content}],
                attempt_system,
                1800,
                tool_config,
            )
            try:
                return SpecialistResult.model_validate(self._structured_from_response(response, tool_name))
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
        raise ValueError("Specialist model failed validated JSON after one retry") from last_error

    @classmethod
    def _structured_from_response(cls, response: dict[str, Any], tool_name: str) -> dict[str, Any]:
        blocks = response.get("output", {}).get("message", {}).get("content", [])
        for block in blocks:
            tool_use = block.get("toolUse")
            if tool_use and tool_use.get("name") == tool_name:
                return tool_use.get("input", {})
        return cls._json_from_response(response)

    @staticmethod
    def _json_from_response(response: dict[str, Any]) -> dict[str, Any]:
        blocks = response.get("output", {}).get("message", {}).get("content", [])
        text = "\n".join(block.get("text", "") for block in blocks if "text" in block).strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1)
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Model response did not contain a JSON object")
        return json.loads(text[start:end + 1])
