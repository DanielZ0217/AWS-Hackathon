# Calling Bedrock from the project

The repository root contains a local `.env` **file**, not a folder. It is ignored by Git. `.env.example` is the shareable template. A shared Python adapter reads the root file regardless of the working directory; existing shell variables take precedence. No credentials are bundled, and no AWS resources are provisioned.

For the deployed demo, `.env` and `.env.example` identify Bedrock Knowledge Base `L5QSI6FVDY` and Neptune Analytics graph `g-qvfjw4p3qa`. The [managed GraphRAG runbook](../ingestion/managed-neptune-graphrag.md) covers the actual S3 upload, provisioning, sync, and verification. OpenSearch and Neptune Database endpoints below are optional legacy/custom-path settings, not requirements for this demo.

## Setup (PowerShell, from AWS_Hackathon)

```powershell
python -m venv .venv
$projectPython = if (Test-Path .venv\Scripts\python.exe) { '.\.venv\Scripts\python.exe' } else { '.\.venv\bin\python.exe' }
& $projectPython -m pip install -r requirements.txt
```

This machine's MSYS2 Python creates `.venv\bin\python.exe`; standard Windows Python usually creates `.venv\Scripts\python.exe`. The variable above handles both. Set it again when opening a new PowerShell session.

For another team member's checkout, copy `.env.example` to `.env` if they do not already have one. Do not overwrite their existing settings.

Authenticate using your hackathon account's prescribed method. For AWS CLI v2 SSO:

```powershell
aws configure sso --profile hackathon
aws sso login --profile hackathon
```

Then uncomment `AWS_PROFILE=hackathon` in `.env`. If the event provides temporary credentials instead, fill the commented access-key, secret-key and session-token entries in your local file. Session credentials expire; replace all supplied values together. On AWS compute, leave credentials/profile unset to use the attached role. The SDK follows the [AWS credential chain](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html).

## Verify

```powershell
# Local settings only; does not read or print credentials or contact AWS.
& $projectPython -m cloud.bedrock

# Checks AWS login only; does not invoke a model.
& $projectPython -m cloud.bedrock --identity

# Six small billable requests: Sonnet text/image, Nova specialist text/image,
# Titan embeddings, and Cohere reranking.
& $projectPython -m cloud.bedrock --invoke
```

Default region: `us-east-1`. Sonnet uses the `us.` cross-region inference profile, which can process requests in supported US Regions. Verify this matches the account's allowed routing. Region configuration alone does not guarantee single-region processing.

Sonnet is used for decomposition, optional classification, routing, query construction, evaluation, recovery, Doctor synthesis, guidance review and final generation. Amazon Nova Pro is the main model for the lab, radiology, ECG, nutrition and physio specialists. `.env.example` lists explicit per-role mappings. Titan uses 1,024 dimensions by default; changing dimensions requires a matching versioned retrieval index. Cohere uses the separate `bedrock-agent-runtime` client and `Rerank` API.

## Use from agent code

```python
from cloud.bedrock import Bedrock

cloud = Bedrock()
response = cloud.converse(
    "decomposition",
    [{"role": "user", "content": [{"text": "Explain the supplied test reports."}]}],
    system="Break the request into bounded subtasks; do not infer missing patient facts.",
)
vector = cloud.embed("What does this test measure?")
ranking = cloud.rerank("What does this test measure?", ["First passage", "Second passage"])
```

This is a connection adapter, not the implemented LangGraph workflow or final agent prompts. Preserve output validation and the state contracts when wiring agents. `converse` returns the SDK response; use the text content and usage metadata, not private reasoning blocks, in application outputs.

The ingestion CLI also loads `.env` for live `extract` and `embed` commands. `--region`, `--model-id` and `--dimensions` override environment defaults. `GRAPH_MODEL_ID` is explicitly set to Sonnet for the working Converse adapter; the preferred GPT-6 Sol candidate requires a separate compatibility test before switching. The ingestion embedding implementation is deliberately fixed to Titan V2 and rejects a different configured embedding model. See [ingestion services](../ingestion/README.md#cloud-services-and-models) for S3, OpenSearch, Neptune and Textract settings.

```powershell
& $projectPython -m ingestion.pipeline extract --work ingestion/work/demo-v1
& $projectPython -m ingestion.pipeline embed --work ingestion/work/demo-v1
```

## Access failures

- Missing credentials / profile: configure the intended profile or supplied temporary credentials.
- Expired token / SSO session: sign in again or refresh temporary credentials.
- Access denied: ask the account administrator for the required model access and `bedrock:InvokeModel` permissions (including inference-profile destination models), plus `bedrock:Rerank` for reranking. Streaming later requires `bedrock:InvokeModelWithResponseStream`.
- Model access/validation error: check account availability, region, model/profile IDs, provider terms and supported request parameters.
- Throttling: check inference quotas; do not add unbounded retry loops.

Model calls do not require OpenSearch, Neptune or S3 to be provisioned first. Those services are separate retrieval/ingestion setup. See [AWS's direct reranking example](https://docs.aws.amazon.com/bedrock/latest/userguide/rerank-use.html).
