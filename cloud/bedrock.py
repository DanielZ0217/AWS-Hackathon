"""Bedrock model calls. Default CLI checks configuration without network calls."""
import argparse
import json
import os
import struct
import zlib
from pathlib import Path

ROLES = ("decomposition", "classification", "routing", "specialist", "lab", "radiology",
         "ecg", "query", "evaluation", "recovery", "doctor", "nutrition", "physio",
         "guidance_review", "generation")
ROOT = Path(__file__).resolve().parent.parent


def _access_test_png():
    """Return a small valid PNG for testing multimodal model access."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    width = height = 32
    rows = b"".join(b"\x00" + (b"\xff\xff\xff" * width) for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def _require_test_response(response, label):
    content = response.get("output", {}).get("message", {}).get("content", [])
    if not content or response.get("stopReason") not in ("end_turn", "max_tokens"):
        raise ValueError(f"{label} test did not return a usable response")


def load_environment():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False, interpolate=False)


class Bedrock:
    def __init__(self):
        load_environment()
        self.region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
        default = os.getenv("BEDROCK_LLM_MODEL_ID") or "us.anthropic.claude-sonnet-4-6"
        self.models = {r: os.getenv(f"BEDROCK_{r.upper()}_MODEL_ID") or default for r in ROLES}
        self.embedding_model = os.getenv("BEDROCK_EMBEDDING_MODEL_ID") or "amazon.titan-embed-text-v2:0"
        self.dimensions = int(os.getenv("BEDROCK_EMBEDDING_DIMENSIONS") or "1024")
        if self.dimensions not in (256, 512, 1024):
            raise ValueError("Titan embedding dimensions must be 256, 512, or 1024")
        self.rerank_model = os.getenv("BEDROCK_RERANK_MODEL_ID") or "cohere.rerank-v3-5:0"
        self._session = None

    def session(self):
        import boto3
        if self._session is None:
            self._session = boto3.Session(region_name=self.region)
        return self._session

    def client(self, service="bedrock-runtime"):
        from botocore.config import Config
        return self.session().client(service, config=Config(
            connect_timeout=10, read_timeout=120,
            retries={"mode": "standard", "total_max_attempts": 2}))

    def converse(self, role, messages, system=None, max_tokens=2048, tool_config=None):
        if role not in self.models:
            raise ValueError(f"Unknown role: {role}")
        request = {"modelId": self.models[role], "messages": messages,
                   "inferenceConfig": {"maxTokens": max_tokens}}
        if system:
            request["system"] = [{"text": system}]
        if tool_config:
            request["toolConfig"] = tool_config
        return self.client().converse(**request)

    def embed(self, text):
        response = self.client().invoke_model(
            modelId=self.embedding_model, contentType="application/json", accept="application/json",
            body=json.dumps({"inputText": text, "dimensions": self.dimensions, "normalize": True}))
        return json.loads(response["body"].read())["embedding"]

    def rerank(self, query, documents, top_n=5):
        if not documents or top_n < 1:
            raise ValueError("Rerank requires documents and a positive top_n")
        partition = self.session().get_partition_for_region(self.region)
        arn = os.getenv("BEDROCK_RERANK_MODEL_ARN") or (
            f"arn:{partition}:bedrock:{self.region}::foundation-model/{self.rerank_model}")
        return self.client("bedrock-agent-runtime").rerank(
            queries=[{"type": "TEXT", "textQuery": {"text": query}}],
            sources=[{"type": "INLINE", "inlineDocumentSource": {
                "type": "TEXT", "textDocument": {"text": text}}} for text in documents],
            rerankingConfiguration={"type": "BEDROCK_RERANKING_MODEL",
                "bedrockRerankingConfiguration": {"modelConfiguration": {"modelArn": arn},
                    "numberOfResults": min(top_n, len(documents))}})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", action="store_true", help="Check AWS login via STS; no model calls")
    parser.add_argument("--invoke", action="store_true", help="Call Sonnet and Nova text/image, Titan and Cohere with small test inputs; incurs usage")
    args = parser.parse_args()
    try:
        cloud = Bedrock()
        # Never print environment variables, credentials, account IDs or full SDK errors.
        print(json.dumps({"region": cloud.region, "models": cloud.models,
                          "embedding_model": cloud.embedding_model, "dimensions": cloud.dimensions,
                          "rerank_model": cloud.rerank_model}, indent=2))
        if args.identity:
            cloud.client("sts").get_caller_identity()
            print("AWS identity: authenticated")
        if args.invoke:
            response = cloud.converse("generation", [{"role": "user", "content": [
                {"text": "Reply with the word connected."}]}], max_tokens=32)
            _require_test_response(response, "Sonnet text")
            print("Sonnet text: response received")
            image_response = cloud.converse("classification", [{"role": "user", "content": [
                {"image": {"format": "png", "source": {"bytes": _access_test_png()}}},
                {"text": "This is a connectivity test image. Reply with the word connected."},
            ]}], max_tokens=32)
            _require_test_response(image_response, "Sonnet image input")
            print("Sonnet image input: response received")
            nova_response = cloud.converse("lab", [{"role": "user", "content": [
                {"text": "Reply with the word connected."}]}], max_tokens=64)
            _require_test_response(nova_response, "Nova specialist text")
            print("Nova specialist text: response received")
            nova_image_response = cloud.converse("radiology", [{"role": "user", "content": [
                {"image": {"format": "png", "source": {"bytes": _access_test_png()}}},
                {"text": "This is a connectivity test image. Reply with the word connected."},
            ]}], max_tokens=64)
            _require_test_response(nova_image_response, "Nova specialist image input")
            print("Nova specialist image input: response received")
            vector = cloud.embed("Cloud connectivity test")
            if len(vector) != cloud.dimensions:
                raise ValueError("Unexpected embedding dimensions")
            print("Titan: embedding received")
            result = cloud.rerank("Which text describes a database?", [
                "A database stores structured records.", "A bicycle has two wheels."], top_n=2)
            if len(result.get("results", [])) != 2:
                raise ValueError("Unexpected reranking result")
            print("Cohere: ranking received")
        if not args.identity and not args.invoke:
            print("Configuration loaded. No AWS requests made. Use --identity or --invoke to test access.")
    except Exception as exc:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", type(exc).__name__)
        print(f"Check failed ({code}). See cloud/README.md for credentials, permissions and model access.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
