"""Small, rerunnable Bedrock + Neptune Analytics GraphRAG demo bootstrap.

This managed route uses the reference files staged for the existing Layer 00
pipeline, but Bedrock performs embedding and graph construction at sync time.
It deliberately never indexes patient or evaluation artifacts.
"""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from cloud.bedrock import load_environment

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "sample-data" / "s3"
BUCKET = "awshackathon2026"
PREFIX = "sample-data/s3/"
REFERENCE_PREFIX = PREFIX + "reference/"
GRAPH_NAME = "awshackathon-graphrag-demo"
KB_NAME = "awshackathon-neptune-graphrag-demo"
ROLE_NAME = "BedrockKB-Hackathon-NeptuneGraphRAG"
EMBED_MODEL = "amazon.titan-embed-text-v2:0"
GRAPH_MODEL = "amazon.nova-micro-v1:0"


def session():
    import boto3
    load_environment()
    return boto3.Session(region_name=os.getenv("AWS_REGION") or "us-east-1")


def code(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code", type(error).__name__)


def upload(s):
    client = s.client("s3")
    uploaded = skipped = 0
    for lane in ("reference", "patient"):
        for path in sorted((LOCAL / lane).rglob("*")):
            if not path.is_file():
                continue
            key = PREFIX + path.relative_to(LOCAL).as_posix()
            data = path.read_bytes()
            checksum = hashlib.sha256(data).hexdigest()
            try:
                old = client.get_object(Bucket=BUCKET, Key=key)["Body"].read()
            except client.exceptions.NoSuchKey:
                old = None
            if old is not None:
                if hashlib.sha256(old).hexdigest() != checksum:
                    raise RuntimeError(f"S3 object differs; refusing overwrite: s3://{BUCKET}/{key}")
                skipped += 1
                continue
            client.put_object(Bucket=BUCKET, Key=key, Body=data,
                              ServerSideEncryption="AES256",
                              ContentType="application/json" if path.suffix == ".json" else "text/markdown")
            uploaded += 1
    print(f"S3: uploaded {uploaded}, identical existing {skipped}; KB source s3://{BUCKET}/{REFERENCE_PREFIX}")
    print("Patient lane is separate; evaluation answers remain local and outside the KB source.")


def repair_metadata(s):
    """One-time migration from list-valued topics rejected by Neptune GraphRAG."""
    client = s.client("s3")
    changed = 0
    for path in sorted((LOCAL / "reference").glob("*.metadata.json")):
        key = PREFIX + path.relative_to(LOCAL).as_posix()
        new = json.loads(path.read_text(encoding="utf-8"))
        old = json.loads(client.get_object(Bucket=BUCKET, Key=key)["Body"].read())
        if old == new:
            continue
        expected = json.loads(json.dumps(new))
        value = expected["metadataAttributes"]["topics"]["value"]
        topics = value.pop("stringValue").split(",")
        value.update({"type": "STRING_LIST", "stringListValue": topics})
        if old != expected:
            raise RuntimeError(f"Unexpected S3 metadata content; refusing overwrite: {key}")
        client.put_object(Bucket=BUCKET, Key=key, Body=path.read_bytes(),
                          ServerSideEncryption="AES256", ContentType="application/json")
        changed += 1
    print("Migrated metadata sidecars:", changed)


def one(items, name):
    matches = [x for x in items if x["name"] == name]
    if len(matches) > 1:
        raise RuntimeError(f"Multiple resources named {name}; inspect manually")
    return matches[0] if matches else None


def graph(s):
    c = s.client("neptune-graph")
    found = one(c.list_graphs(maxResults=100).get("graphs", []), GRAPH_NAME)
    if found is None:
        print("Creating 16 m-NCU Neptune Analytics graph (ongoing charges until paused/deleted)...", flush=True)
        found = c.create_graph(graphName=GRAPH_NAME, provisionedMemory=16,
                               replicaCount=0, publicConnectivity=False,
                               vectorSearchConfiguration={"dimension": 1024},
                               deletionProtection=False,
                               tags={"project": "AWS-Hackathon", "purpose": "GraphRAG-demo"})
    graph_id = found["id"]
    for _ in range(30):
        current = c.get_graph(graphIdentifier=graph_id)
        state = current.get("status")
        if state == "AVAILABLE":
            print("Neptune graph ready:", graph_id)
            return current["arn"]
        if state in {"FAILED", "DELETING"}:
            raise RuntimeError(f"Neptune graph {graph_id}: {state}")
        time.sleep(10)
    raise TimeoutError(f"Neptune graph {graph_id} is still provisioning; rerun build")


def role(s, graph_arn):
    iam = s.client("iam")
    account = s.client("sts").get_caller_identity()["Account"]
    region = s.region_name
    trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow",
        "Principal": {"Service": "bedrock.amazonaws.com"}, "Action": "sts:AssumeRole",
        "Condition": {"StringEquals": {"aws:SourceAccount": account},
                      "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock:{region}:{account}:knowledge-base/*"}}}]}
    policy = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": f"arn:aws:s3:::{BUCKET}"},
        {"Effect": "Allow", "Action": ["s3:GetObject"],
         "Resource": f"arn:aws:s3:::{BUCKET}/{REFERENCE_PREFIX}*"},
        {"Effect": "Allow", "Action": ["bedrock:InvokeModel"], "Resource": [
            f"arn:aws:bedrock:{region}::foundation-model/{EMBED_MODEL}",
            f"arn:aws:bedrock:{region}::foundation-model/{GRAPH_MODEL}"]},
        {"Effect": "Allow", "Action": ["neptune-graph:GetGraph", "neptune-graph:ReadDataViaQuery",
            "neptune-graph:WriteDataViaQuery", "neptune-graph:DeleteDataViaQuery"],
         "Resource": graph_arn}]}
    try:
        existing = iam.get_role(RoleName=ROLE_NAME)["Role"]
    except iam.exceptions.NoSuchEntityException:
        existing = iam.create_role(RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Scoped Bedrock KB role for hackathon reference GraphRAG")["Role"]
    iam.put_role_policy(RoleName=ROLE_NAME, PolicyName="ReferenceGraphAccess",
                        PolicyDocument=json.dumps(policy))
    print("KB service role ready:", ROLE_NAME)
    return existing["Arn"]


def kb(s, graph_arn, role_arn):
    c = s.client("bedrock-agent")
    found = one(c.list_knowledge_bases(maxResults=100).get("knowledgeBaseSummaries", []), KB_NAME)
    if found is None:
        region = s.region_name
        try:
            found = c.create_knowledge_base(name=KB_NAME, roleArn=role_arn,
                knowledgeBaseConfiguration={"type": "VECTOR", "vectorKnowledgeBaseConfiguration": {
                    "embeddingModelArn": f"arn:aws:bedrock:{region}::foundation-model/{EMBED_MODEL}",
                    "embeddingModelConfiguration": {"bedrockEmbeddingModelConfiguration": {"dimensions": 1024}}}},
                storageConfiguration={"type": "NEPTUNE_ANALYTICS", "neptuneAnalyticsConfiguration": {
                    "graphArn": graph_arn, "fieldMapping": {"textField": "text", "metadataField": "metadata"}}},
                description="Synthetic-data hackathon reference corpus; no patient/evaluation objects")['knowledgeBase']
        except Exception as error:
            print("Knowledge Base creation error:", code(error))
            raise
    kb_id = found["knowledgeBaseId"]
    for _ in range(20):
        current = c.get_knowledge_base(knowledgeBaseId=kb_id)["knowledgeBase"]
        if current["status"] == "ACTIVE":
            print("Knowledge Base ready:", kb_id)
            return kb_id
        if current["status"] == "FAILED":
            raise RuntimeError(f"Knowledge Base failed: {current.get('failureReasons', [])}")
        time.sleep(5)
    raise TimeoutError(f"Knowledge Base {kb_id} is still provisioning; rerun build")


def source_and_sync(s, kb_id):
    c = s.client("bedrock-agent")
    sources = c.list_data_sources(knowledgeBaseId=kb_id, maxResults=100).get("dataSourceSummaries", [])
    found = one(sources, "reviewed-reference-summaries")
    if found is None:
        region = s.region_name
        found = c.create_data_source(knowledgeBaseId=kb_id, name="reviewed-reference-summaries",
            dataSourceConfiguration={"type": "S3", "s3Configuration": {
                "bucketArn": f"arn:aws:s3:::{BUCKET}", "inclusionPrefixes": [REFERENCE_PREFIX]}},
            vectorIngestionConfiguration={"contextEnrichmentConfiguration": {
                "type": "BEDROCK_FOUNDATION_MODEL", "bedrockFoundationModelConfiguration": {
                    "modelArn": f"arn:aws:bedrock:{region}::foundation-model/{GRAPH_MODEL}",
                    "enrichmentStrategyConfiguration": {"method": "CHUNK_ENTITY_EXTRACTION"}}}})['dataSource']
    source_id = found["dataSourceId"]
    jobs = c.list_ingestion_jobs(knowledgeBaseId=kb_id, dataSourceId=source_id, maxResults=20).get("ingestionJobSummaries", [])
    active = next((j for j in jobs if j["status"] in {"STARTING", "IN_PROGRESS"}), None)
    if active:
        print("Ingestion already running:", active["ingestionJobId"])
    else:
        job = c.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=source_id)["ingestionJob"]
        print("Started GraphRAG sync:", job["ingestionJobId"])
    print("Data source:", source_id)


def status(s):
    graphs = s.client("neptune-graph").list_graphs(maxResults=100).get("graphs", [])
    bases = s.client("bedrock-agent").list_knowledge_bases(maxResults=100).get("knowledgeBaseSummaries", [])
    print("Graph:", [(x["id"], x["status"]) for x in graphs if x["name"] == GRAPH_NAME])
    for base in bases:
        if base["name"] != KB_NAME:
            continue
        kb_id = base["knowledgeBaseId"]
        print("Knowledge Base:", kb_id, base["status"])
        sources = s.client("bedrock-agent").list_data_sources(knowledgeBaseId=kb_id, maxResults=20)
        for src in sources.get("dataSourceSummaries", []):
            print("Data source:", src["dataSourceId"], src["status"])
            jobs = s.client("bedrock-agent").list_ingestion_jobs(knowledgeBaseId=kb_id,
                dataSourceId=src["dataSourceId"], maxResults=5)
            print("Jobs:", [(j["ingestionJobId"], j["status"]) for j in jobs.get("ingestionJobSummaries", [])])


def verify(s):
    agent = s.client("bedrock-agent")
    base = one(agent.list_knowledge_bases(maxResults=100).get("knowledgeBaseSummaries", []), KB_NAME)
    if not base or base["status"] != "ACTIVE":
        raise RuntimeError("Knowledge Base is not active")
    kb_id = base["knowledgeBaseId"]
    source = one(agent.list_data_sources(knowledgeBaseId=kb_id, maxResults=100).get(
        "dataSourceSummaries", []), "reviewed-reference-summaries")
    if not source:
        raise RuntimeError("Reference data source is missing")
    source_id = source["dataSourceId"]
    detail = agent.get_data_source(knowledgeBaseId=kb_id, dataSourceId=source_id)["dataSource"]
    s3_source = detail.get("dataSourceConfiguration", {}).get("s3Configuration", {})
    if s3_source.get("bucketArn") != f"arn:aws:s3:::{BUCKET}" or s3_source.get(
            "inclusionPrefixes") != [REFERENCE_PREFIX]:
        raise RuntimeError("Knowledge Base data source is not limited to the reference prefix")
    jobs = agent.list_ingestion_jobs(knowledgeBaseId=kb_id, dataSourceId=source_id,
                                     maxResults=20).get("ingestionJobSummaries", [])
    if not jobs:
        raise RuntimeError("No ingestion job found")
    latest = max(jobs, key=lambda item: item["startedAt"])
    job = agent.get_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=source_id,
                                  ingestionJobId=latest["ingestionJobId"])["ingestionJob"]
    stats = job.get("statistics", {})
    expected = len(list((LOCAL / "reference").glob("*.md")))
    if job["status"] != "COMPLETE" or stats.get("numberOfDocumentsScanned", 0) < expected or stats.get(
            "numberOfDocumentsFailed", 0) != 0:
        raise RuntimeError(f"Latest sync is not a clean {expected}-document scan: {job['status']} {stats}")
    print("Verified latest sync:", latest["ingestionJobId"], "documents scanned:",
          stats["numberOfDocumentsScanned"], "new:", stats.get("numberOfNewDocumentsIndexed", 0))
    runtime = s.client("bedrock-agent-runtime")
    for query in ("What does an ECG record?", "What foods support heart health?",
                  "What should someone consider before starting physical activity?",
                  "How do cardiac CT, cardiac MRI, and echocardiography differ?",
                  "What else can cause a high BNP result?",
                  "What does pulse oximetry measure?"):
        results = runtime.retrieve(knowledgeBaseId=kb_id, retrievalQuery={"text": query},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}})
        items = results.get("retrievalResults", [])
        prefix = f"s3://{BUCKET}/{REFERENCE_PREFIX}"
        if not items or any(not x.get("location", {}).get("s3Location", {}).get("uri", "").startswith(prefix)
                            for x in items):
            raise RuntimeError(f"Retrieval boundary failed for: {query}")
        print("Reference-only retrieval:", len(items), query)


def query_reference(s, query, top):
    """Retrieve broadly from the KB, then rerank reference-only text."""
    from cloud.bedrock import Bedrock

    if not query or not query.strip() or not 1 <= top <= 10:
        raise ValueError("Provide a nonempty --query and --top between 1 and 10")
    agent = s.client("bedrock-agent")
    base = one(agent.list_knowledge_bases(maxResults=100).get("knowledgeBaseSummaries", []), KB_NAME)
    if not base or base["status"] != "ACTIVE":
        raise RuntimeError("Knowledge Base is not active")
    items = s.client("bedrock-agent-runtime").retrieve(
        knowledgeBaseId=base["knowledgeBaseId"], retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 20}}
    ).get("retrievalResults", [])
    prefix = f"s3://{BUCKET}/{REFERENCE_PREFIX}"
    if not items or any(not x.get("location", {}).get("s3Location", {}).get("uri", "").startswith(prefix)
                        for x in items):
        raise RuntimeError("Knowledge Base returned no results or a non-reference source")
    texts = [x.get("content", {}).get("text", "") for x in items]
    ranked = Bedrock().rerank(query, texts, top_n=min(len(items), top * 3))["results"]
    shown = set()
    for item in ranked:
        result = items[item["index"]]
        uri = result["location"]["s3Location"]["uri"]
        if uri in shown:
            continue
        shown.add(uri)
        print(json.dumps({"source": uri, "source_url": result.get("metadata", {}).get("source_url"),
            "rerank_score": round(item.get("relevanceScore", 0), 3),
            "excerpt": result.get("content", {}).get("text", "")[:300]}, ensure_ascii=False))
        if len(shown) >= top:
            break


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["upload", "repair-metadata", "build", "status", "verify", "query"])
    p.add_argument("--query", help="Reference-only question for the query action")
    p.add_argument("--top", type=int, default=3, help="Unique sources to show after reranking")
    args = p.parse_args()
    s = session()
    if args.action == "upload":
        upload(s)
    elif args.action == "repair-metadata":
        repair_metadata(s)
    elif args.action == "build":
        graph_arn = graph(s)
        role_arn = role(s, graph_arn)
        kb_id = kb(s, graph_arn, role_arn)
        source_and_sync(s, kb_id)
    elif args.action == "status":
        status(s)
    elif args.action == "verify":
        verify(s)
    else:
        query_reference(s, args.query, args.top)


if __name__ == "__main__":
    main()
