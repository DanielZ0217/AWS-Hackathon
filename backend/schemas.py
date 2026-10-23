from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Modality = Literal["lab_report", "radiology_image", "ecg_image", "general", "unknown"]
Worker = Literal["lab", "radiology", "ecg", "nutrition", "physio"]
RunStatus = Literal[
    "queued", "running", "completed", "partial", "needs_clarification",
    "needs_human_review", "unsupported", "failed", "cancelled",
]


class ArtifactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=128)
    storage_reference: str | None = None
    modality: Modality = "unknown"
    modality_source: Literal["user_label", "classifier", "unknown"] = "unknown"
    upload_status: Literal["ready", "failed"] = "ready"
    uncertainty: str | None = None

    @model_validator(mode="after")
    def ready_artifacts_have_storage(self):
        if self.upload_status == "ready" and not self.storage_reference:
            raise ValueError("ready artifacts require storage_reference")
        return self


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = Field(default=None, max_length=128)
    patient_text: str = Field(default="", max_length=20_000)
    artifacts: list[ArtifactInput] = Field(default_factory=list, max_length=10)
    requested_outcomes: list[Literal[
        "understand_tests", "combined_explanation", "nutrition", "exercise"
    ]] = Field(default_factory=list)
    knowledge_snapshot: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_input(self):
        if not self.patient_text.strip() and not self.artifacts:
            raise ValueError("patient_text or at least one artifact is required")
        ids = [item.artifact_id for item in self.artifacts]
        if len(ids) != len(set(ids)):
            raise ValueError("artifact_id values must be unique")
        return self


class InformationNeed(BaseModel):
    id: str
    question: str
    evidence_type: Literal[
        "lab_report", "radiology_image", "ecg_image", "combined", "general", "unknown"
    ]
    artifact_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class IntakeResult(BaseModel):
    status: Literal["ready", "partial", "needs_clarification", "unsupported"]
    patient_summary: str
    structure: Literal["direct", "decompose"]
    requested_outcomes: list[str]
    information_needs: list[InformationNeed] = Field(max_length=5)
    missing_information: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    review_state: Literal["not_assessed"] = "not_assessed"


class RoutingAssignment(BaseModel):
    need_id: str
    worker: Worker
    artifact_ids: list[str]
    reason: str


class RoutingResult(BaseModel):
    assignments: list[RoutingAssignment]
    synthesis_need_ids: list[str] = Field(default_factory=list)
    unresolved_need_ids: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    method: Literal["model", "fallback"] = "fallback"


class EvidenceItem(BaseModel):
    id: str
    kind: Literal["passage", "graph_path"] = "passage"
    source_ids: list[str]
    passage_refs: list[str]
    excerpt: str
    rerank_score: float | None = None


class Observation(BaseModel):
    id: str
    description: str
    origin: Literal[
        "extracted_from_report", "model_inferred_from_image",
        "computed_from_supplied_values", "patient_reported",
    ]
    artifact_id: str | None = None
    source_locator: str | None = None
    value: str | int | float | None = None
    unit: str | None = None
    reference_interval: str | None = None
    uncertainty: str | None = None


class Interpretation(BaseModel):
    id: str
    statement: str
    observation_ids: list[str]
    evidence_ids: list[str]
    assertion: Literal["possible", "supported_explanation", "unresolved"]
    limitations: list[str] = Field(default_factory=list)


class RedFlag(BaseModel):
    id: str
    description: str
    supporting_observation_ids: list[str] = Field(default_factory=list)
    requires_human_review: bool = True


class EvidencePackage(BaseModel):
    schema_version: Literal[1] = 1
    package_id: str
    run_id: str
    task_id: str
    worker: Worker
    status: Literal["succeeded", "partial", "failed", "timed_out"]
    observations: list[Observation] = Field(default_factory=list)
    interpretations: list[Interpretation] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    red_flags: list[RedFlag] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    retrieval_status: Literal["complete", "degraded", "unavailable", "not_needed"]
    retrieval_trace: dict[str, Any] = Field(default_factory=dict)
    ontology_validation: Literal["not_run", "passed", "warnings", "failed"] = "not_run"
    provenance: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ReviewedClaim(BaseModel):
    claim_id: str
    statement: str
    observation_ids: list[str]
    evidence_ids: list[str]
    applicability: str
    uncertainty: str | None = None
    limitations: list[str] = Field(default_factory=list)


class DoctorReview(BaseModel):
    run_id: str
    review_id: str
    review_version: int = 1
    status: Literal["complete", "partial", "failed"]
    combined_summary: str
    supported_explanations: list[ReviewedClaim] = Field(default_factory=list)
    need_coverage: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    missing_patient_information: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    red_flags: list[RedFlag] = Field(default_factory=list)
    decision: Literal["proceed", "retrieve_more", "clarify", "human_review"]
    decision_reason: str


class AnswerSection(BaseModel):
    section_id: str
    order: int
    title: str
    text: str
    reviewed_claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    bundle_id: str
    bundle_version: int = 1
    rendering_method: Literal["model", "template"]


class WorkflowEvent(BaseModel):
    schema_version: Literal[1] = 1
    event_id: str
    run_id: str
    sequence: int
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    timestamp: str
    layer: Literal["01", "02", "03", "04", "05", "runtime"]
    node: str
    task_id: str | None = None
    need_ids: list[str] = Field(default_factory=list)
    type: str
    status: str
    summary: str
    source_worker: str | None = None
    destination_worker: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    review_version: int | None = None
    retrieval_round: int | None = None
    strategy: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    visibility: Literal["patient", "demo_detail", "operator"] = "demo_detail"

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()


class RunCreated(BaseModel):
    run_id: str
    status: RunStatus
    status_url: str
    events_url: str


class RunView(BaseModel):
    run_id: str
    status: RunStatus
    created_at: str
    updated_at: str
    state: dict[str, Any]

