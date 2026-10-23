# Architecture

A care-team demo: specialist AI agents review one patient's **chest X-ray and ECG**, pass their findings to a
doctor-style synthesizer, and a caregiver gets a plain-language summary. Prototype, synthetic/public data only,
not medical advice.

## Flow

```
Patient data (S3, one bucket per patient)      demo uses a bundled copy of the same files
        |
        v
  Backend (Python, FastAPI)
  1. Intake          split the request into questions
  2. Routing         the input type decides the specialist (plain code, no model)
  3. Specialists     run in parallel, each a Strands agent on Amazon Bedrock (Claude Sonnet 4.6)
       - Radiology   looks at the actual X-ray image
       - ECG         beats counted in code + machine report + a picture of the trace
  4. Red-flag gate   plain code. Any critical finding -> STOP, no guidance, human review required
  5. Doctor          Sonnet 4.6 combines the findings (and earlier visits) into a summary
  6. Guardrail       Amazon Bedrock Guardrails checks every patient-facing section
        |
        |  every step is an event, streamed live (Server-Sent Events)
        v
  Frontend (React)
  - Care team strip   who is working, and who handed what to the doctor
  - Plain summary     what was reviewed, what it may mean, questions for the doctor
  - "How we got this" evidence, uncertainty, every step; model details behind a switch
```

## AWS services
| Service | Used for |
| --- | --- |
| Amazon Bedrock (Claude Sonnet 4.6) | the specialist agents and the doctor synthesis, via the Strands Agents SDK |
| Amazon Bedrock Guardrails | masks personal details (names, phones, emails, addresses); withholds dosing or prescribing advice |
| Amazon S3 | patient files, one bucket per patient: encrypted, public access blocked, TLS-only |

## Safety design
- **The red-flag stop is code, not a prompt.** Guardrails filter text and cannot judge a number, so a critical
  heart rate, an ECG report that mentions possible acute injury, or a pulmonary-edema label on the X-ray stops the run
  before any model is asked for guidance.
- **The guardrail is a second layer** on the text the caregiver sees.
- **Failures are visible, never guessed.** A missing file or a failed step becomes a marked gap, the summary says
  what it does not cover, and it asks for clinical re-evaluation.
- **Auditable.** Every handoff, finding, flag and model call is an event the UI can show.

## Data
One virtual patient (three visits, each with a real 12-lead ECG and a real chest X-ray) from the MIMIC-NIH composite
cohort made for this hackathon: ECGs from MIMIC-IV-ECG (PhysioNet), X-rays from NIH ChestX-ray14.
**The ECG and X-ray in each virtual patient come from two different real people**, the ECG report text is
machine-generated, and the labels are noisy. Say this on stage.

## Status (be accurate in the slides)
| Piece | State |
| --- | --- |
| React frontend, live event stream, recorded-replay fallback (real recorded runs) | built and tested |
| Bedrock agents (X-ray image + ECG), Guardrail, red-flag stop, SSE backend | built and verified end to end in a browser on the real VP01 data, all three visits |
| S3 bucket-per-patient scheme | code written, not yet run; the demo reads the bundled local copy |
