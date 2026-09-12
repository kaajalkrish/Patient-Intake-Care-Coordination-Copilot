"""Agentic-RAG retriever over the synthetic guideline corpus (AC-11).

Builds a vector index of the care-pathway / triage-guideline documents in
data/synthetic/guidelines/ and exposes `care_pathway_lookup(query, k)`.

Primary backend: **Chroma** (per the approved stack). If Chroma is unavailable, falls back to an
embedded cosine index built on the local Sentence-Transformers embeddings — so retrieval always works
and is deterministic in tests.

"Agentic" = the agent DECIDES when to call this (it is bound as a tool), rather than a fixed
pre-retrieval step. See src/agents/triage.py and docs/context-engineering.md.
"""
from __future__ import annotations

import functools
from pathlib import Path

from ..config import settings
from ..memory.embeddings import cosine, embed

GUIDELINES_DIR = settings.path("data/synthetic/guidelines")


def _chunk(text: str, size: int = 500, overlap: int = 80) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i : i + size]))
        i += size - overlap
    return chunks


def _load_corpus() -> list[dict]:
    docs: list[dict] = []
    if not GUIDELINES_DIR.exists():
        return docs
    for path in sorted(GUIDELINES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for j, ch in enumerate(_chunk(text)):
            docs.append({"id": f"{path.stem}-{j}", "source": path.name, "text": ch})
    return docs


class _CosineIndex:
    """Deterministic embedded fallback index."""

    def __init__(self, docs: list[dict]):
        self.docs = docs
        self.vectors = [embed(d["text"]) for d in docs]

    def query(self, q: str, k: int) -> list[dict]:
        qv = embed(q)
        scored = [
            {**d, "score": round(cosine(qv, v), 4)}
            for d, v in zip(self.docs, self.vectors)
        ]
        scored.sort(key=lambda d: d["score"], reverse=True)
        return scored[:k]


class _ChromaIndex:
    """Chroma-backed index (primary, per approved stack)."""

    def __init__(self, docs: list[dict]):
        import chromadb

        self.client = chromadb.EphemeralClient()
        self.col = self.client.get_or_create_collection("care_guidelines")
        self.col.add(
            ids=[d["id"] for d in docs],
            documents=[d["text"] for d in docs],
            embeddings=[embed(d["text"]) for d in docs],
            metadatas=[{"source": d["source"]} for d in docs],
        )

    def query(self, q: str, k: int) -> list[dict]:
        res = self.col.query(query_embeddings=[embed(q)], n_results=k)
        out = []
        for i in range(len(res["ids"][0])):
            dist = res["distances"][0][i] if res.get("distances") else 0.0
            out.append({
                "id": res["ids"][0][i],
                "text": res["documents"][0][i],
                "source": res["metadatas"][0][i].get("source", ""),
                "score": round(1.0 - dist, 4),
            })
        return out


@functools.lru_cache(maxsize=1)
def _index():
    docs = _load_corpus()
    if not docs:
        return _CosineIndex([])
    try:
        return _ChromaIndex(docs)
    except Exception:
        return _CosineIndex(docs)


def care_pathway_lookup(query: str, k: int = 3) -> list[dict]:
    """Retrieve top-k care-pathway / triage-guideline passages relevant to `query`.

    Returns a list of {id, source, text, score}. This is the function the agent calls on demand.
    """
    return _index().query(query, k)


def reset_index() -> None:
    """Clear the cached index (used in tests after (re)generating the corpus)."""
    _index.cache_clear()
