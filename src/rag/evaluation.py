"""Self-contained RAGAS-style evaluation for the agentic-RAG tool.

The `ragas` package (0.4.x) hard-imports `langchain_community.chat_models.vertexai`, a path removed in
the langchain 1.x stack this project pins — installing it would force a full langchain downgrade and
break the working Gemini integration. So we implement the four canonical RAGAS metrics ourselves,
using the project's own local Sentence-Transformers embeddings (deterministic, offline-safe) and,
when a Gemini key is present, Gemini for answer generation:

  - context_precision : how on-topic the retrieved contexts are for the question / ground truth.
  - context_recall    : how much of the ground-truth answer is covered by the retrieved contexts.
  - faithfulness      : how well the generated answer is grounded in the retrieved contexts
                        (penalizes hallucination).
  - answer_relevancy  : how well the generated answer addresses the question.

Each metric is a mean-of-max cosine similarity in [0, 1] — a continuous, threshold-free approximation
of the RAGAS definitions, so results are stable and reproducible without an LLM judge.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from ..memory.embeddings import cosine, embed


def _sentences(text: str) -> list[str]:
    """Split text into claim-like sentences."""
    parts = re.split(r"(?<=[.!?;])\s+|\n+", (text or "").strip())
    return [p.strip() for p in parts if len(p.strip()) > 3]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _max_sim(claim: str, pool: list[str]) -> float:
    if not pool:
        return 0.0
    cv = embed(claim)
    return _clamp01(max(cosine(cv, embed(p)) for p in pool))


def _mean(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 4) if xs else 0.0


def context_precision(question: str, contexts: list[str], ground_truth: str) -> float:
    """Mean relevance of each retrieved context to the question+ground-truth."""
    target = f"{question} {ground_truth}"
    tv = embed(target)
    if not contexts:
        return 0.0
    return _mean([_clamp01(cosine(tv, embed(c))) for c in contexts])


def context_recall(contexts: list[str], ground_truth: str) -> float:
    """Fraction (as mean-of-max sim) of ground-truth claims covered by the contexts."""
    claims = _sentences(ground_truth)
    return _mean([_max_sim(c, contexts) for c in claims])


def faithfulness(answer: str, contexts: list[str]) -> float:
    """How grounded the answer claims are in the retrieved contexts (anti-hallucination)."""
    claims = _sentences(answer)
    return _mean([_max_sim(c, contexts) for c in claims])


def answer_relevancy(question: str, answer: str) -> float:
    """How well the answer addresses the question (embedding cosine)."""
    if not answer.strip():
        return 0.0
    return round(_clamp01(cosine(embed(question), embed(answer))), 4)


def generate_answer(question: str, contexts: list[str]) -> tuple[str, str]:
    """Produce an answer from the retrieved contexts.

    Returns (answer, mode). Uses Gemini when a key is configured; otherwise a deterministic
    extractive answer (most-relevant context sentences), so evaluation runs offline too.
    """
    joined = "\n".join(f"- {c}" for c in contexts)
    try:
        from ..llm import LLMUnavailable, chat_text

        try:
            system = (
                "You are a care-coordination assistant. Answer the question using ONLY the provided "
                "care-pathway/triage-guideline context. Be concise and non-diagnostic. If the context "
                "does not cover it, say so."
            )
            answer = chat_text(
                f"Context:\n{joined}\n\nQuestion: {question}\n\nAnswer:",
                system=system, temperature=0.0,
            )
            return answer.strip(), "gemini_llm"
        except LLMUnavailable:
            pass
    except Exception:
        pass

    # Deterministic extractive fallback: rank context sentences by similarity to the question.
    pool = [s for c in contexts for s in _sentences(c)]
    if not pool:
        return "", "offline_deterministic_fallback"
    qv = embed(question)
    ranked = sorted(pool, key=lambda s: cosine(qv, embed(s)), reverse=True)
    return " ".join(ranked[:2]), "offline_deterministic_fallback"


@dataclass
class RagEvalResult:
    id: str
    question: str
    retrieved_sources: list[str]
    expected_source: str
    expected_source_retrieved: bool
    answer: str
    answer_mode: str
    context_precision: float
    context_recall: float
    faithfulness: float
    answer_relevancy: float

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate_item(item: dict, retriever, *, k: int = 3) -> RagEvalResult:
    """Evaluate one eval-set item end-to-end: retrieve -> generate -> score."""
    question = item["question"]
    hits = retriever(question, k=k)
    contexts = [h["text"] for h in hits]
    sources = [h["source"] for h in hits]
    gt = item.get("ground_truth", "")
    answer, mode = generate_answer(question, contexts)
    return RagEvalResult(
        id=item["id"],
        question=question,
        retrieved_sources=sources,
        expected_source=item.get("expected_source", ""),
        expected_source_retrieved=item.get("expected_source", "") in sources,
        answer=answer,
        answer_mode=mode,
        context_precision=context_precision(question, contexts, gt),
        context_recall=context_recall(contexts, gt),
        faithfulness=faithfulness(answer, contexts),
        answer_relevancy=answer_relevancy(question, answer),
    )


def aggregate(results: list[RagEvalResult]) -> dict:
    """Mean of each metric across all evaluated items + retrieval hit-rate."""
    if not results:
        return {}
    keys = ["context_precision", "context_recall", "faithfulness", "answer_relevancy"]
    agg = {k: _mean([getattr(r, k) for r in results]) for k in keys}
    agg["retrieval_hit_rate"] = _mean([1.0 if r.expected_source_retrieved else 0.0 for r in results])
    agg["n_items"] = len(results)
    return agg
