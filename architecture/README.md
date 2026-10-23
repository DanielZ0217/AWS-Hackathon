# Architecture and hackathon build sequence

**Updated:** 2026-10-23. Target build session: 2026-10-24.

## Adopted architecture

0. [Layer 00: ingestion and knowledge preparation](00-ingestion-and-knowledge-preparation.md) — exact starter sources, separate reference/patient/evaluation lanes, parsing/OCR, parent-child indexing, graph extraction, and publication checks. [Source manifest](00-ingestion-sources.json).
1. [Layer 1: patient intake and query planning](01-patient-intake-and-query-planning.md) — text/image intake, artifact classification, bounded decomposition, and evidence references.
2. [Layer 2: routing and orchestration](02-planner-orchestrator-and-routing.md) — validated routing, parallel specialists, synthesis, review gates, and patient-facing assembly.
3. [Layer 3: specialist analysis and evidence retrieval](03-specialist-analysis-and-evidence-retrieval.md) — hybrid parent-child retrieval, GraphRAG up to five hops, RRF fusion and reranking, one bounded recovery round, common evidence packages, and optional ontology checks.

4. [Layer 4: Doctor synthesis and evidence review](04-doctor-synthesis-and-evidence-review.md) — claim support, contradictions, bounded recovery, nutrition/physio knowledge scopes, and guidance checks.

These revised documents supersede the earlier Layer 1 and Layer 2 notes. Sonnet 4.6 is the initial configurable model for decomposition and routing; five workers are lab, radiology, ECG, nutrition, and physio, with a separate Doctor synthesis node.

5. [Layer 5: generation, streaming, and tracing](05-generation-streaming-and-tracing.md) — live decomposition/routing/evaluation/recovery timeline, durable traces, scoped recovery strategies, and reviewed answer streaming.

## Reading the state schema

Graph ingestion decision: [Layer 00](00-ingestion-and-knowledge-preparation.md#llm-concept-and-relationship-extraction-into-neptune) now specifies GPT-6 Sol as the preferred configurable concept/relationship extractor, terminology mapping, evidence/causal-claim review and controlled publication into Neptune Database. Sonnet is a configured extraction fallback; runtime specialist models remain as documented. Neptune Database is the selected managed graph target, with a local export adapter for labeled fallback. Account access and deployment remain unverified. Earlier PowerPoint/draw.io exports predate this model/backend revision.

Related research: [Existing medical ontologies and terminology resources](ontology-research.md) maps established resources to our agents, records source/licensing notes, and proposes a bounded integration and validation plan.

Each layer document ends with **State schema after Layer 00–05**, listing key fields, their meanings and write ownership. These are documentation contracts for the upcoming harness, not an implemented persistence schema.

| Layer | Main state contribution |
| --- | --- |
| 00 | Offline ingestion records; compact pinned `knowledge_snapshot` for each patient run. |
| 01 | `run_id`, `original_request`, `artifact_manifest`, validated `intake`. |
| 02 | `routing`, `tasks`, `limits`, `runtime_status`, `recovery_grant`, shared reducer maps and observability initialization. |
| 03 | Versioned `evidence_packages`, flags, recovery requests and handoff events; temporary retrieval work stays local. |
| 04 | `doctor_review`, review history, scoped guidance contexts, `guidance_check`, `reviewed_content_bundle`. |
| 05 | `answer_sections`, `generation_status`, `final_response` and durable event/trace references. |

Layer 02 contains the illustrative combined `WorkflowState` declaration and reducer policy. Nested table rows describe fields inside an existing object, not additional independent copies. Single-writer fields are updated only by their scheduled owner; parallel evidence/event contributions merge by immutable ID.

## Architecture work still needed

- Finalize specialist prompts and evaluate the candidate model/tool adapters against Layer 3's common input/output contract.
- Implement Layer 5's stream adapter, event/trace journal, timeline and reviewed-section renderer in the harness.
- Prepare Layer 00's proposed synthetic demo-001 fixture and review its consistency; optional public image/ECG record IDs still need selection.
- Verify storage and Bedrock access/Region; build the curated corpus and source-backed demo graph required by Layer 3.

## Harness build sequence for tomorrow

1. Define shared schemas for artifacts, intake results, routing proposals, worker results, run state, and handoff events.
2. Build a registry of mock workers with deterministic synthetic results, including failure and red-flag fixtures.
3. Wire the Layer 2 execution graph and event timeline. Demonstrate parallel diagnostics, synthesis, downstream workers, and terminal outcomes before connecting real model calls.
4. Add text/image intake, local artifact storage behind a storage interface, and the upload category selector.
5. Connect Bedrock decomposition and routing through configurable adapters. Verify model access and structured-output behavior in the selected Region.
6. Replace mock specialists individually with selected model/tool adapters. Clearly label any remaining mock results in the demo.
   Add shared passage/graph retrieval and reranking, and verify claim-to-source links using the chosen patient scenario. Ontology validation remains optional.
7. Add the patient explanation view and review-required state. Implement explicit review/resume only if the demo needs it.
8. Rehearse one complete synthetic case and the failure, unknown-image, and red-flag paths.

The harness should provide one callable workflow entry point, shared state, a worker registry, artifact resolution, model adapters, configurable limits, and visible event recording. Keep it in one runtime initially.

## Definition of demo-ready

One synthetic/public patient scenario accepts text and images, shows at least two real specialist handoffs, and produces one understandable explanation with evidence references and limitations. Missing evidence or worker failures are visible; flagged care guidance pauses for human review. The prototype boundary is visible.

This folder specifies the architecture and build sequence. The executable harness has not yet been implemented.
