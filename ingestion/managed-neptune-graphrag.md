# Managed Bedrock + Neptune Analytics demo

This is the selected quick-build path. It replaces the planned standalone OpenSearch index **for this demo**. One Bedrock Knowledge Base backed by one Neptune Analytics graph handles vector RAG and graph-enhanced retrieval. Neptune Analytics is different from Neptune Database; do not feed the old Neptune Database CSV export to this Knowledge Base. The Knowledge Base graph is machine-extracted from text, not a validated medical ontology or confirmed causal network.

## Exact data boundary

- `s3://awshackathon2026/sample-data/s3/reference/`: eleven small, authored educational summaries grounded in MedlinePlus/NHLBI. Only this prefix is connected to the KB. Coverage includes BNP and metabolic labs, ECG and monitoring limits, chest imaging plus CT/MRI/echo, oxygen saturation, symptoms, nutrition and physical activity.
- `s3://awshackathon2026/sample-data/s3/patient/fictional-001/`: one entirely fictional intake, lab JSON, chest-X-ray **report**, and ECG **report**. There is no image or waveform, so do not claim image/waveform inference.
- `sample-data/evaluation/fictional-001-expected.md`: local held-out checks; never part of the KB source.
- Mendeley lab reports, CheXpert, PTB-XL, credentialed MIMIC-CXR, ACDC and RadGraph are **evaluation candidates**, not reference knowledge. No records from those datasets were downloaded or uploaded in this quick build. Their access, privacy, license, and ground-truth separation still need review. USDA FoodData Central is an optional structured nutrition lookup, not present in the graph. RadLex/HPO/Mondo and lab terminology have not been loaded or validated. MedQuAD is not included pending item-level rights review.

## Commands from repository root

Use the existing private `.env` for short-lived AWS credentials. Do not commit or print them.

```powershell
.venv\bin\python.exe -m ingestion.managed_kb upload
.venv\bin\python.exe -m ingestion.managed_kb build
.venv\bin\python.exe -m ingestion.managed_kb status
.venv\bin\python.exe -m ingestion.managed_kb verify
.venv\bin\python.exe -m ingestion.managed_kb query --query "How do cardiac CT and MRI differ?" --top 3
```

`upload` is idempotent: it skips identical S3 objects and refuses to overwrite differing ones. It uses S3-managed encryption. `build` selects Titan Text Embeddings V2 at 1,024 dimensions, a 16 m-NCU Neptune Analytics graph with no replica and private connectivity, and Amazon Nova Micro for Bedrock-managed entity/relation extraction. It creates a service role whose S3 object read permission is limited to the reference prefix. It then creates a Bedrock Knowledge Base, S3 data source, and ingestion job. Existing resources with the expected names are reused. If a step fails, inspect status and rerun rather than creating duplicates. `build` starts a new sync when the previous one is complete, so use `status` for read-only monitoring.

Neptune GraphRAG rejected `STRING_LIST` sidecar attributes in the first sync. The sidecars now use scalar strings for `topics`; `repair-metadata` is a narrowly checked one-time migration for the previous five S3 sidecars, not a general overwrite command. The six newer documents also include `source_url` and `review_status` metadata. Authoring these summaries and checking their source links is not the same as clinician review.

The `query` command retrieves up to 20 KB passages, rejects non-reference S3 sources, then reranks with Cohere and returns unique document URIs, source metadata, scores, and short excerpts. This is the demo retrieval adapter for specialist agents; it does not validate graph edges or decide care actions. In test queries, it ranked the dedicated CT/MRI, BNP and oxygen documents first after raw GraphRAG retrieval had ranked them lower.

## Live deployment on 2026-10-23

- Neptune Analytics graph: `g-qvfjw4p3qa` (`AVAILABLE`, 16 m-NCU, no replica).
- Bedrock Knowledge Base: `L5QSI6FVDY` (`ACTIVE`).
- S3 data source: `KPKRRHLGVR` at `s3://awshackathon2026/sample-data/s3/reference/`.
- Latest successful ingestion job: `ETIJRVNQQV` (`COMPLETE`: eleven documents scanned, six new documents indexed, zero failed). Earlier successful job `SCFMSKTSEM` indexed the first five. The initial `RKMMJDNLRZ` indexed zero because its list-valued sidecars were rejected.
- Retrieval checks for ECG, food, activity, CT/MRI, BNP and oxygen returned reference S3 URIs only. Source and review metadata is attached to the six new documents. No direct graph edge audit was performed because the current AWS principal lacked `GetGraphSummary` permission; do not claim that particular clinical relationships or traversal depth were validated.

The graph incurs charges while running, plus Bedrock ingestion/model usage. Pause or remove it when the demo is finished, after deciding whether the Knowledge Base must remain available. AWS advises deleting the KB before the graph. Do not pause during the live demo. The script deliberately does not automate deletion or cleanup.

## Verify before claiming it works

1. Run `verify`; it requires a clean scan of all eleven local reference documents and checks that test-query results stay inside the reference prefix. Errors are not a successful build.
2. Use `bedrock-agent-runtime.retrieve` with the Knowledge Base ID to ask, for example, what an ECG records. Check it cites an S3 reference document and never returns the patient or held-out answers.
3. Ask cross-document questions and inspect citations. A returned graph path or Bedrock-generated edge is evidence for retrieval, not a medical conclusion; any care action still needs a clinician.
4. Check that nutrition and physio questions find the appropriate reference summaries. Model-generated edges and terminology alignment remain unreviewed and cannot be used as a clinical validation gate.

References: [Bedrock Neptune GraphRAG setup](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-build-graphs-build.html), [Bedrock KB role permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-permissions.html), [Neptune Analytics pricing](https://aws.amazon.com/neptune/pricing/).
