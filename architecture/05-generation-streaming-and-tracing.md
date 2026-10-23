# Layer 5 — Generation, live streaming, and tracing

**Status:** Adopted architecture, 2026-10-23; implementation remains for the harness.  
**Model:** Configurable Sonnet 4.6 via Bedrock.  
**Scope:** Final presentation and cross-layer observability for Layers 00–5.

The README requires visible handoffs and an audit trail. Live streaming is the project owner's additional implementation requirement. Show real execution, evidence and concise decision explanations, not hidden chain-of-thought or simulated progress.

## Presentation

Show two outputs: a live workflow timeline and an understandable patient answer. Nutrition/physio execute with their scoped knowledge after Doctor review; their outputs pass Layer 4's support gate before final generation. Layer 5 introduces no new retrieval or clinical conclusions.

| Event | Visible information |
| --- | --- |
| run.started | Request accepted and run ID |
| intake.started/decomposed | Organizing request, then validated subquestions and artifact IDs |
| routing.assigned | Exact question, destination worker and brief routing reason |
| worker.started | Distinct parallel worker status cards |
| retrieval.started/completed | Query, method, corpus version and candidate counts |
| graph.expanded | Actual depth and supported paths found |
| rerank.completed | Selected evidence count and source links |
| evaluation.started/passed/insufficient | Need/claim IDs, support verdict, missing evidence and next action |
| recovery.requested/granted/denied | Specific gap, strategy and remaining budget |
| recovery.queries_generated | Paraphrase, step-back query and clearly labeled HyDE search aid |
| recovery.completed | Additional real evidence and remaining gaps |
| worker.completed/failed/timed_out | Status, limitation and next action |
| doctor.review_completed | Proceed, clarify, retrieve more or human review with short reason |
| guidance.started/checked | Nutrition/physio work and support-check outcome |
| review.required | Guidance paused pending human review |
| answer.started/section/completed | Reviewed answer sections and citations |
| run.completed/partial/failed/cancelled/paused | Explicit outcome; pauses include reason and resumability |

An evaluation pass means support for the stated explanatory scope, not clinical clearance. Rerank scores alone cannot produce a pass. No fake percentages or success labels before checks finish. Separate parallel cards prevent display order from implying dependency order.

## LangGraph and Bedrock streaming

Use a backend-owned run with a server-sent events (SSE) subscription. Start/cancel/review are separate API requests. Disconnect does not automatically rerun, approve or cancel the workflow.

Pin LangGraph's version and normalize its stream API through an adapter. Updates/custom events expose progress, including inside long-running tools. Messages/token events must be filtered by producing node; never forward raw state snapshots, debug events, every model message or provider reasoning blocks. Newer typed event APIs may replace the adapter without changing our event envelope. [LangGraph streaming](https://docs.langchain.com/oss/python/langgraph/streaming)

Decomposition and routing become visible after structured validation. Partial JSON cannot be displayed as a confirmed plan or dispatched. Non-streaming tools still emit truthful started/completed events.

Use Bedrock ConverseStream for supported final-generation models, verifying streaming support and bedrock:InvokeModelWithResponseStream permission during setup. [Bedrock streaming API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html)

## Durable event envelope

```text
WorkflowEvent
  schema_version, event_id, run_id, sequence
  trace_id, span_id, parent_span_id?
  timestamp, layer, node, task_id?, need_ids[]
  type, status, summary
  source_worker?, destination_worker?
  artifact_ids[], evidence_ids[], review_version?
  retrieval_round?, strategy?
  payload                     # allowlisted by event type
  visibility: patient | demo_detail | operator
```

One backend sink serializes SQLite writes, assigns a monotonically increasing sequence per run, and persists before publishing. Unique run/event IDs deduplicate repeat delivery. Send sequence as SSE id; reconnect replays records after the last received sequence and then resumes live delivery without a gap. Task/parent span IDs preserve causal relationships across parallel work.

Heartbeats are connection signals, not fake progress. Slow clients may coalesce token deltas but cannot lose durable status, evidence, review and terminal events. Large outputs use artifact references.

Checkpoints and events are separate records. Reconcile crashes between checkpointing and event persistence through stable task/event IDs; do not promise exactly-once model calls. Instrument node/tool wrappers for persistence and streaming. Reducers remain pure and never write logs or emit network events.

If the durable event sink fails, surface degraded observability and stop dispatching new work until recoverable. Optional external exporter failure need not stop execution when the local journal is healthy.

## Developer tracing

Create a root trace per run and child spans for intake, routing, specialists, every model/tool call, keyword/vector search, graph traversal, reranking, evaluation, recovery, Doctor review, guidance checks and generation.

Record task/need IDs, parent span IDs, timestamps/duration, model/profile, prompt/schema version, sanitized input/output references, provider request ID, actual returned token usage, corpus/graph versions, queries/filters, selected evidence IDs, graph depth, decisions, recovery counts, errors and final status. Unknown usage stays unknown; optional cost estimates require a dated price configuration.

Do not log credentials, signed URLs or hidden reasoning. Store raw content only in controlled artifact storage; traces use references. Label HyDE generated_search_aid and exclude it from accepted evidence.

Baseline storage: SQLite event/span journal plus JSON trace export. Optional OpenTelemetry-compatible export, AWS observability or LangSmith can be added after checking account/data boundaries. External tracing SaaS is not required. Bedrock Agents tracing must not be assumed to instrument this custom LangGraph workflow automatically.

## Bounded retrieval recovery

| Problem | Action |
| --- | --- |
| Specific knowledge gap or vocabulary mismatch | Request remaining run-wide retrieval grant |
| Missing patient fact | Clarification or explicit limitation |
| Material source conflict or red flag | Layer 4 review gate |
| Timeout, permissions error or service outage | Visible technical failure/degraded result; not query rewriting |
| Invalid model JSON | Existing deterministic fallback; no unlimited repair |

When granted, one structured Sonnet call creates one targeted paraphrase, one broader step-back question and one short hypothetical reference paragraph (maximum 150 words). Preserve the original need/query. Original plus paraphrase provides multi-query coverage. Validate intent and IDs; skip invalid variants with a visible reason rather than repairing repeatedly.

Embed the hypothetical paragraph with Titan for vector search only. It is general reference-style text, not an invented patient report. Keyword/graph branches use validated questions/concepts, never hypothetical findings as facts. Merge genuine retrieved passages and paths, deduplicate, rerank once, expand parents and reassess. All strategies share the one recovery grant; they are not three independent loops.

Keep Layer 3's candidate/context/time caps. Show only strategies actually executed. If evidence remains insufficient, qualify the answer, clarify or escalate. No retries until a desired diagnosis appears.

## Final generation

Input is Layer 4's versioned ReviewedContentBundle, original questions, allowed citations and runtime status. One call creates sections for what was reviewed, supported explanations, requested guidance, uncertainty/missing information and discussion/next steps. Every substantive statement links to reviewed claim IDs; no new diagnosis, prescription or recommendation.

Stream workflow events throughout. Buffer each answer section until its structure, citation IDs, required uncertainty and permitted scope validate, then emit answer.section. This is incremental section delivery, not unfiltered token streaming. Raw final-draft tokens are disabled in the patient UI; internal token streaming can measure latency.

Basic validation cannot prove semantic faithfulness: evaluate generated prose against fixture cases and constrain it to reviewed claims. If a section fails checks, withhold it and use a template rendering of supported content rather than launching a new reasoning loop. Withheld care guidance must never be streamed early and retracted later.

Review/clarification outcomes show permitted explanations and next action. A mid-generation failure leaves an explicitly partial answer; do not emit completed after failure.

## Demo sequence and checks

Illustration only; derive actual messages from runtime events:

```text
Organized request into 4 questions.
Q1 -> Lab; Q2 -> Radiology; Q3 -> ECG.
Three specialists started.
Lab: evidence supports this explanation; continuing.
Radiology: reference support is incomplete.
Recovery granted: paraphrase + step-back + HyDE search aid.
Additional real sources retrieved and reranked.
Doctor: enough support for a qualified explanation.
Nutrition/Physio: retrieving their scoped references.
Guidance checked; reviewed answer sections streaming.
Run completed with stated limitations.
```

Use a labeled retrieval-gap fixture to demonstrate recovery reproducibly. Do not disguise a replay or staged failure as live execution.

Verify visible validated decomposition; exact question-to-worker mapping; distinct parallel status; causal evaluation/recovery events; no HyDE as evidence; one recovery grant; correct technical-failure paths; red-flag pauses; reconnect without duplicate cards; linked trace/source/model records; withheld content never emitted; cancellation/failure never reported as success.

Implementation work: event schemas and sink, SQLite event/span tables, LangGraph adapter, SSE endpoint, UI timeline, tool/model instrumentation, recovery generator, section validators and renderer.

## State schema after Layer 05

Layer 05 reads the reviewed bundle and adds presentation outputs. Observability starts at run creation, not only after generation; its durable records capture every preceding layer.

| State field | Type | Meaning / write policy |
| --- | --- | --- |
| `answer_sections` | `list[ValidatedAnswerSection]` | Ordered sections that passed structure, citation and permitted-scope checks. Each has `section_id`, order, text, reviewed claim/evidence IDs, bundle ID/version and rendering method (`model` or `template`). One generation/validation pipeline writer; no parallel reducer. |
| `generation_status` | `not_started / generating / completed / partial / failed / cancelled` | Presentation status, distinct from the overall clinical-review/workflow outcome. Generation pipeline owns this field; an answer can finish rendering while the run still needs human review. |
| `final_response` | `str or null` | Rendered text assembled from validated sections only. Null before a deliverable exists; partial text remains explicitly partial. Single generation pipeline writer. |
| `handoff_events` | reducer map | Adds answer-started/section/completed or failed events and references to durable records. Uses the existing immutable ID reducer; not a separate competing event log. |
| `observability.trace_id` | `str` | Root trace identifier assigned at run start; all model/tool spans link back to it. |
| `observability.event_journal_ref` | reference | Durable per-run event stream in SQLite. Backend event sink owns persistence and sequence allocation. |
| `observability.span_journal_ref` | reference | Detailed model/tool spans with timings, usage, versions, source IDs and sanitized errors. Full span lists do not belong in LLM context. |
| `observability.health` | `healthy / degraded / unavailable` | Journal service health, updated through its serialized control path; dispatch stops on durable-sink failure under the policy above. |
| `observability.trace_export_ref` | optional reference | Completed JSON trace export, if available. No signed URLs or credentials in state. |
| `runtime_status` | existing runtime field | Orchestrator commits the actual terminal outcome. Generating readable text never clears `needs_human_review` or `needs_clarification`. |

**Persist beside state, not inside every checkpoint:** complete `WorkflowEvent` records, tool/model spans and large output artifacts. `sequence` belongs to the durable event journal; SSE reconnect cursors belong to each client connection. Neither is a parallel-worker-owned LangGraph counter. Checkpoints hold compact references and outputs; replay does not imply exactly-once provider calls.

**Keep private/local:** draft tokens, invalid sections and hidden reasoning are never appended to `answer_sections` or streamed to patients. Only emit `answer.section` after validation and durable event persistence. A generation failure must not emit `answer.completed`; retain any already validated sections with an explicit partial outcome.

**Final state:** input + pinned knowledge snapshot + validated routing/tasks + versioned evidence + Doctor review + checked bundle + validated answer + event/trace references. It is an auditable record of this prototype run, not a clinical record or clinician approval.
