"""Export a ragas-ready evaluation dataset from the live RAG pipeline (main venv).

Produces evidence/ragas_dataset.json: for each eval question, the retrieved contexts, the generated
answer (Gemini when keyed), and the ground-truth reference. The official `ragas` library is then run
against this dataset from the isolated .venv-ragas (see scripts/run_official_ragas.py), because ragas
is incompatible with this project's pinned langchain 1.x stack.

Usage:  python -m scripts.export_ragas_dataset
"""
from __future__ import annotations

import json
from pathlib import Path

from src.config import settings
from src.rag.evaluation import generate_answer
from src.rag.retriever import care_pathway_lookup, reset_index

REPO = Path(__file__).resolve().parents[1]
EVAL_SET = REPO / "data" / "synthetic" / "rag_eval_set.json"
OUT = REPO / "evidence" / "ragas_dataset.json"


def main() -> None:
    reset_index()
    items = json.loads(EVAL_SET.read_text(encoding="utf-8"))["items"]
    rows = []
    for it in items:
        q = it["question"]
        hits = care_pathway_lookup(q, k=3)
        contexts = [h["text"] for h in hits]
        answer, mode = generate_answer(q, contexts)
        rows.append({
            "id": it["id"],
            "user_input": q,
            "retrieved_contexts": contexts,
            "response": answer,
            "reference": it.get("ground_truth", ""),
            "answer_mode": mode,
        })
    OUT.write_text(json.dumps({
        "mode": "gemini_llm" if settings.has_api_key else "offline_deterministic_fallback",
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} rows, mode={'gemini_llm' if settings.has_api_key else 'offline'})")


if __name__ == "__main__":
    main()
