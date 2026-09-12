"""Run the RAGAS-style evaluation of the agentic-RAG tool and commit the report.

Retrieves care-pathway/triage-guideline passages for each eval question, generates an answer
(Gemini when keyed, deterministic otherwise), and scores context_precision, context_recall,
faithfulness and answer_relevancy. Writes:

  evidence/ragas_report.json   - full per-item + aggregate metrics
  evidence/ragas_report.md     - human-readable summary table

Usage:  python -m scripts.run_ragas_eval
All data is synthetic; the answer text is PII-free coordination guidance.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from src.config import settings
from src.rag.evaluation import aggregate, evaluate_item
from src.rag.retriever import care_pathway_lookup, reset_index

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = REPO_ROOT / "evidence"
EVAL_SET = REPO_ROOT / "data" / "synthetic" / "rag_eval_set.json"


def run() -> dict:
    reset_index()
    eval_set = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    results = [evaluate_item(item, care_pathway_lookup, k=3) for item in eval_set["items"]]
    agg = aggregate(results)
    return {
        "description": "AC-11 agentic-RAG quality — RAGAS-style metrics (self-contained; the ragas "
                       "package is incompatible with the pinned langchain 1.x stack). "
                       "Metrics are embedding-based means in [0,1].",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "mode": "gemini_llm" if settings.has_api_key else "offline_deterministic_fallback",
        "aggregate": agg,
        "items": [r.as_dict() for r in results],
    }


def _md(report: dict) -> str:
    a = report["aggregate"]
    lines = [
        "# Agentic-RAG Evaluation (RAGAS-style)",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- mode: {report['mode']}",
        f"- items evaluated: {a.get('n_items')}",
        "",
        "## Aggregate metrics (mean, 0-1)",
        "",
        "| metric | score |",
        "|--------|-------|",
        f"| context precision | {a.get('context_precision')} |",
        f"| context recall | {a.get('context_recall')} |",
        f"| faithfulness | {a.get('faithfulness')} |",
        f"| answer relevancy | {a.get('answer_relevancy')} |",
        f"| retrieval hit-rate (expected source in top-3) | {a.get('retrieval_hit_rate')} |",
        "",
        "## Per-item",
        "",
        "| id | expected source retrieved | ctx_prec | ctx_recall | faithful | ans_rel |",
        "|----|:-:|:-:|:-:|:-:|:-:|",
    ]
    for it in report["items"]:
        lines.append(
            f"| {it['id']} | {'yes' if it['expected_source_retrieved'] else 'NO'} | "
            f"{it['context_precision']} | {it['context_recall']} | "
            f"{it['faithfulness']} | {it['answer_relevancy']} |"
        )
    lines += ["", "_Coordination aid only — not medical advice. All data synthetic._"]
    return "\n".join(lines)


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    report = run()
    (EVIDENCE / "ragas_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (EVIDENCE / "ragas_report.md").write_text(_md(report), encoding="utf-8")
    a = report["aggregate"]
    print(f"RAGAS-style eval ({report['mode']}): "
          f"ctx_prec={a['context_precision']} ctx_recall={a['context_recall']} "
          f"faithfulness={a['faithfulness']} ans_rel={a['answer_relevancy']} "
          f"hit_rate={a['retrieval_hit_rate']}")
    print("  evidence/ragas_report.json")
    print("  evidence/ragas_report.md")


if __name__ == "__main__":
    main()
