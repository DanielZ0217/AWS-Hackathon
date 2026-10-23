from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from cloud.bedrock import Bedrock, load_environment
from .schemas import EvidenceItem


@dataclass(frozen=True)
class KnowledgeHit:
    source_id: str
    path: str
    excerpt: str
    score: float


class KnowledgeProvider:
    """Layer 00 boundary. Replace search() with the managed retrieval adapter."""

    async def search(self, query: str, scopes: list[str], limit: int = 5) -> list[KnowledgeHit]:
        raise NotImplementedError


class LocalReferenceProvider(KnowledgeProvider):
    """Read-only demo adapter over Layer 00-style reference files."""

    def __init__(self, reference_root: str | Path):
        self.reference_root = Path(reference_root).resolve()

    async def search(self, query: str, scopes: list[str], limit: int = 5) -> list[KnowledgeHit]:
        terms = {term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 2}
        hits: list[KnowledgeHit] = []
        for path in sorted(self.reference_root.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            words = re.findall(r"[a-z0-9]+", text.lower())
            overlap = sum(words.count(term) for term in terms)
            scope_bonus = sum(1 for scope in scopes if scope.replace("_", " ") in text.lower())
            score = float(overlap + scope_bonus)
            if score <= 0:
                continue
            excerpt = " ".join(text.split())[:1200]
            hits.append(KnowledgeHit(path.stem, str(path), excerpt, score))
        return sorted(hits, key=lambda item: (-item.score, item.source_id))[:limit]


class BedrockKnowledgeBaseProvider(KnowledgeProvider):
    """Managed Layer 00 retrieval with fail-closed source provenance checks."""

    def __init__(self, knowledge_base_id: str, reference_uri_prefix: str,
                 cloud: Bedrock | None = None):
        if not knowledge_base_id:
            raise ValueError("BEDROCK_KNOWLEDGE_BASE_ID is required for managed retrieval")
        if not reference_uri_prefix.startswith("s3://") or not reference_uri_prefix.endswith("/"):
            raise ValueError("BEDROCK_KB_REFERENCE_URI_PREFIX must be an s3:// prefix ending in /")
        self.knowledge_base_id = knowledge_base_id
        self.reference_uri_prefix = reference_uri_prefix
        self.cloud = cloud or Bedrock()

    async def search(self, query: str, scopes: list[str], limit: int = 5) -> list[KnowledgeHit]:
        focused_query = query
        if scopes:
            focused_query = f"{query}\nClinical reference scopes: {', '.join(scopes)}"
        return await asyncio.to_thread(self._search_sync, focused_query, limit)

    def _search_sync(self, query: str, limit: int) -> list[KnowledgeHit]:
        response = self.cloud.client("bedrock-agent-runtime").retrieve(
            knowledgeBaseId=self.knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={"vectorSearchConfiguration": {
                "numberOfResults": max(1, min(limit, 25)),
            }},
        )
        hits: list[KnowledgeHit] = []
        for result in response.get("retrievalResults", []):
            location = result.get("location", {})
            uri = location.get("s3Location", {}).get("uri", "")
            if not uri.startswith(self.reference_uri_prefix):
                raise ValueError(f"Knowledge Base returned an unapproved source location: {uri or '<missing>'}")
            text = result.get("content", {}).get("text", "").strip()
            if not text:
                continue
            metadata = result.get("metadata", {})
            source_id = str(metadata.get("source_id") or Path(urlparse(uri).path).stem)
            hits.append(KnowledgeHit(
                source_id=source_id,
                path=uri,
                excerpt=text[:4000],
                score=float(result.get("score", 0.0)),
            ))
        return hits


def build_knowledge_provider(root: str | Path) -> KnowledgeProvider:
    load_environment()
    root = Path(root)
    mode = os.getenv("WORKFLOW_RETRIEVAL_MODE", "").strip().lower()
    knowledge_base_id = os.getenv("BEDROCK_KNOWLEDGE_BASE_ID", "").strip()
    if mode == "local" or (not mode and not knowledge_base_id):
        return LocalReferenceProvider(root / "sample-data" / "s3" / "reference")
    if mode not in {"", "managed"}:
        raise ValueError("WORKFLOW_RETRIEVAL_MODE must be 'managed' or 'local'")
    bucket = os.getenv("S3_BUCKET", "").strip()
    object_prefix = os.getenv("S3_REFERENCE_PREFIX", "sample-data/s3/reference/").strip("/")
    default_uri_prefix = f"s3://{bucket}/{object_prefix}/" if bucket else ""
    uri_prefix = os.getenv("BEDROCK_KB_REFERENCE_URI_PREFIX", default_uri_prefix).strip()
    return BedrockKnowledgeBaseProvider(knowledge_base_id, uri_prefix)


def to_evidence_items(task_id: str, hits: list[KnowledgeHit]) -> list[EvidenceItem]:
    return [EvidenceItem(
        id=f"evidence-{task_id}-{index}", source_ids=[hit.source_id],
        passage_refs=[hit.path], excerpt=hit.excerpt, rerank_score=hit.score,
    ) for index, hit in enumerate(hits, start=1)]

