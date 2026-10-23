# Demo rehearsal checklist — Track 1, Caregivers Challenge

Demos are **3 minutes, strict**, at **4:00 PM**. Awards 5:30 PM. Build window closes at 4:00 PM.
Sources: the track page's demo checklist and HCLS guardrails (verbatim in `aws_hackathon_context_briefing.md`),
the team README's demo checklist, and the judge playbook. Items marked **(confirm)** depend on something
the backend teammate has not confirmed yet.

## 1. What the organizers require

### The official demo checklist (track page)
- [ ] Start with **one patient scenario**.
- [ ] Show **at least two specialist handoffs**.
- [ ] End with a **clear patient-facing result**.
- [ ] State the boundary plainly: **synthetic/public data only; a prototype, not a clinical system or medical advice.**

### Guardrails the judges will look for
| Guardrail (organizers' words, shortened) | What to show | Where in the UI | Status |
| --- | --- | --- | --- |
| Handoffs are visible, not one opaque prompt | Which specialist reviewed which input and what it passed on | Care team strip + "What was passed to the doctor" | built (mock data) |
| Evidence, provenance, uncertainty | Findings tied to their source; what is uncertain | Summary "Based on:", "What this summary can't tell you", per-specialist limits in "How we got this" | partly built. **Input provenance is not shown yet** (dataset name / record id per input). Needs data from the backend (confirm) |
| Fail safely: missing/corrupt data is flagged, never guessed | A specialist fails, and the screen says what is missing and asks for clinical re-evaluation | "Missing analysis" case: dashed handoff, "Part of this review is missing" | built (mock data) |
| Red flags halt recommendations and need human confirmation | A critical value stops guidance and shows a clear review requirement | "Red-flag safety stop" case: red banner, strip freeze, no summary sections | built, **but there is no confirm action**. See "Open decisions" |
| Audit trail: evidence, handoffs, tool calls, uncertainty, outputs | A record someone could replay | "How we got this" (every step in order); technical switch for model calls | built (mock data). A downloadable trace is not built |
| Approved AWS boundaries, encryption in transit and at rest | Say what is used and how data is protected | Not a screen. Say it in the pitch (confirm with the backend teammate) | confirm |
| Avoid unsupported certainty | Separate measured facts, model interpretations, possible explanations, clinician-confirmed conclusions | Summary wording ("may mean", "Nothing here is a diagnosis") | **copy needs review** with a clinician or mentor |

The organizers' closing question to answer in the room: *Can your team show how five specialized perspectives become one answer that a patient could actually understand?*

## 2. Before you rehearse
- [ ] Replace every **"(Placeholder text for UI development.)"** in the case copy. It is mock text and must not reach the judges.
- [ ] Replace placeholder values ("Critical value flagged (placeholder)") with the real flag from the team's red-flag case.
- [ ] Case names in the selector are mock names. Rename them to the team's real preset patients.
- [ ] Decide **live vs. replay** for the demo. The screen shows a **Replay** badge for scripted runs. Never present a replay as a live run. Say "recorded case" out loud if it is one.
- [ ] Have a clinician-literate teammate or a mentor read the final patient story once for anything clearly wrong.
- [ ] Both cases use the same synthetic patient, and the story hangs together (image, labs and heart rhythm tell one story). Say "synthetic patient assembled from public sources."

## 3. The 3-minute run (from the playbook, with what to click)
| Time | Say | Do |
| --- | --- | --- |
| 0:00–0:30 | The caregiver's problem in one sentence. "Synthetic data, a prototype, not medical advice." | Show the page with the case selected and the "What this case shows" line |
| 0:30–1:45 | Walk the handoffs. Three specialists in parallel, each hands its result to the doctor, the doctor decides | Press **Run case** (standard). Narrate while the strip fills. **Pause** after the handoff lines draw. Open **How we got this** for 10 seconds |
| 1:45–2:20 | The safety stop. "A critical value halts guidance until a human reviews it" | Select the **red-flag** case, **Run case**. Point at the red banner and the frozen strip |
| 2:20–3:00 | Read one line of the patient summary aloud. Then one sentence of architecture (confirm what is true) | Select the standard case again, scroll to the summary. Optionally flip **Show technical details** if asked |

Timing facts for the scripted runs at 1x: standard ≈ 13 s, red-flag ≈ 7 s, missing analysis ≈ 10 s, evidence recovery ≈ 18 s. The real backend will be slower. Use **Pause** and speed 2x to stay inside 3 minutes.
- [ ] Never type live. Pick cases from the dropdown.
- [ ] Assign roles: **one person talks, one person clicks.** Rehearse the handoff between them.
- [ ] Time the whole run with a stopwatch. Target 2:40 so there is slack.
- [ ] Rehearse at least 3 times, including once with the backup video.

## 4. If something breaks (decide before the day)
| What breaks | What to do |
| --- | --- |
| Backend unreachable or slow | Switch to the replay build and say it is a recorded case |
| Venue wifi congested | Run everything locally from the built app (`npm run build`, then `npm run preview`). Fonts and assets are self-hosted, so no outside requests |
| Browser misbehaves | Reload. State resets cleanly. Keep a second browser window ready |
| Projector resolution looks cramped | Zoom the browser to 110–125% before you start. The strip scrolls horizontally on narrow widths |
| Everything fails | Play the screen recording, and narrate over it |

- [ ] **At 3:30 PM, record the backup**: a clean run of the standard case and the red-flag case (QuickTime or OBS). Save it on the laptop and on a second device.
- [ ] Practice switching to the backup video without fumbling.

## 5. Right before going up
- [ ] Laptop charged and charger in the bag. Do-not-disturb on, notifications off.
- [ ] Browser: full screen, bookmarks bar hidden, one tab only, zoom set, cursor visible.
- [ ] App already loaded and the first case already selected.
- [ ] Screen recording tested for sound if you plan to narrate over it.
- [ ] `npm run build` done on the demo machine, not the dev server. Use `npm ci` if it is a fresh machine.

## 6. Likely judge questions (answers to confirm with the backend teammate)
- Why not a single prompt? → separate specialists with visible handoffs and a safety gate. *(confirm what the code does)*
- How is the red-flag stop enforced? → the strongest answer is "deterministic code checks the values, not a prompt." **Only say this if the backend really does it.** The helper in `core/safety.py` is not wired into the team's harness. *(confirm)*
- What happens when a model or file fails? → the "Missing analysis" case. The step is marked failed, the doctor sees the gap, and the summary asks for clinical re-evaluation.
- Where does the data come from, and is any of it real? → synthetic/public only; name the sources.
- Why this orchestration framework, and why EC2/S3 vs. SageMaker or others? → have a one-sentence production answer ready. *(confirm)*
- How do you control cost? → model routing and token awareness. *(confirm what is actually implemented)*
- Who built what? → say it distinctly. Frontend/visual layer, orchestration harness, data and specialists, safety.

## 7. Open decisions (the team should settle these before rehearsing)
1. **Human confirmation.** The guardrail says a red flag must require human confirmation before any care-related action. Today the system halts and withholds all guidance, and the screen says so, but there is no way to confirm. Either say plainly in the demo that guidance stays withheld until a human reviews (no care action is taken), or have the backend define a review/resume action and add a button.
2. **Input provenance.** The team README asks to display the source and provenance of each input. This needs the backend to send input records (dataset, id) so the UI can show them.
3. **Live vs. replay** for the actual demo (see section 2).
4. **Optional:** a "Download trace" button (JSON of the run's events), which answers "replayable trace" directly.
