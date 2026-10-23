# Small S3 Knowledge Base sample

The chosen GraphRAG demo has eleven short authored, sourced reference summaries in [reference](reference/), and a separate [fictional patient](patient/fictional-001/) case. Upload all files with `python -m ingestion.managed_kb upload`. The Knowledge Base data source must point only at:

```text
s3://awshackathon2026/sample-data/s3/reference/
```

The patient files are under `sample-data/s3/patient/fictional-001/` and the held-out expected behavior is local in `sample-data/evaluation/`; neither is included in retrieval. The bucket must exist and be in the Knowledge Base Region. Sidecar filenames append `.metadata.json` to document names. [AWS S3 connector and metadata format](https://docs.aws.amazon.com/bedrock/latest/userguide/s3-data-source-connector.html).

These are short authored reference summaries grounded in linked MedlinePlus/NHLBI pages. They test ingestion, retrieval, citations, and metadata filtering. They contain no patient data or hidden evaluation answer. Bedrock's Neptune Analytics GraphRAG sync populates both its vector index and generated graph; the graph is not a clinician-reviewed ontology.

Example retrieval question: “What does an ECG measure, and can it diagnose a heart condition by itself?” Check that the result points to this document and retains its `corpus_role`, `source_type`, and `topics` metadata.
