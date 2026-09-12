"""DEEP AC-11: agentic-RAG care-pathway / triage-guideline retrieval — exhaustive.

The retriever indexes data/synthetic/guidelines/ and returns top-k relevant passages. "Agentic" =
the agent decides when to call it (bound as a tool); here we test the retrieval tool's correctness and
relevance so the agent's decision has a sound backend.
"""
from __future__ import annotations

import pytest

from src.rag.retriever import care_pathway_lookup, reset_index


@pytest.fixture(autouse=True)
def _fresh_index():
    reset_index()
    yield
    reset_index()


def test_returns_structured_hits():
    hits = care_pathway_lookup("chest pain triage", k=3)
    assert hits, "no passages retrieved"
    for h in hits:
        assert {"id", "source", "text", "score"} <= set(h)
        assert isinstance(h["score"], float)


def test_k_limits_result_count():
    assert len(care_pathway_lookup("urgency", k=1)) <= 1
    assert len(care_pathway_lookup("urgency", k=2)) <= 2


@pytest.mark.parametrize("query,expected_source_fragment", [
    ("crushing chest pain radiating to the arm", "chest_pain"),
    ("feeling hopeless and low mood", "mental_health"),
    ("itchy rash on the skin", "dermatology"),
])
def test_relevant_guideline_ranks_in_topk(query, expected_source_fragment):
    hits = care_pathway_lookup(query, k=3)
    sources = " ".join(h["source"] for h in hits)
    assert expected_source_fragment in sources, (
        f"expected a '{expected_source_fragment}' guideline in top-3 for {query!r}, got {sources}"
    )


def test_scores_sorted_descending():
    hits = care_pathway_lookup("triage urgency red flags", k=5)
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)
