# AWS Agentic AI Hackathon (AUS20) — Track 1: Caregivers Challenge

Full context lives in `aws_hackathon_context_briefing.md` (read it if you need the verbatim
track text, logistics email, or resource list). This file is the short version.
`aws_hackathon_winning_tactics_judge_playbook.md` is the user's own research on what AWS judges
reward (demo structure, presets, provenance tags, Guardrails MASK vs BLOCK). It is advice, not
organizer-confirmed rules; model names in it may be outdated, so check what Bedrock actually offers.

## Event
- Fri 2026-10-23. Build window 10:00–16:00, 3-minute live demo to AWS judges at 16:00.
- Teams of 3–5 form at 9:30. The Workshop Studio event dashboard offers browser VS Code or a
  Kiro Ubuntu desktop (per the organizers' email). The user's understanding is that AWS also
  provides temporary credentials that can be exported to the local machine, so local development
  with Claude Code is the plan. This is the user's assumption, not organizer-confirmed text; if
  the export doesn't work, fall back to pasting code into the Workshop environment (helpers are stdlib-only).
- Synthetic/public data only. No real PHI. This is a prototype, not medical advice — the demo
  must say so explicitly.

## Hard requirements (judged)
- Demo: one patient scenario, at least two visible specialist handoffs, a clear patient-facing result.
- Visible handoffs: show which persona reviewed which input and what it passed on. No opaque single-prompt chatbot.
- Provenance + uncertainty: advice ties back to specific findings; state what is uncertain.
- Explicit failure handling: missing/corrupt/unreadable data is flagged, never guessed. Ask for clinical re-evaluation.
- Red-flag intercept: critical values halt unsupervised recommendations and require human confirmation.

## Working agreement
- The user wants to stay in the loop and must understand all code well enough to present it to judges.
  BEFORE writing or editing any code, explain what it will do, granularly: each function, its inputs
  and outputs, why it exists, and what notable lines do. Wait for approval, then write. A high-level
  summary after the fact is not sufficient. Work in small steps; do not build large amounts of code unprompted.
- Do NOT lock in personas, data schemas, or UI before the team agrees at 9:30. The persona count
  and roles (Lab Analyst, Radiologist, Doctor, Nutritionist, Physio) are suggestions, not rules.
- Keep code modular and framework-agnostic (Strands Agents SDK, plain boto3 Converse, or
  AgentCore are all still open). Prefer the standard library for helpers so they paste anywhere.
- Safety gates and missing-data handling are first-class and deterministic (plain Python, not prompts).
- Log every agent/tool input, output and reasoning step somewhere central so handoffs can be rendered in any UI.

## Ideas to propose to the team (not decisions)
Strands Agents SDK or boto3 Converse; Streamlit UI with an audit view and a caregiver view and
preset scenarios (one happy path, one red-flag/missing-data path); Bedrock Guardrails with PII
set to MASK not BLOCK; cheap model for extraction, stronger model for synthesis; prompt caching.

## Helpers prepared in advance (`core/`, stdlib only)
- `core/safety.py` — deterministic red-flag + missing-value check. `DEFAULT_RULES` holds one TEMPLATE rule (hypoxia); add the real rules once the team picks its scenario and data.
- `core/failure.py` — `guarded()` turns an exception into a flagged gap instead of a crash.

## Frontend (`frontend/`, the user's task; a teammate owns the LangGraph backend/harness)
- Vite + React 19 + TypeScript + Tailwind 4. Commands: `npm test` (vitest), `npx tsc -b`, `npx oxlint`, `npm run build`, `npm run preview -- --port 4173`. Run these via the project scripts, not bare `npx vite` (that once picked up a wrong copy). Use `npm ci` on a fresh machine.
- Customer-first: a caregiver reads a plain-language summary; the "How we got this" panel holds the audit trail. Model/token details are hidden behind a "Show technical details" switch (off by default). Do not surface tokens or model names by default.
- Data flow: an `EventSourceLike` (replay now, live SSE later) -> `ingestRaw` -> `RunState` (a pure fold of events sorted by `sequence`) -> `buildStripModel` / `buildSummaryModel` -> components. Only `src/mock/` and `src/source/replaySource.ts` are mock; the live SSE client is NOT written yet.
- Event shape follows `architecture/05-generation-streaming-and-tracing.md` in the team repo (github.com/DanielZ0217/AWS-Hackathon). Payload shapes are ASSUMPTIONS, isolated in `src/state/payloadAdapters.ts`. Still unconfirmed with the backend teammate: timestamp/status formats, per-event payloads, whether model-call spans are fetchable, SSE endpoint/event naming, run-control endpoints, how presets are passed. Customer-facing wording in event `summary` fields is shown verbatim, so the backend must write plain-language summaries.
- Design: `.claude/skills/frontend-design` (Anthropic's official skill, installed at project level). Chart-paper look, tokens in `src/index.css`, Atkinson Hyperlegible + Literata self-hosted. Red (`--color-alarm`) is reserved for red flags only. Motion only answers real events; respects reduced-motion. No review-confirm/resume action exists because the backend has not defined one.
