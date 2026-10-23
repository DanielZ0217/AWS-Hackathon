from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from .knowledge import KnowledgeProvider, to_evidence_items
from .models import BedrockModelGateway
from .schemas import (
    AnswerSection, DoctorReview, EvidencePackage, InformationNeed, IntakeResult,
    Observation, RedFlag, ReviewedClaim, RoutingAssignment, RoutingResult, RunRequest,
    WorkflowEvent,
)
from .store import Journal


TERMINAL = {"completed", "partial", "needs_clarification", "needs_human_review", "unsupported", "failed", "cancelled"}
DIAGNOSTIC_WORKERS = {"lab", "radiology", "ecg"}


class WorkflowState(TypedDict, total=False):
    run_id: str
    trace_id: str
    request: dict[str, Any]
    intake: dict[str, Any]
    routing: dict[str, Any]
    evidence_packages: dict[str, Any]
    doctor_review: dict[str, Any]
    reviewed_content_bundle: dict[str, Any]
    answer_sections: list[dict[str, Any]]
    final_response: str
    runtime_status: str


class WorkflowEngine:
    def __init__(self, journal: Journal, knowledge: KnowledgeProvider, artifact_root: str | Path,
                 models: BedrockModelGateway | None = None):
        self.journal = journal
        self.knowledge = knowledge
        self.artifact_root = Path(artifact_root).resolve()
        self.models = models
        self.cancelled: set[str] = set()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(WorkflowState)
        graph.add_node("intake", self._intake)
        graph.add_node("route", self._route)
        graph.add_node("diagnostics", self._diagnostics)
        graph.add_node("doctor", self._doctor)
        graph.add_node("guidance", self._guidance)
        graph.add_node("generate", self._generate)
        graph.add_edge(START, "intake")
        graph.add_edge("intake", "route")
        graph.add_edge("route", "diagnostics")
        graph.add_edge("diagnostics", "doctor")
        graph.add_edge("doctor", "guidance")
        graph.add_edge("guidance", "generate")
        graph.add_edge("generate", END)
        return graph.compile()

    async def _emit(self, state: WorkflowState, layer: str, node: str, event_type: str,
                    status: str, summary: str, **extra) -> WorkflowEvent:
        event = WorkflowEvent(
            event_id=f"evt-{uuid4().hex}", run_id=state["run_id"], sequence=0,
            trace_id=state["trace_id"], span_id=f"span-{uuid4().hex}",
            timestamp=WorkflowEvent.now(), layer=layer, node=node, type=event_type,
            status=status, summary=summary, **extra,
        )
        return await self.journal.append(event)

    def cancel(self, run_id: str):
        self.cancelled.add(run_id)

    def _check_cancelled(self, state: WorkflowState):
        if state["run_id"] in self.cancelled:
            raise asyncio.CancelledError

    async def run(self, run_id: str, request: RunRequest):
        state: WorkflowState = {
            "run_id": run_id, "trace_id": f"trace-{uuid4().hex}",
            "request": request.model_dump(mode="json"), "runtime_status": "running",
            "evidence_packages": {}, "answer_sections": [],
        }
        await self._emit(state, "runtime", "run", "run.started", "running", "Request accepted.")
        self.journal.save_run(run_id, "running", WorkflowEvent.now(), state)
        try:
            final_state = await self.graph.ainvoke(state)
            status = final_state.get("runtime_status", "completed")
            self.journal.save_run(run_id, status, WorkflowEvent.now(), final_state)
            await self._emit(final_state, "runtime", "run", f"run.{status}", status,
                             f"Run ended with status {status}.", visibility="patient")
        except asyncio.CancelledError:
            state["runtime_status"] = "cancelled"
            self.journal.save_run(run_id, "cancelled", WorkflowEvent.now(), state)
            await self._emit(state, "runtime", "run", "run.cancelled", "cancelled",
                             "Run cancelled; no new work will be scheduled.", visibility="patient")
        except Exception as exc:
            state["runtime_status"] = "failed"
            self.journal.save_run(run_id, "failed", WorkflowEvent.now(), state)
            await self._emit(state, "runtime", "run", "run.failed", "failed",
                             f"Workflow failed: {type(exc).__name__}.", visibility="patient")

    async def _intake(self, state: WorkflowState) -> dict[str, Any]:
        self._check_cancelled(state)
        await self._emit(state, "01", "intake", "intake.started", "running",
                         "Organizing the request and artifact references.")
        request = RunRequest.model_validate(state["request"])
        needs: list[InformationNeed] = []
        unknown = []
        mapping = {
            "lab_report": "Explain the supplied laboratory results.",
            "radiology_image": "Explain the supplied radiology evidence.",
            "ecg_image": "Explain the supplied ECG evidence.",
        }
        for artifact in request.artifacts:
            if artifact.upload_status != "ready":
                continue
            if artifact.modality == "unknown":
                unknown.append(artifact.artifact_id)
                continue
            if artifact.modality in mapping:
                needs.append(InformationNeed(
                    id=f"need-{len(needs)+1}", question=mapping[artifact.modality],
                    evidence_type=artifact.modality, artifact_ids=[artifact.artifact_id],
                ))
        if request.patient_text.strip() and not needs:
            needs.append(InformationNeed(id="need-1", question=request.patient_text.strip(),
                                         evidence_type="general"))
        if len(needs) > 1 or any(x in request.requested_outcomes for x in ("combined_explanation", "nutrition", "exercise")):
            needs.append(InformationNeed(
                id=f"need-{len(needs)+1}",
                question="Explain how the available findings fit together and address the requested outcomes.",
                evidence_type="combined", artifact_ids=[a.artifact_id for a in request.artifacts if a.upload_status == "ready"],
                depends_on=[need.id for need in needs],
            ))
        needs = needs[:5]
        status = "needs_clarification" if unknown and not needs else ("partial" if unknown else "ready")
        intake = IntakeResult(
            status=status, patient_summary=request.patient_text.strip() or "Patient wants help understanding uploaded tests.",
            structure="direct" if len(needs) <= 1 else "decompose",
            requested_outcomes=request.requested_outcomes, information_needs=needs,
            uncertainty_notes=[f"Unknown artifact category: {item}" for item in unknown],
            clarification_question="What type of test is the unknown upload?" if unknown else None,
        )
        await self._emit(state, "01", "intake", "intake.decomposed", "completed",
                         f"Organized the request into {len(needs)} validated question(s).",
                         need_ids=[need.id for need in needs],
                         artifact_ids=[a.artifact_id for a in request.artifacts],
                         payload={"needs": [need.model_dump() for need in needs], "intake_status": status})
        return {"intake": intake.model_dump(mode="json")}

    async def _route(self, state: WorkflowState) -> dict[str, Any]:
        self._check_cancelled(state)
        intake = IntakeResult.model_validate(state["intake"])
        assignments: list[RoutingAssignment] = []
        unresolved: list[str] = []
        modality_worker = {"lab_report": "lab", "radiology_image": "radiology", "ecg_image": "ecg"}
        for need in intake.information_needs:
            worker = modality_worker.get(need.evidence_type)
            if worker:
                assignments.append(RoutingAssignment(
                    need_id=need.id, worker=worker, artifact_ids=need.artifact_ids,
                    reason=f"Known {need.evidence_type} evidence routes to {worker}.",
                ))
            elif need.evidence_type == "combined":
                if "nutrition" in intake.requested_outcomes:
                    assignments.append(RoutingAssignment(need_id=need.id, worker="nutrition", artifact_ids=[], reason="Nutrition was requested after review."))
                if "exercise" in intake.requested_outcomes:
                    assignments.append(RoutingAssignment(need_id=need.id, worker="physio", artifact_ids=[], reason="Exercise was requested after review."))
            elif need.evidence_type == "unknown":
                unresolved.append(need.id)
        routing = RoutingResult(
            assignments=assignments,
            synthesis_need_ids=[n.id for n in intake.information_needs if n.evidence_type in ("combined", "general")],
            unresolved_need_ids=unresolved,
        )
        for assignment in assignments:
            await self._emit(state, "02", "routing", "routing.assigned", "completed",
                             f"{assignment.need_id} assigned to {assignment.worker}.",
                             need_ids=[assignment.need_id], artifact_ids=assignment.artifact_ids,
                             destination_worker=assignment.worker,
                             payload={"reason": assignment.reason})
        return {"routing": routing.model_dump(mode="json")}

    def _artifact_text(self, request: RunRequest, artifact_id: str) -> str:
        artifact = next(item for item in request.artifacts if item.artifact_id == artifact_id)
        path = Path(artifact.storage_reference or "")
        if not path.is_absolute():
            path = self.artifact_root / path
        resolved = path.resolve()
        if self.artifact_root not in resolved.parents and resolved != self.artifact_root:
            raise ValueError("artifact path is outside the configured root")
        if resolved.suffix.lower() == ".json":
            return json.dumps(json.loads(resolved.read_text(encoding="utf-8")), indent=2)
        return resolved.read_text(encoding="utf-8")

    async def _run_worker(self, state: WorkflowState, worker: str,
                          assignments: list[RoutingAssignment]) -> EvidencePackage:
        task_id = f"task-{worker}"
        await self._emit(state, "03", worker, "worker.started", "running",
                         f"{worker.title()} specialist started.", task_id=task_id,
                         need_ids=[a.need_id for a in assignments], source_worker=worker)
        request = RunRequest.model_validate(state["request"])
        observations: list[Observation] = []
        limitations: list[str] = []
        artifact_ids = sorted({item for a in assignments for item in a.artifact_ids})
        artifact_texts: dict[str, str] = {}
        artifact_images: dict[str, tuple[str, bytes]] = {}
        image_formats = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg",
                         ".gif": "gif", ".webp": "webp"}
        for index, artifact_id in enumerate(artifact_ids, start=1):
            artifact = next(item for item in request.artifacts if item.artifact_id == artifact_id)
            path = Path(artifact.storage_reference or "")
            if not path.is_absolute():
                path = self.artifact_root / path
            resolved = path.resolve()
            if self.artifact_root not in resolved.parents and resolved != self.artifact_root:
                raise ValueError("artifact path is outside the configured root")
            image_format = image_formats.get(resolved.suffix.lower())
            if image_format:
                artifact_images[artifact_id] = (image_format, resolved.read_bytes())
                text = f"Image upload {artifact.filename}; visual findings require multimodal model review."
            else:
                text = self._artifact_text(request, artifact_id)
                artifact_texts[artifact_id] = text
            observations.append(Observation(
                id=f"obs-{worker}-{index}", description=" ".join(text.split())[:1600],
                origin="extracted_from_report", artifact_id=artifact_id,
                source_locator="supplied artifact",
                uncertainty="Synthetic/demo content; preserve the source attribution.",
            ))
        query = " ".join(a.need_id + " " + next(
            n["question"] for n in state["intake"]["information_needs"] if n["id"] == a.need_id
        ) for a in assignments)
        model_mode = "deterministic_harness"
        if self.models and (artifact_texts or artifact_images):
            model_result = await self.models.specialist(worker, query, artifact_texts,
                                                         images=artifact_images)
            allowed_artifacts = set(artifact_ids)
            if len(allowed_artifacts) == 1:
                only_artifact = next(iter(allowed_artifacts))
                model_result = model_result.model_copy(update={
                    "observations": [item.model_copy(update={"artifact_id": only_artifact})
                                     for item in model_result.observations]
                })
            if any(item.artifact_id not in allowed_artifacts for item in model_result.observations):
                raise ValueError(f"{worker} model referenced an artifact outside its assignment")
            observations = [Observation(
                id=f"obs-{worker}-{index}", description=item.description,
                origin="extracted_from_report", artifact_id=item.artifact_id,
                source_locator=item.source_locator, uncertainty=item.uncertainty,
            ) for index, item in enumerate(model_result.observations, start=1)]
            limitations.extend(model_result.limitations)
            query = model_result.retrieval_query
            model_mode = "bedrock_validated_json"
        await self._emit(state, "03", worker, "retrieval.started", "running",
                         f"Retrieving references for {worker}.", task_id=task_id,
                         need_ids=[a.need_id for a in assignments], payload={"query": query})
        hits = await self.knowledge.search(query, [worker], limit=5)
        evidence = to_evidence_items(task_id, hits)
        await self._emit(state, "03", worker, "retrieval.completed", "completed",
                         f"Retrieved {len(evidence)} source passage(s).", task_id=task_id,
                         evidence_ids=[item.id for item in evidence],
                         payload={"candidate_count": len(evidence), "method": type(self.knowledge).__name__})
        if not evidence:
            limitations.append("No matching reference passage was available in the current snapshot.")
        package = EvidencePackage(
            package_id=f"pkg-{state['run_id']}-{worker}-v1", run_id=state["run_id"],
            task_id=task_id, worker=worker, status="succeeded" if observations else "partial",
            observations=observations, evidence_items=evidence, limitations=limitations,
            missing_information=[] if observations else ["No usable artifact was supplied."],
            retrieval_status="complete" if evidence else "degraded",
            retrieval_trace={"queries": [query], "round": 0, "budget_exhausted": False},
            provenance={"specialist_model": os.getenv(f"BEDROCK_{worker.upper()}_MODEL_ID", "us.amazon.nova-pro-v1:0"),
                        "mode": model_mode, "corpus_version": state["request"].get("knowledge_snapshot", {}).get("corpus_version", "local-demo")},
        )
        await self._emit(state, "03", worker, "worker.completed", package.status,
                         f"{worker.title()} specialist produced a validated evidence package.",
                         task_id=task_id, need_ids=[a.need_id for a in assignments],
                         artifact_ids=artifact_ids, evidence_ids=[item.id for item in evidence],
                         source_worker=worker)
        return package

    async def _diagnostics(self, state: WorkflowState) -> dict[str, Any]:
        self._check_cancelled(state)
        routing = RoutingResult.model_validate(state["routing"])
        grouped: dict[str, list[RoutingAssignment]] = {}
        for assignment in routing.assignments:
            if assignment.worker in DIAGNOSTIC_WORKERS:
                grouped.setdefault(assignment.worker, []).append(assignment)
        packages = await asyncio.gather(*[
            self._run_worker(state, worker, assignments)
            for worker, assignments in grouped.items()
        ]) if grouped else []
        return {"evidence_packages": {package.package_id: package.model_dump(mode="json") for package in packages}}

    async def _doctor(self, state: WorkflowState) -> dict[str, Any]:
        self._check_cancelled(state)
        await self._emit(state, "04", "doctor", "doctor_review.started", "running",
                         "Doctor review started over the available evidence packages.")
        packages = [EvidencePackage.model_validate(item) for item in state.get("evidence_packages", {}).values()]
        claims: list[ReviewedClaim] = []
        for index, package in enumerate(packages, start=1):
            if not package.observations:
                continue
            claims.append(ReviewedClaim(
                claim_id=f"claim-{index}",
                statement=f"The {package.worker} package contains report-derived observations that require clinical correlation.",
                observation_ids=[item.id for item in package.observations],
                evidence_ids=[item.id for item in package.evidence_items],
                applicability="Educational explanation of the supplied synthetic report.",
                uncertainty="The prototype does not confirm a diagnosis.",
                limitations=package.limitations,
            ))
        patient_text = state["request"].get("patient_text", "").lower()
        red_flags: list[RedFlag] = []
        if "short of breath" in patient_text or "shortness of breath" in patient_text or "swelling" in patient_text:
            red_flags.append(RedFlag(
                id="flag-symptoms-human-review",
                description="New shortness of breath or swelling needs prompt assessment by a qualified clinician.",
            ))
        decision = "human_review" if red_flags else "proceed"
        review = DoctorReview(
            run_id=state["run_id"], review_id=f"review-{state['run_id']}", status="complete" if packages else "partial",
            combined_summary="Available specialist packages were reviewed together; source attribution and limitations are preserved.",
            supported_explanations=claims,
            need_coverage=[{"need_id": need["id"], "state": "partial" if not claims else "supported",
                            "claim_ids": [claim.claim_id for claim in claims]}
                           for need in state["intake"]["information_needs"]],
            red_flags=red_flags, decision=decision,
            decision_reason="Unresolved symptoms require human review before care guidance." if red_flags else "No review-blocking flag was found in the supplied context.",
        )
        await self._emit(state, "04", "doctor", "doctor.review_completed", "completed",
                         f"Doctor review decision: {decision}.",
                         evidence_ids=[e for claim in claims for e in claim.evidence_ids],
                         review_version=review.review_version,
                         payload={"decision": decision, "reason": review.decision_reason})
        if red_flags:
            await self._emit(state, "04", "doctor", "review.required", "paused",
                             "Care guidance paused pending human review.",
                             review_version=review.review_version, visibility="patient",
                             payload={"red_flags": [flag.model_dump() for flag in red_flags]})
        return {"doctor_review": review.model_dump(mode="json"),
                "runtime_status": "needs_human_review" if red_flags else "running"}

    async def _guidance(self, state: WorkflowState) -> dict[str, Any]:
        self._check_cancelled(state)
        review = DoctorReview.model_validate(state["doctor_review"])
        requested = set(state["intake"].get("requested_outcomes", []))
        selected = [name for name, outcome in (("nutrition", "nutrition"), ("physio", "exercise")) if outcome in requested]
        if review.decision != "proceed" or not selected:
            bundle = {
                "bundle_id": f"bundle-{state['run_id']}", "bundle_version": 1,
                "review_id": review.review_id, "review_version": review.review_version,
                "explanations": [claim.model_dump(mode="json") for claim in review.supported_explanations],
                "guidance": [], "withheld_reasons": ["Guidance withheld pending human review."] if selected else [],
                "missing_information": review.missing_patient_information,
                "red_flags": [flag.model_dump(mode="json") for flag in review.red_flags],
            }
            return {"reviewed_content_bundle": bundle}
        await self._emit(state, "04", "guidance", "guidance.started", "running",
                         f"Requested guidance workers started: {', '.join(selected)}.",
                         payload={"workers": selected})
        # The first slice withholds personalized guidance until the Nova prompt and support checker land.
        bundle = {
            "bundle_id": f"bundle-{state['run_id']}", "bundle_version": 1,
            "review_id": review.review_id, "review_version": review.review_version,
            "explanations": [claim.model_dump(mode="json") for claim in review.supported_explanations],
            "guidance": [], "withheld_reasons": ["Specialist guidance model integration is not enabled in this slice."],
            "missing_information": review.missing_patient_information,
            "red_flags": [flag.model_dump(mode="json") for flag in review.red_flags],
        }
        await self._emit(state, "04", "guidance", "guidance.checked", "partial",
                         "No unchecked personalized guidance was released.")
        return {"reviewed_content_bundle": bundle, "runtime_status": "partial"}

    async def _generate(self, state: WorkflowState) -> dict[str, Any]:
        self._check_cancelled(state)
        await self._emit(state, "05", "generation", "answer.started", "running",
                         "Building validated patient-facing sections.")
        bundle = state["reviewed_content_bundle"]
        explanations = bundle.get("explanations", [])
        sections = [AnswerSection(
            section_id="section-reviewed", order=1, title="What was reviewed",
            text=f"The workflow reviewed {len(state.get('evidence_packages', {}))} specialist evidence package(s).",
            bundle_id=bundle["bundle_id"], rendering_method="template",
        )]
        if explanations:
            sections.append(AnswerSection(
                section_id="section-explanation", order=2, title="Supported explanation",
                text=" ".join(item["statement"] for item in explanations),
                reviewed_claim_ids=[item["claim_id"] for item in explanations],
                evidence_ids=sorted({e for item in explanations for e in item.get("evidence_ids", [])}),
                bundle_id=bundle["bundle_id"], rendering_method="template",
            ))
        limitations = list(bundle.get("withheld_reasons", []))
        if bundle.get("red_flags"):
            limitations.extend(item["description"] for item in bundle["red_flags"])
        limitations.append("This prototype is educational and does not provide medical advice or a diagnosis.")
        sections.append(AnswerSection(
            section_id="section-limits", order=3, title="Uncertainty and next steps",
            text=" ".join(limitations), bundle_id=bundle["bundle_id"], rendering_method="template",
        ))
        for section in sections:
            await self._emit(state, "05", "generation", "answer.section", "completed",
                             section.title, evidence_ids=section.evidence_ids,
                             payload=section.model_dump(mode="json"), visibility="patient")
        final_response = "\n\n".join(f"## {section.title}\n{section.text}" for section in sections)
        await self._emit(state, "05", "generation", "answer.completed", "completed",
                         "Validated answer sections are ready.", visibility="patient")
        status = state.get("runtime_status", "running")
        if status == "running":
            status = "completed"
        return {"answer_sections": [section.model_dump(mode="json") for section in sections],
                "final_response": final_response, "runtime_status": status}

