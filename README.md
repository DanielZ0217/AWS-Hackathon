# Make Complex Signals Feel Human

Design a coordinated set of healthcare personas that turns multiple kinds of patient information into a clear, useful experience for a person and their care team.

> [!IMPORTANT]
> This project is a hackathon prototype—not a clinical system or a source of medical advice. It must use synthetic, public, or properly de-identified data only. Any care-related conclusion or action requires review and confirmation by a qualified healthcare professional.

## Background

### One patient, many signals

Healthcare guidance often depends on connecting structured results, medical images, time-series data, and everyday behavior. This prototype demonstrates how specialized agents can collaborate while keeping the final experience understandable, transparent, and useful.

## Build Brief

### Give each persona a clear job

Make the handoffs visible. The experience should show:

- Which persona reviewed each input
- What that persona found
- What evidence supports the finding
- How confident or uncertain the persona is
- How the specialist findings combine into patient-friendly guidance

## Healthcare Personas

| Persona | Primary responsibility | Example inputs | Example outputs |
| --- | --- | --- | --- |
| Lab Analyst | Reviews structured laboratory results and flags meaningful trends or outliers | Blood work, metabolic panels, biomarkers | Abnormal values, trends, reference ranges, uncertainty |
| Radiologist | Reviews diagnostic images and associated context | X-rays, CT scans, radiology metadata | Image findings, supporting regions, limitations, confidence |
| Doctor | Synthesizes specialist findings and identifies the appropriate next step | Lab and imaging findings, EKG summaries, patient context | Patient-friendly clinical summary, differential considerations, escalation flags |
| Nutritionist | Translates relevant findings into practical nutrition guidance | Metabolic markers, lifestyle context, clinician-approved constraints | Food and meal guidance, goals, cautions |
| Physio | Creates safe, practical movement guidance from the combined picture | Functional context, symptoms, clinician-approved constraints | Exercise suggestions, progression, stop conditions |

## Potential Agent Flow

1. Ingest lab results, radiology images, and EKG time-series data from synthetic or public sources.
2. Classify each input and route it to the best-suited specialist persona.
3. Have the Lab Analyst, Radiologist, and other specialists review their assigned evidence.
4. Pass structured findings—with provenance, confidence, and limitations—to the Doctor persona.
5. Let the Doctor synthesize the findings and request nutrition or physical-activity guidance where appropriate.
6. Present one clear patient-facing result that separates observations, interpretations, suggested questions, and clinician-confirmed actions.
7. Preserve an auditable record of evidence, handoffs, tool calls, uncertainty, and final outputs.

## Suggested Demo Story

Start with one synthetic patient whose case includes at least two input types, such as a metabolic panel, chest X-ray, and short EKG trace.

The demo should make at least two specialist handoffs visible—for example:

```text
Patient inputs
  ├─ Lab results ─────> Lab Analyst ──┐
  ├─ Chest X-ray ─────> Radiologist ──┼─> Doctor
  └─ EKG time series ─> Doctor ───────┘      │
                                              ├─> Nutritionist
                                              └─> Physio
                                                    │
                                                    v
                                      Patient-friendly care summary
```

The final screen should answer:

- What did each specialist review?
- What did each specialist find?
- What evidence supports the combined summary?
- What remains uncertain?
- What should the patient discuss with a healthcare professional?
- Is there a red flag that requires immediate human review?

## Demo Checklist

- [ ] Begin with one coherent patient scenario.
- [ ] Use only synthetic, public, or properly de-identified data.
- [ ] Include at least two different data modalities.
- [ ] Show at least two specialist handoffs.
- [ ] Stream validated subquestions, question-to-worker assignments, parallel progress, evidence checks, and actual recovery actions in a live timeline.
- [ ] Preserve a replayable trace of model/tool calls, evidence references, review decisions, failures, and final outcomes.
- [ ] Display the source and provenance of each input.
- [ ] Display confidence, uncertainty, and limitations.
- [ ] Handle missing data and agent/tool failures explicitly.
- [ ] Flag red-alert findings and require human confirmation.
- [ ] End with a clear, plain-language patient-facing result.
- [ ] State prominently that the prototype is not medical advice or a clinical system.

## HCLS Guardrails

- **Protect patient privacy.** Use synthetic, public, or properly de-identified data only. Do not send protected health information (PHI) to unapproved endpoints.
- **Fail safely.** If an image, lab-data, or time-series analysis step fails, clearly report the limitation and request clinical re-evaluation instead of silently continuing or crashing.
- **Keep an audit trail.** Record the evidence, provenance, persona handoffs, tool calls, uncertainty, and final outputs.
- **Escalate red flags.** Flag values such as severe hypoxia and require human confirmation before any care-related action.
- **Stay within approved infrastructure.** Use approved AWS boundaries and encryption at rest and in transit for any stored or transmitted data.
- **Avoid unsupported certainty.** Clearly distinguish measured facts, model interpretations, possible explanations, and clinician-confirmed conclusions.

## Data Sources to Explore

Begin with de-identified or synthetic data. Review every dataset's license, usage restrictions, and access requirements before including it in the prototype.

- [MultiCaRe](https://www.kaggle.com/datasets/mauronievasoffidani/multicare) — De-identified case reports with clinical histories, blood work, metabolic panels, and diagnostic radiology scans.
- [PathVQA and MedVQA](https://huggingface.co/datasets/flant5/pathvqa) — Multimodal diagnostic question-and-answer pairs covering CT, X-ray, pathology, and clinical questions.
- [NIH ChestX-ray14](https://www.kaggle.com/datasets/nih-chest-xrays/data) — A large chest-radiology dataset with NLP-extracted labels for image-classification and retrieval experiments.
- [MIMIC-CXR-JPG](https://physionet.org/content/mimic-cxr-jpg/) — Chest X-rays paired with radiology reports. Review and satisfy PhysioNet access requirements before use.

## Reference Implementations

- [AWS Healthcare Agents](https://github.com/aws-samples/sample-healthcare-agents) — AWS healthcare-agent samples and FHIR integration patterns.
- [AWS Agentic RadMapper](https://github.com/aws-samples/sample-agentic-radmapper) — A Bedrock AgentCore radiology workflow-orchestration reference.
- [AWS HCLS Bedrock Library](https://github.com/aws-samples/amazon-bedrock-agents-healthcare-lifesciences) — Bedrock agent patterns for healthcare and life-sciences workflows.
- [MedAgent-Pro](https://github.com/jinlab-imvr/MedAgent-Pro) — Multimodal medical-reasoning patterns with vision and text planners.
- [MIMIC-Ext-CXR-QBA](https://github.com/philip-mueller/mimic-ext-cxr-qba) — A benchmark for radiology-report evaluation and clinical reasoning.
- [Clinical Notes and Diagnosis Code](https://www.kaggle.com/datasets/smmmmmmmmmmmm/automated-medical-diagnosis-using-clinical-notes) — A Kaggle dataset and notebook reference for clinical-note workflows.

## Demo Challenge

**Can five specialized perspectives become one answer that a patient can actually understand?**

The strongest demo will make the collaboration visible without exposing the patient to unnecessary complexity. It will show where every important claim came from, communicate uncertainty honestly, and keep a qualified human in control of any care-related decision.
