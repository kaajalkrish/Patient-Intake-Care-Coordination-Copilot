"""Embeddings for semantic memory + RAG.

Default: local open-source Sentence-Transformers `all-MiniLM-L6-v2` (no API key, per the approved
stack). Optional: Gemini embeddings via env. A deterministic hashing fallback keeps the system
importable/testable even if neither backend is available.
"""
from __future__ import annotations

import functools
import hashlib
import math

from ..config import settings

_DIM_FALLBACK = 256


@functools.lru_cache(maxsize=1)
def _local_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.local_embedding_model)


def _hash_embed(text: str, dim: int = _DIM_FALLBACK) -> list[float]:
    """Deterministic bag-of-hashed-tokens embedding — last-resort fallback (no deps)."""
    vec = [0.0] * dim
    for tok in (text or "").lower().split():
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed(text: str) -> list[float]:
    """Return an embedding vector for `text`."""
    if settings.use_local_embeddings:
        try:
            v = _local_model().encode(text, normalize_embeddings=True)
            return v.tolist() if hasattr(v, "tolist") else list(v)
        except Exception:
            return _hash_embed(text)
    # Gemini embeddings path
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        emb = GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embedding_model, google_api_key=settings.google_api_key
        )
        return emb.embed_query(text)
    except Exception:
        return _hash_embed(text)


def cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a[:n])) or 1.0
    nb = math.sqrt(sum(x * x for x in b[:n])) or 1.0
    return dot / (na * nb)
