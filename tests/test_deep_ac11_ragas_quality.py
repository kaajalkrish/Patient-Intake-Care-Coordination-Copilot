"""DEEP AC-11: RAGAS-style quality gate for the agentic-RAG tool.

Runs the self-contained RAGAS-style evaluator (context precision/recall, faithfulness, answer
relevancy) over the synthetic eval set and asserts the RAG pipeline clears sane quality floors. Runs
in deterministic offline mode under conftest, so it is fully reproducible without an API key.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.rag.evaluation import (
    aggregate,
    answer_relevancy,
    context_precision,
    context_recall,
    evaluate_item,
    faithfulness,
)
from src.rag.retriever import care_pathway_lookup, reset_index

REPO = Path(__file__).resolve().parents[1]
EVAL_SET = json.loads((REPO / "data" / "synthetic" / "rag_eval_set.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _fresh_index():
    reset_index()
    yield
    reset_index()


@pytest.fixture(scope="module")
def results():
    reset_index()
    return [evaluate_item(item, care_pathway_lookup, k=3) for item in EVAL_SET["items"]]


# ---- metric unit behavior ----

def test_metrics_bounded_0_1():
    ctx = ["chest pain radiating to the arm is an emergent red flag; direct to emergency care"]
    assert 0.0 <= context_precision("chest pain triage", ctx, "emergent, go to ED") <= 1.0
    assert 0.0 <= context_recall(ctx, "chest pain is emergent") <= 1.0
    assert 0.0 <= faithfulness("go to the ED immediately", ctx) <= 1.0
    assert 0.0 <= answer_relevancy("how to triage chest pain?", "direct to emergency care") <= 1.0


def test_empty_answer_has_zero_relevancy():
    assert answer_relevancy("any question", "") == 0.0


def test_faithful_answer_scores_higher_than_unrelated():
    ctx = ["Self-harm reports are urgent; escalate for same-day mental-health assessment."]
    grounded = faithfulness("Escalate for a same-day mental-health assessment.", ctx)
    hallucinated = faithfulness("Prescribe antibiotics and schedule surgery next month.", ctx)
    assert grounded > hallucinated


# ---- pipeline quality gates (retrieve -> generate -> score) ----

def test_every_expected_source_is_retrieved(results):
    misses = [r.id for r in results if not r.expected_source_retrieved]
    assert not misses, f"expected guideline not retrieved in top-3 for: {misses}"


def test_aggregate_quality_floors(results):
    agg = aggregate(results)
    assert agg["retrieval_hit_rate"] >= 0.8
    assert agg["faithfulness"] >= 0.5, agg
    assert agg["context_recall"] >= 0.3, agg
    assert agg["answer_relevancy"] >= 0.2, agg


def test_every_item_produces_an_answer(results):
    for r in results:
        assert r.answer.strip(), f"no answer generated for {r.id}"
