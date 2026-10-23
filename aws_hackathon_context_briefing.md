# AWS Agentic AI Hackathon (AUS20) — Complete Context & Briefing

---

# PART 1: STRATEGIC BRIEFING & ARCHITECTURE HYPOTHESES

## 1. Hackathon Context & Official Rules
* **Event:** AWS Austin Agentic AI Hackathon (AUS20) — Friday, October 23, 2026.
* **Timeline:** 
  * 9:00 AM: Kickoff & Keynote
  * 9:30 AM: Team formation (cross-functional teams of 3–5)
  * 10:00 AM – 4:00 PM: 6-hour build window
  * 4:00 PM: 3-minute live demos to AWS judges / SAs
  * 5:30 PM: Awards ceremony
* **Environment:** AWS Workshop Studio (`catalog.workshops.aws/join`) via a 12-digit event code. Provides temporary, pre-funded AWS accounts with Bedrock access. Options include browser VS Code, Kiro Ubuntu desktop, or exported AWS credentials for local CLI tools.
* **Track:** Track 1 — Caregivers Challenge (Healthcare).

---

## 2. Official Track Scope & Mandates (From Hackathon Organizers)

### Data Boundaries
* **Strictly Synthetic / Public Data:** No real patient PHI; HIPAA compliance is not required.
* **Suggested Public Datasets:** MultiCaRe, PathVQA, MedVQA, NIH ChestX-ray14, MIMIC-CXR-JPG, Kaggle clinical notes.

### Core Challenge & Scope
* **Multimodal Inputs Expected:**
  1. *Lab results:* Structured numbers, metabolic panels, blood chemistry.
  2. *Radiology:* Images, scans, or text-based imaging reports/impressions.
  3. *EKG / Vitals:* Telemetry, time-series, or vital signs.
* **Agent Personas (Blueprint vs. Hard Rule):**
  * *Organizers' suggested flow:* 5 roles (*Lab Analyst, Radiologist, Doctor, Nutritionist, Physio*).
  * *Actual official demo checklist requirement:* Pick one patient scenario, demonstrate **at least two specialist handoffs**, and end with a clear patient-facing result. (The team has full discretion to design, consolidate, or pick different personas based on team consensus and scope).
* **Target Patient-Facing Deliverables:**
  * Understandable condition/diagnosis summary.
  * Medication/prescription guidance.
  * Nutrition guidance.
  * Safe mobility/exercise guidance.

### Official HCLS Guardrails & Evaluation Criteria
* **Visible Specialist Handoffs:** The system must visibly show which persona reviewed which input and what it passed forward—do not collapse everything into an opaque, single-prompt chatbot.
* **Data Provenance & Uncertainty:** Final advice must tie back to specific findings/evidence, noting clinical uncertainty where applicable.
* **Explicit Failure Handling:** If data is missing, corrupted, or unreadable, the system must not guess or hallucinate; it must explicitly flag the gap and ask for clinical re-evaluation.
* **Mandatory Red-Flag Intercept:** Critical physiological values (e.g., extreme vitals, toxic lab spikes) must halt unsupervised recommendations and trigger a clear human-confirmation alert.

---

## 3. Hypothesized Strategy & Technical Ideas (For Team Discussion)
*Note: These are brainstormed architectural patterns to propose to the team at 9:30 AM, not fixed mandates.*

### Proposed Frameworks & Tools
* **Inference & Agent Loop:** Amazon Bedrock using either the **Strands Agents SDK** or native `boto3` Converse API. Real Python tool-calling (`@tool`) for deterministic calculations, range checks, and safety thresholds.
* **Proposed Frontend (Streamlit):**
  * Fast to prototype locally; eliminates frontend build overhead.
  * Can use `st.status` or visual step containers to make agent-to-agent handoffs explicitly visible to judges.
  * Can show dual views: an *Audit/Clinician Trace* (raw data, confidence, handoffs) vs. an *End-User / Caregiver View* (simple action cards, plain language).
  * Sidebar dropdown with pre-loaded synthetic presets (one "happy path", one "red flag / missing data path") to avoid live-typing risks during a 3-minute pitch.
* **Hypothesized AWS Service Additions (For Technical Depth Scoring):**
  * **Bedrock Guardrails:** Fast way to demonstrate Responsible AI. If used, configure PII filters to `MASK` (so processing continues with redacted placeholders) rather than `BLOCK` (which throws exceptions on clinician names or room numbers).
  * **Storage (S3 or DynamoDB):** S3 as an immutable bucket for raw notes/scans, or a lightweight DynamoDB table to persist caregiver task checklists.
* **AWS Alignment & Frugality (Leadership Principle):**
  * Support multi-model routing: fast/cheaper models (e.g., Nova Lite / Haiku) for parsing and data extraction; frontier models (e.g., Sonnet / Nova Pro) for clinical synthesis and caregiver translation.
  * Mention Bedrock Prompt Caching on repetitive static instructions/tools to highlight cost-awareness.

---

## 4. Operating Instructions for Claude Code
* **Wait for Team Consensus:** Do not prematurely lock in data schemas, specific persona counts, or UI layouts until team alignment at 9:30 AM.
* **Keep Code Decoupled:** Structure the code modularly so whatever personas and data formats the team selects can be plugged in cleanly.
* **Prioritize State Logging:** Ensure any agent or function writes its inputs, outputs, and reasoning steps to a central state/trace object so handoffs can be rendered visually regardless of the chosen UI framework.
* **Build for the Failure Case Early:** Ensure deterministic safety gates and missing-data handlers are first-class components rather than afterthoughts.

---

# PART 2: VERBATIM REFERENCE — TRACK 1 WEBPAGE TEXT

```text
Track 1:
Caregivers Challenge

Build multi-agent healthcare personas — Lab Analyst, Radiologist, Doctor, Nutritionist & Physio — that analyze lab results, radiology images, and EKG timeseries to deliver patient-friendly diagnoses, prescriptions, nutrition plans, and exercise guidance. Uses synthetic/public data only (no HIPAA compliance required).

Back to tracks
Registration ↗
HEALTHCARE / 01care
together.
BEFORE YOU BUILD
How to join the event
WORKSPACE OPTIONS
Choose your build environment
COMMON STARTER KIT
Set up Bedrock + AgentCore
BACKGROUND + INSTRUCTIONS
Make complex signals feel human.
Design a coordinated set of healthcare personas that can turn multiple kinds of patient information into a clear, useful experience for a person and their care team.

BACKGROUND
One patient, many signals
Healthcare guidance often depends on connecting structured results, images, time-series data, and everyday behavior. Your agents should show how specialists can collaborate while keeping the final experience understandable.
BUILD BRIEF
Give each persona a job
Make the handoffs visible. A strong prototype can show which persona reviewed each input, what it found, and how the combined result becomes patient-friendly guidance.
POTENTIAL AGENT FLOW
Ingest lab results, radiology images, and EKG timeseries from synthetic or public sources.
Route each input to the Lab Analyst, Radiologist, Doctor, Nutritionist, or Physio persona best suited to analyze it.
Combine the findings into patient-friendly diagnoses, prescriptions, nutrition plans, and exercise guidance.
Show data provenance, uncertainty, and the reasoning behind the final response.
DEMO CHECKLIST
Start with one patient scenario.
Show at least two specialist handoffs.
End with a clear patient-facing result.
KEEP IN SCOPE
Use synthetic/public data only. This is a hackathon prototype, not a clinical system or medical advice. Make that boundary explicit in the demo.
RESOURCES TO EXPLORE
Find data.
Borrow patterns.
Start with de-identified or synthetic data, then use the sample repositories as references for multimodal analysis, healthcare workflows, and Bedrock-based agents.

DATASETS
MultiCaRe
De-identified case reports with clinical histories, blood work, metabolic panels, and diagnostic radiology scans.
PathVQA and MedVQA
Multimodal diagnostic question-answer pairs covering CT, X-ray, pathology, and clinical questions.
NIH ChestX-ray14
A large chest-radiology dataset with NLP-extracted labels for image classification and retrieval experiments.
MIMIC-CXR-JPG
Chest X-rays matched with radiology reports. Review PhysioNet access requirements before using the dataset.
SAMPLE REPOSITORIES
AWS Healthcare Agents
AWS healthcare agent samples and FHIR integration patterns.
AWS Agentic RadMapper
A Bedrock AgentCore radiology workflow orchestrator reference.
AWS HCLS Bedrock Library
Bedrock agent patterns for healthcare and life-sciences workflows.
MedAgent-Pro
Multimodal medical reasoning patterns with vision and text planners.
MIMIC-Ext-CXR-QBA
A benchmark for radiology report evaluation and clinical reasoning.
Clinical Notes and Diagnosis Code
A Kaggle dataset and notebook reference for clinical-note workflows.
HCLS GUARDRAILS
Use synthetic or public data only. Keep inputs de-identified and do not send PHI to unapproved endpoints.
Handle failures explicitly. If an image agent or lab-data step fails, request clinical re-evaluation instead of crashing.
Record the evidence, agent handoffs, tool calls, uncertainty, and final outputs so the result can be audited.
Flag red-flag values, such as severe hypoxia, and require human confirmation before any care-related action.
Use approved AWS boundaries and encryption at rest and in transit for any data your prototype stores or transmits.
Good demo question
Can your team show how five specialized perspectives become one answer that a patient could actually understand?
```

---

# PART 3: VERBATIM REFERENCE — 8 PM LOGISTICS EMAIL

```text
Hi Agentic AI Builders,

We're less than a day out from the Austin Agentic AI Hackathon — here's everything you need to hit the ground running tomorrow.

📅 Logistics

When: Friday, October 23, 2026
Where: AUS20 — 2904 Palm Way, Austin, TX 78758
Format: One day, three tracks, cross-functional teams of 3–5.
Hosted by AWS, with support from our sponsors Arpio and Posit.
⏰ Your day at a glance

Time

Session

9:00 AM

Kickoff & Keynote — opening remarks, challenge overview & rules

9:30 AM

Team Intro — Meet your crew (teams of 3–5)

10:00 AM

Build Time — hack away; mentors on hand

4:00 PM

3-Minute Demos — each team presents to the judges

5:30 PM

Awards Ceremony — winners announced (gift cards & certificates!)

🔗 Your one-stop landing page

https://atx.rahman.dev/ — everything below, including each track's background page, lives here.

🎯 The three tracks

Pick the problem that pulls you in:

Track 1: Caregivers Challenge (Healthcare) — multi-agent personas analyzing labs, radiology & EKG data. Details
Track 2: Autonomic Shop Floor & Predictive Maintenance (Industrial AI) — predict equipment failure and coordinate maintenance. Details
Track 3: Financial Portfolio Management (Finance) — agents that build investment portfolios, scored against real performance. Details
💻 Before you build — joining the environment

Each track page has a step-by-step "How to join the event" guide: use a fresh/private browser window, sign in to Workshop Studio (catalog.workshops.aws/join), enter the 12-digit event access code from the event operator, and open the temporary AWS account provided. Then pick your build environment (browser-based VS Code or the Kiro Ubuntu desktop) from the Event dashboard.

📊 Sample data & 🧩 sample code

Each track page lists free, open datasets and AWS sample repositories to borrow patterns from — open your track page and scroll to "Resources to explore."

✅ Come ready

Bring a laptop and charger.
Skim your track's background page tonight so you start building — not reading — at 9 AM.
Come with a problem in mind; you'll form teams first thing.
Questions before tomorrow? Just reply to this email.

See you there — let's build something worth showing!

Best,
Austin Hackathon Team, AWS
```

---

# PART 4: VERBATIM REFERENCE — FREE AWS RESOURCES PACKET

```text
Free AWS Resources for Hackathon Students
Fundamentals, AI fundamentals, Amazon Bedrock, AgentCore, and Kiro (AWS-specific and free)
1. Get Set Up for Free (no cost, no surprise bills)
- AWS Free Tier: New accounts get up to $200 in credits over 6 months. The Free plan incurs no charges
unless you upgrade.
- AWS Builder Center for Students: Verified students unlock 1 full year of AWS Skill Builder free (900+
courses, labs, a certification voucher), plus guided workshops with free AWS sandboxes, no credit card.
Best single starting point.
2. Cloud Fundamentals (start here)
- AWS Skill Builder free learning center: 1,000+ free, self-paced resources, including 900+ courses on
compute, storage, networking, databases, and security.
- AWS Educate: Open to anyone 13+ with just an email (no credit card). Free hands-on labs for S3, EC2,
VPC, and RDS, plus self-paced courses and digital badges. Great for true beginners.
- AWS Cloud Quest: A free, gamified 3D role-playing game where you build real solutions across cloud
roles, including a Generative AI Practitioner track. A fun, low-pressure way to learn fundamentals.
- AWS Workshops catalog: 200+ expert-built, self-paced workshops. Several tagged 'Free AWS
environment available', ranging from Foundational (100) to Expert (400).
3. AI Fundamentals (concepts and no-code practice)
- PartyRock (Amazon Bedrock playground): Build no-code generative AI apps and learn prompt
engineering in minutes. Free daily usage, no AWS account or credit card needed. Has a 'For educators'
section. Ideal icebreaker for beginners.
- Generative AI 'Learn about' hub: A curated set of free intro courses: Introduction to Generative AI (Art of
the Possible), ML Essentials for decision makers, and more.
- AWS SimuLearn: Generative AI Practitioner: Free, simulation-based learning plan on Skill Builder:
learn-recommend-build scenarios with hands-on labs using Bedrock, Amazon Q, and SageMaker. No
prior AI experience needed.
4. Amazon Bedrock (generative AI foundations)
- Get started with Amazon Bedrock: Four pathways to build: console playground, API keys (30-day
quick-start key), SageMaker Unified Studio, and SDKs.
- Amazon Bedrock Workshop (official aws-samples): Labs on text generation, knowledge bases and
RAG, model customization, and agents. Tip: use a sandbox or Free Tier account to avoid charges.
5. Amazon Bedrock AgentCore (building AI agents)
- Get started with AgentCore (official docs): Zero-to-running-agent quickstart via the AgentCore CLI.
Covers the managed harness and code-based agents (Strands, LangGraph, etc.).
- Strands Agents SDK (open source): The AWS-native, open-source framework for building AI agents in
Python and TypeScript. Pairs directly with AgentCore (the workshops use Strands).
- AgentCore + Strands + Nova workshop (aws-samples): 8 progressive labs: first agent, code interpreter,
browser automation, secure credentials, MCP servers, runtime + observability, memory, and Gateway.
6. Kiro (AWS agentic IDE, free to start)
- Kiro (download and overview): AWS's agentic, spec-driven coding IDE (built on VS Code). Anyone can
start on the free tier (50 credits/month, no credit card; sign in with GitHub, Google, or AWS Builder ID,
no AWS account needed). Great for building your hackathon project.
- Kiro Students tier (check eligibility): Eligible university students get 1 full year free with 1,000
credits/month. Requires age 18+, a participating university, a university email, and SheerID verification.
Check whether your school is listed; if not, the standard free tier still applies.
- Your first project (guided): A walkthrough of Kiro's core features: steering files, specs, hooks, and MCP,
using a real project.
7. Build Something (project starters)
- AWS Hands-on Tutorials: Short, step-by-step build guides, including 'Build a Serverless Web
Application Using Generative AI' (Amplify + Bedrock) and full-stack React apps. A great project skeleton
to start from.