# Dataset destinations and acquisition checklist

Saved from the model/dataset research on 2026-10-23. All entries are **candidates, not downloaded or operational integrations**. Public availability does not grant unrestricted reuse. Model weights, evaluation datasets, reference passages and graph facts are different resources.

| Resource | Lane / intended destination | Exact selection and use |
| --- | --- | --- |
| Coherent synthetic patient | `patient_artifact` → run-scoped S3; answers → `evaluation` | One fictional patient with context, labs and matching report/image, radiology report, ECG report and artifact manifest. Store expected behavior separately. Do not combine unrelated real records into one patient. |
| [Clinical Laboratory Test Reports](https://data.mendeley.com/datasets/bygfmk4rx9/2) | `evaluation` | Candidate collection of 260 reports from 24 labs. Select a small layout-diverse subset and its extraction ground truth after reviewing de-identification and reuse terms. Preserve names, units, values and ranges exactly. No general-reference indexing. |
| [CheXpert](https://aimi.stanford.edu/datasets/chexpert-chest-x-rays) | `evaluation` | Selected chest images plus separate label files under dataset terms. Hide labels and known findings during blind image tests. |
| [MIMIC-CXR](https://physionet.org/content/mimic-cxr/2.1.0/) | Optional `evaluation` | Selected paired images/reports after credentialed access. Do not block the demo on new approval. Reports are supplied only in explicit report-explanation mode; hide them during blind image evaluation. |
| [PTB-XL 1.0.3](https://physionet.org/content/ptb-xl/1.0.3/records100/01000/) | `evaluation` | `ptbxl_database.csv`, `scp_statements.csv`, selected waveform `.dat`/`.hea` pairs and release/license. Preserve sample rate, lead names/order, units, record ID and split/patient grouping. Keep labels separate from model input. |
| [ACDC](https://www.creatis.insa-lyon.fr/Challenge/acdc/contest.html) | Optional `evaluation` | Registered-access cardiac MRI images and segmentation references. Verify task, dimensions and preprocessing match the selected segmentation model. These images are not raw k-space inputs for a reconstruction model. |
| [Nine MedlinePlus/NHLBI references](../architecture/00-ingestion-sources.json) | `reference_knowledge` → S3 parents + OpenSearch; reviewed assertions → Neptune | Main first-party article sections with source URL, headings, dates, rights record and exact locator. Include lab/ECG explanations, heart-failure context, food and physical-activity guidance. Exclude navigation and unlicensed media. |
| [USDA FoodData Central](https://fdc.nal.usda.gov/api-guide/) | Optional `structured_nutrition` | Selected food IDs, data type/release, serving quantities, nutrient IDs, amounts and units. Structured lookup for nutrition; amounts alone do not establish diet recommendations. Do not run the clinical relationship extractor over numeric tables by default. |
| Selected terminology | `terminology` → reviewed concept subset in Neptune | [RadLex](https://www.rsna.org/practice-tools/data-tools-and-standards/radlex-radiology-lexicon), [HPO](https://obofoundry.org/ontology/hp.html), [Mondo](https://obofoundry.org/ontology/mondo.html), LOINC/UCUM for labs and units. Pin releases, identifiers, hierarchy semantics and license records. See [ontology research](../architecture/ontology-research.md). |
| [Original MedQuAD](https://github.com/abachaa/MedQuAD) / [HF mirror](https://huggingface.co/datasets/keivalya/MedQuad-MedicalQnADataset) | Optional `reference_knowledge` after item-level review | Prefer original XML when source URLs/concept annotations matter. Select relevant question/answer passages, preserve provenance, review currency and exclusions. Do not restore copyright-omitted answers or treat the mirror as blanket reuse permission. |
| [RadGraph](https://www.physionet.org/content/radgraph/1.0.0/) | Optional `evaluation` | Annotated radiology text/entities/relations after its data-use agreement. Evaluate extraction, negation and relation fidelity. Report-level relations do not become universal clinical or causal edges. |
| [CheXagent](https://github.com/Stanford-AIMI/CheXagent) | `developer_reference` | Pin the code commit and license for CheXinstruct compilation and evaluation tooling. Cloning code does not grant underlying dataset access or make the dataset clinical guidance. |

## Agent knowledge coverage

| Consumer | Inputs for specialist analysis | Shared reference knowledge | Graph use |
| --- | --- | --- | --- |
| Lab | Synthetic structured labs / report image; Mendeley extraction tests | BNP, metabolic panel, potassium explanations | Test ↔ finding ↔ qualified condition associations; LOINC/UCUM normalization later |
| Radiology | X-ray/report; CheXpert or approved MIMIC evaluation | Selected diagnostic context; later curated radiology explanations | Findings, anatomy and conditions; RadLex terms; no labels promoted into facts |
| ECG | ECG report or annotated image baseline; raw PTB-XL waveforms remain evaluation-only | ECG explanation and diagnostic context | Measurement/finding associations; supplied report labels remain attributed observations |
| Doctor | Evidence packages from specialists | All permitted synthesis references | Reviewed connections, contradictions, source passages and uncertainty |
| Nutrition | Doctor-reviewed context and restrictions | Heart-healthy foods + scoped condition/lab context; optional FDC lookup | Guidance applicability with populations/restrictions; no nutrient-to-treatment inference |
| Physio | Doctor-reviewed symptoms, function and restrictions | Physical activity + scoped condition context | Guidance applicability and limits; a graph path is not patient-specific clearance |

The baseline has one shared OpenSearch reference index and one shared Neptune graph, with scope/version filters. It does not create a database per dataset or per agent. S3 separates artifact lanes; SQLite remains a planned workflow/journal store.

## What is still missing

Nova specialist preprocessing/output adapters; ECG label/threshold evaluation and waveform intake boundaries; an acquired reference corpus and reviewed loaded graph; extraction/citation/uncertainty tests on real passages; and a coherent reviewed synthetic case.

Start with Nova-powered X-ray/report explanation, lab-report extraction and ECG report explanation, Doctor review, and requested nutrition/physio guidance. Keep raw waveform diagnosis and MRI as later, separately validated branches. The pipeline in this folder addresses preparation of resources; it does not make specialist prompts clinically validated.
