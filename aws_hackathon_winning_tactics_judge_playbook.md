# AWS Hackathon Winning Tactics & Evaluator Playbook

This document captures architectural edges, evaluator psychology, and demonstration tactics specifically calibrated for AWS Solutions Architects (SAs) and senior engineering judges. Use these principles when designing features, writing agent logic, and preparing the demo.

---

## 1. Evaluator Psychology: What AWS SAs Care About (and What Bores Them)

* **The "Wrapper App" Fatigue:** Judges evaluate dozens of projects. They immediately tune out standard single-prompt chatbots wrapped in a generic UI.
* **What Hooks an AWS SA:**
  * **Visible Multi-Agent Orchestration:** Clear evidence that independent personas or tools executed distinct sub-tasks, passed structured data, and operated on shared state.
  * **Deterministic Logic over Blind Faith:** Pure LLM prompt engineering is considered fragile. Implementing explicit code-level checks (e.g., Python `@tool` functions evaluating strict mathematical or physiological thresholds) proves production readiness.
  * **AWS Well-Architected Alignment:** Subtle signals that reflect core AWS philosophies: **Customer Obsession** (solving the end-user's actual UX problem), **Frugality** (token and compute awareness), and **Operational Excellence** (monitoring, auditability, error recovery).

---

## 2. Technical Implementation Edges

### A. The "Failure as a Feature" Edge (Handling Edge Cases)
* **The Common Mistake:** Most teams only build a "happy path" and panic when data is imperfect or an agent encounters missing values.
* **The High-Scoring Alternative:** Make graceful failure an intentional showcase.
  * If a synthetic lab value lacks standard units or a medication lacks dosage instructions, the agent **must explicitly halt that specific output, log the ambiguity, and output an alert: "Action paused — requires clinician clarification."**
  * Presenting this during judging demonstrates robust HCLS compliance and hallucination prevention.

### B. Bedrock Guardrails Strategy: `MASK` vs. `BLOCK`
* If Bedrock Guardrails are integrated:
  * **Sensitive Data (PII/PHI):** Always set action to **`MASK`** (or redact), **never `BLOCK`**. Setting PII to `BLOCK` causes the model API to throw a 400-level exception if it encounters synthetic names, hospital room numbers, or clinician signatures, terminating the entire agent execution. `MASK` allows downstream processing to continue cleanly.
  * **Safety/Toxicity/Misconduct:** Keep `BLOCK` reserved strictly for harmful instructions or unauthorized medical directives.

### C. Demonstrating AWS "Frugality" (Multi-Model Routing & Prompt Caching)
* Mentioning or implementing basic multi-model routing scores points for cloud design:
  * Route fast parsing and data extraction to lightweight, low-latency models (e.g., **Amazon Nova Lite** or **Claude 3.5 Haiku**).
  * Reserve frontier models (e.g., **Claude 3.5/3.7 Sonnet** or **Nova Pro**) for clinical synthesis and caregiver translation.
* If discussing Bedrock API calls with mentors, mention **Bedrock Prompt Caching** for static persona system prompts and tool schemas to highlight token efficiency and latency reduction.

### D. Auditability & Data Provenance
* Healthcare agents cannot be black boxes. Ensure every downstream recommendation attaches a small metadata tag referencing its source:
  * Example: `Source: Metabolic Panel (Sodium: 132 mEq/L)` or `Confidence: High | Extracted via LabAnalyst`.
* Displaying this provenance in the UI directly answers the official rubric requirement for transparency.

---

## 3. The 3-Minute Demo Playbook

Judges have strict stopwatches. At 3 minutes, they will cut you off mid-sentence. Structure the demo into four crisp blocks:

```
[0:00 - 0:30] The Customer Problem & Input Multimodal Data
[0:30 - 1:45] The Live Run: Visible Specialist Handoffs (The "Baton Pass")
[1:45 - 2:20] The Red-Flag / Safety Intercept (The Proof of Control)
[2:20 - 3:00] The Patient-Facing Output & Architectural Summary
```

### Key Demo Mechanics:
1. **Never Live-Type on Stage:**
   * Do not copy-paste complex medical JSON or type prompt queries live. Network latency or typos can derail the presentation.
   * Use a UI dropdown with pre-configured synthetic profiles:
     * **Preset 1 (Standard Case):** Clean multimodal run demonstrating multi-agent handoffs.
     * **Preset 2 (Safety / Edge Case):** Triggers a red-flag value or missing data to show deterministic safety stops in action.
2. **Dual-View UI (The Visual Contrast):**
   * **Clinician / Audit Trace:** Show an expandable view with raw metrics, agent tool logs, and handoff timestamps.
   * **Caregiver / Patient Card:** Show clean, scannable cards written in accessible, 6th-grade language ("What to do today", "Things to watch out for", "Questions for your doctor").
   * This immediately demonstrates turning technical signals into human guidance.
3. **The 30-Second Screen Recording Backup:**
   * At 3:30 PM, run a screen recorder (QuickTime or OBS) capturing a clean run of both demo presets.
   * If venue Wi-Fi becomes congested during final judging, switch instantly to the high-resolution local video without fumbling.

---

## 4. Engaging Mentors & SAs During Build Time

Solutions Architects walk the floor throughout the 6-hour build window. Their informal notes often feed directly into judge deliberations:

* **Ask Design Review Questions, Not Syntax Questions:**
  * Avoid flagging down an SA for basic syntax errors or Python package mismatches.
  * Instead, ask architectural questions: *"We are evaluating whether to persist agent execution traces in an S3 bucket or DynamoDB for auditability. What trade-offs do production teams building on Bedrock typically consider?"*
* **Articulate Individual Ownership:**
  * When mentors visit your table, make roles distinct: *"My teammate structured the multimodal parsing pipeline, while I focused on the deterministic safety guardrails and handoff state machine."*
* **Be Receptive to AWS Suggestions:**
  * If an SA suggests an AWS-native pattern (e.g., Strands, AgentCore, or a specific Bedrock feature), acknowledge it and incorporate a reference to it in your architecture diagram or pitch.