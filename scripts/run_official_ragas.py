"""Run the OFFICIAL `ragas` library against the exported dataset (isolated .venv-ragas only).

This must be run with the isolated interpreter, NOT the project venv:

    .venv-ragas/Scripts/python.exe scripts/run_official_ragas.py

It reads evidence/ragas_dataset.json (produced by scripts.export_ragas_dataset in the main venv) and
scores it with real ragas metrics using Google Gemini as the judge LLM and Gemini embeddings. Writes
evidence/ragas_official_report.json + .md.

Requires GOOGLE_API_KEY in the environment / .env.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATASET = REPO / "evidence" / "ragas_dataset.json"
OUT_JSON = REPO / "evidence" / "ragas_official_report.json"
OUT_MD = REPO / "evidence" / "ragas_official_report.md"


def _load_env() -> None:
    """Load GOOGLE_API_KEY and GEMINI_MODEL from .env if not already in the environment."""
    env = REPO / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _load_key() -> str:
    _load_env()
    key = os.getenv("GOOGLE_API_KEY", "")
    if not key or key == "your-gemini-api-key-here":
        raise SystemExit("GOOGLE_API_KEY not set; official ragas needs a Gemini judge LLM.")
    os.environ["GOOGLE_API_KEY"] = key
    return key


def main() -> None:
    key = _load_key()
    # Judge model override with RAGAS_JUDGE_MODEL / GEMINI_MODEL. gemini-3.6-flash is the current
    # non-retired flash model; free-tier daily caps are tiny so keep the item count small.
    model = os.getenv("RAGAS_JUDGE_MODEL") or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    max_items = int(os.getenv("RAGAS_ITEMS", "0"))  # 0 = all

    import ragas
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas import EvaluationDataset, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )
    from ragas.run_config import RunConfig

    rows = json.loads(DATASET.read_text(encoding="utf-8"))["rows"]
    if max_items:
        rows = rows[:max_items]
    samples = [{
        "user_input": r["user_input"],
        "retrieved_contexts": r["retrieved_contexts"],
        "response": r["response"],
        "reference": r["reference"],
    } for r in rows]
    dataset = EvaluationDataset.from_list(samples)

    llm = LangchainLLMWrapper(ChatGoogleGenerativeAI(
        model=model, google_api_key=key, temperature=0.0))
    # Local open-source embeddings for answer_relevancy — no Gemini embedding quota, reproducible,
    # and matches the project's own embedding backend (all-MiniLM-L6-v2).
    emb = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"))

    metrics = [
        LLMContextPrecisionWithReference(llm=llm),
        LLMContextRecall(llm=llm),
        Faithfulness(llm=llm),
        ResponseRelevancy(llm=llm, embeddings=emb),
    ]

    # Serialize calls and back off generously to respect free-tier rate/day limits.
    run_config = RunConfig(max_workers=1, timeout=180, max_retries=5, max_wait=90)
    result = evaluate(dataset=dataset, metrics=metrics, llm=llm, embeddings=emb,
                      run_config=run_config)
    df = result.to_pandas()

    metric_cols = [c for c in df.columns
                   if c not in {"user_input", "retrieved_contexts", "response", "reference"}]
    aggregate = {c: round(float(df[c].mean()), 4) for c in metric_cols}

    report = {
        "description": "Official ragas evaluation of the agentic-RAG tool. Judge LLM: Google Gemini. "
                       "Run from the isolated .venv-ragas (ragas is incompatible with the project's "
                       "pinned langchain 1.x stack).",
        "ragas_version": getattr(ragas, "__version__", "unknown"),
        "judge_model": model,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2 (local)",
        "n_items": len(rows),
        "aggregate": aggregate,
        "per_item": [
            {"id": rows[i]["id"], **{c: (round(float(df.iloc[i][c]), 4)
                                        if isinstance(df.iloc[i][c], (int, float)) else df.iloc[i][c])
                                     for c in metric_cols}}
            for i in range(len(rows))
        ],
    }
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Agentic-RAG Evaluation (OFFICIAL ragas)",
        "",
        f"- ragas version: {report['ragas_version']}",
        f"- judge model: {model}",
        "",
        "## Aggregate (mean, 0-1)",
        "",
        "| metric | score |",
        "|--------|-------|",
    ]
    for k, v in aggregate.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "_Judged by Google Gemini. All data synthetic; coordination aid only._"]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print("ragas", report["ragas_version"], "->", aggregate)
    print(f"  {OUT_JSON}")
    print(f"  {OUT_MD}")


if __name__ == "__main__":
    main()
