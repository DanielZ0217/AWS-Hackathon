# Layer 00 ingestion runbook

## 1. Acquire and classify

Use [resources.md](resources.md) for resource selection and the [nine-page source manifest](../architecture/00-ingestion-sources.json) as the initial reference allowlist. The code does not crawl/download datasets, deploy endpoints, or infer reuse approval.

Acquire each permitted file through its source's supported download/API. Record source URL, release/acquisition date, license/rights reference and reviewer. Runtime specialists use the configured Amazon Nova Pro Bedrock profile; no external model weights are acquired by this pipeline. For an image/waveform test, register inputs and expected outputs as distinct `evaluation` records; the evaluation harness, not shared retrieval, decides which inputs reach a specialist.

Use a manifest item per file, with a unique `resource_id`, one of the roles below, and the fields in [manifest.example.json](manifest.example.json). `path` and `raw_path` resolve inside the manifest's directory. Do not use symlinks/absolute paths to escape it.

| Role | Pipeline behavior |
| --- | --- |
| `reference_knowledge` | Require rights/content review, original and normalized sections; create retrieval passages and graph candidates |
| `patient_artifact` | Register and copy into a patient lane; retain scenario ID and synthetic status in the item's metadata |
| `evaluation` | Register/copy separately; include dataset/split/record ID and `evaluation_kind: input` or `expected_output`; no shared indexing |
| `terminology` | Register pinned ontology artifact/license; parsing/import adapter remains future work |
| `structured_nutrition` | Register food/nutrient quantities and units; a structured lookup adapter remains future work |
| `developer_reference` | Register code/tooling references; no medical indexing |

The harness recognizes the nine reference IDs. Optional reviewed MedQuAD entries use `medquad-<stable-item-id>` and preserve the original article URL and item-level rights record. This namespace is a manual allowlist convention, not an automated license or credibility check. No source is approved merely by renaming it.

## 2. Normalize reference sections

Save untouched originals under `ingestion/local/raw/`. For HTML, extract first-party article headings/body only; remove navigation, scripts and unrelated/third-party media. For MedQuAD, parse selected XML items and retain original URLs, annotations and omissions. Native PDF text comes before OCR; scanned tables require a separate Textract/table adapter and numerical review. Do not OCR X-rays to infer findings.

Create `ingestion/local/normalized/<id>.json`:

```json
{
  "sections": [
    {
      "heading": "Exact section heading",
      "text": "Reviewed article text copied from the identified section, with qualifications intact.",
      "locator": "HTML heading/element identifier, XML item ID, or PDF page and block IDs"
    }
  ]
}
```

`locator` connects normalized sections to the original; it is manually reviewed in this baseline, not an automatic raw-HTML character-offset map. Downstream graph quotes and child spans are exact character offsets **within normalized section text**, never claimed to be byte offsets in HTML/PDF. Keep sentences, table headers, units and ranges together. Split sections exceeding 24,000 characters upstream at logical boundaries.

After checking rights, text fidelity and source locators, set `rights_approved` and `content_approved` to `true`, with the actual reviewer and ISO timestamp. The harness records that attestation; it does not authenticate reviewers or prove legal clearance.

## 3. Prepare immutable parents and children

Run `prepare` as shown in [README](README.md). Each section becomes a parent. Children use 300-word windows and 40-word overlap with exact character spans. These are **word** defaults, not the architectural token targets. Validate long sentences/tables on the actual corpus before switching to tokenizer-aware chunking.

IDs depend on corpus version, pipeline version, source ID and input hashes. The output includes separate artifact lanes, untouched originals, parents, children and a manifest. Identical reruns reuse files; changed input/settings need a new version. This keeps a later corpus from silently changing evidence used by an earlier patient run.

```text
ingestion/work/<version>/
  lanes/<role>/<content-hash>.<extension>
  reference/raw/<hash>.bin
  manifest.json
  parents.json
  children.json
  extractor.json
  batches/<parent-id>.json
  candidates.json
  review.template.json
  failures/<parent-id>-<error-hash>.json
  embedding-config.json
  embeddings/<child-id>.json
  embeddings.json
  export/
    opensearch-mapping.json
    opensearch-bulk.ndjson
    neptune/nodes.csv
    neptune/edges.csv
    review.json
    receipt.json
```

## 4. LLM concept and relationship extraction

The extractor sends one approved section at a time to the configured Bedrock Converse model. It requests bounded JSON: up to 40 typed concepts and 50 edges, with a 6,000-token output cap. The prompt treats source text as evidence, disallows outside knowledge and invented ontology IDs, and requests assertions rather than hidden chain-of-thought. No tools or database credentials are supplied to the model.

GPT-6 Sol remains the preferred architecture configuration, subject to a successful endpoint/Converse test; explicitly select the existing Sonnet fallback if necessary. Credentials and model enablement are deployment prerequisites. Record the actual region/model/profile. There is no silent API/provider fallback.

For each model response, code checks:

- JSON structure, allowed node classes and bounded counts.
- Existing endpoints, permitted relation types/direction, and same-type `IS_A` edges.
- A uniquely resolving exact quote; the application computes its character offsets.
- Explicit assertion status: `affirmed`, `negated`, `uncertain`, or `conditional`.
- Qualifiers and uncertainty notes; source/version lineage and extraction settings.

Invalid, filtered or truncated output stops the stage; no candidate bundle is declared complete. Successful section batches are cached. Retries reuse them. SDK retries are bounded; there is no LLM JSON-repair loop. Failures store identifiers/error type, not raw private reasoning.

These checks establish structural validity and text presence, **not clinical support**. A reviewer still checks whether the quoted passage supports the proposed relationship and scope. The LLM may miss an edge, misread negation or reverse a clinically meaningful association even with valid JSON.

## 5. Review, optional ontology mapping and graph connections

Edit a copy of `review.template.json`. The review contains the hash of the entire candidate bundle, reviewer/time and one accepted/rejected decision with rationale per assertion. Pending or missing decisions block export. `CAUSES` needs `explicit_causal_support: true` only after confirming an explicit causal source statement and its limitations. An association or multi-hop path never establishes causation.

Concepts are source-scoped by default to avoid accidentally merging ambiguous names. To connect the same concept across passages, use the review's `concept_keys` map:

```json
{
  "concept_keys": {
    "<parent-id-1>/n1": "local-v1:reviewed-concept-a",
    "<parent-id-2>/n3": "local-v1:reviewed-concept-a"
  }
}
```

Use the same key only for a reviewed identity match. When using an ontology, replace the local key with a verified system/release/code key from the pinned resource, and record mapping evidence in the review rationale or a referenced mapping record. Do not invent a code, merge related concepts as equivalents or infer hierarchy from an LLM name match. The harness checks conflicting types/self-loops; ontology existence, release checks and formal reasoning remain optional adapters, not implemented guarantees.

The graph export has typed clinical edges carrying source ID, review status, assertion status, qualifiers, extraction provenance and an immutable assertion ID. `SourcePassage` vertices retain full parent provenance. Structural `MENTIONS` edges connect source passages to concepts and **do not count toward the semantic clinical hop budget**.

Neptune may contain accepted **negated/uncertain/conditional assertions** as explicitly qualified records. Runtime traversal must inspect `assertion_status` and metadata; it must never interpret every stored edge as a true affirmative fact. Filter `corpus_version` and `review_status=accepted`, honor source retrieval scopes, and distinguish disagreement from corroboration. Multiple assertions retain separate evidence identities.

## 6. Embed and export

`embed` calls Titan Text Embeddings V2 on child text only. Choose 1,024 dimensions by default (256/512 also supported). Record model, region, normalization and dimensions; use the same settings for retrieval queries. Every vector must have the expected length and finite numeric values.

`export` requires a complete valid candidate review and complete embeddings. It creates:

- One OpenSearch index definition and bulk NDJSON containing child text, vector, parent/source IDs, spans, scopes and version. Full parents/originals stay in the artifact store.
- Neptune property-graph CSVs containing reviewed concepts, SourcePassage vertices, assertions and provenance links.
- A receipt with counts and manifest/candidate/review hashes, explicitly `staged_not_published`.

The export uses Neptune's supported property-graph CSV bulk format. This is an ingestion transport for the same Neptune Database graph that runtime queries with openCypher; it does not introduce a second graph database. It supplements the architecture's controlled openCypher loader option for initial bulk loading.

No RRF or reranking runs here. Configure OpenSearch hybrid search/RRF for the chosen deployment/version and call Cohere reranking at query time. The exported mapping alone does not configure a hybrid search pipeline.

## 7. Deploy and publish (operator steps; not executed by this harness)

1. Use approved encrypted S3 prefixes. Upload reference originals/parents/manifests under `reference/<version>/`; patient and evaluation lanes use separate prefixes and access policies. Runtime reference credentials must not read expected-answer objects. Do not upload the entire work tree into the reference prefix.
2. Create the versioned OpenSearch index from `opensearch-mapping.json` using the account's IAM-signed client. Submit `opensearch-bulk.ndjson` with `_bulk`; inspect **every item error**, not just the HTTP status. Refresh/count and test keyword/vector retrieval, source scopes and parent resolution. Verify the chosen OpenSearch service supports the mapping's k-NN engine/settings.
3. Upload **only** `export/neptune/nodes.csv` and `edges.csv` to an isolated S3 graph-import prefix. Start a Neptune Database bulk load using `format=csv`, the permitted loader role, region, and fail-on-error behavior. The property graph can then be read through openCypher. Check terminal load status and per-file errors; don't treat job submission as completion.
4. Verify expected graph counts and no dangling endpoints, load a sample evidence path, resolve all quotes to original parents, and test negation/uncertainty filters. Do not enable GraphRAG on a zero-assertion export just because the load command succeeded.
5. Run the reference retrieval checks below, then create a new publication manifest with concrete S3 parent/manifest locations, OpenSearch index, Neptune graph version, embedding configuration and validation results. Update the active pointer only after all required checks pass. Runtime pins this `knowledge_snapshot`; the staging receipt is never the active pointer.

Bulk loading is not a cross-service transaction. If OpenSearch or Neptune loading fails, leave the new version inactive and the prior version usable; inspect and resume the failed load before publication. A changed review/content set should use a new corpus/export version rather than overwriting a published graph. Production IAM, networking, KMS, deployment automation and rollback pointer management remain deployment work.

## Acceptance checks

- Every selected manifest resource is present or the stage fails; missing sources are never replaced silently.
- Only reference-role children appear in OpenSearch; model weights, patient facts and evaluation answers cannot be retrieved as guidelines.
- Nutrition and physio queries can retrieve their primary guidance pages and permitted context pages.
- Children/graph quotes resolve exactly to their pinned parent/source; OCR values match the original reviewed tables.
- All clinical edges are reviewed, with no unsupported causal upgrade; contradictory/negated assertions stay qualified.
- Reruns do not add duplicate passages/edges or redo successful model calls; modified inputs/settings do not reuse the old version.
- Retrieval relevance, citation fidelity and graph usefulness are evaluated on held-out authored questions. Use RadGraph for extraction evaluation only after access approval; do not put its labels into the shared graph.

## Offline state and runtime handoff

`manifest.json` holds source records and hashes; parents/children are derived records; extractor/batch files hold model provenance and usage; review files hold decisions/mappings; export receipt holds staged counts. These implement a subset of Layer 00's state contract. Live load reports, SQLite job tracking and publication manifests remain future adapters.

After actual deployment validation, a publisher can emit:

```text
knowledge_snapshot:
  corpus_version          immutable release ID
  graph_version           accepted Neptune version, or null if explicitly unavailable
  manifest_ref            published S3 manifest, not local staging receipt
  search_index_ref        concrete versioned OpenSearch index
  parent_store_ref        versioned S3 parents/originals location
  graph_ref               configured Neptune endpoint + application version filter
  embedding_config       model ID, region, dimensions, normalization
```

The runtime stores only this compact reference. It does not copy the corpus, model weights, evaluation labels or ingestion batches into patient state.

## API references

The live extraction adapter follows [Bedrock Converse](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html). Embedding requests use the documented [Titan V2 input/dimensions](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-embed-text.html). Export formats follow the [OpenSearch Bulk API](https://docs.opensearch.org/latest/api-reference/document-apis/bulk/) and [Neptune property-graph CSV specification](https://docs.aws.amazon.com/neptune/latest/userguide/bulk-load-tutorial-format-gremlin.html). Account/model/deployment compatibility still needs a live test.
