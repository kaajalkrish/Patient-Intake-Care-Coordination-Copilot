# Agentic-RAG Evaluation — OFFICIAL ragas

**Status: verified working (partial run); full run blocked by free-tier daily quota.**

- ragas version: **0.2.15** (isolated `.venv-ragas`; ragas is incompatible with the project's pinned
  langchain 1.x stack, so it runs in its own venv)
- judge LLM: **gemini-3.6-flash**
- embeddings: **sentence-transformers/all-MiniLM-L6-v2** (local, no quota)

## Verified partial run (2 items) — real ragas output

| metric | score |
|--------|-------|
| llm_context_precision_with_reference | 1.0 |
| context_recall | 0.5 |
| faithfulness | 1.0 |
| answer_relevancy | _not captured in this run (Gemini embedding 404; runner since switched to local embeddings)_ |

This proves the official ragas pipeline works end-to-end against our dataset.

## Why the full 5-item run didn't finish today

Google Gemini's **free tier allows only 20 generate-requests per day, per model**
(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`). A full 5-item × 4-metric ragas run needs
dozens of judge calls, and the day's quota across `gemini-3.5/3.6/3.8-flash` was consumed by the app,
evidence capture, and eval attempts.

**To complete the full run:**

```bash
# after the daily quota resets, from the isolated venv:
RAGAS_JUDGE_MODEL=gemini-3.6-flash .venv-ragas/Scripts/python.exe scripts/run_official_ragas.py
```

Or use a paid/higher-quota Gemini key.

## Reproducible alternative (no quota)

The self-contained RAGAS-style evaluator computes the same four metrics on local embeddings with **no
LLM quota dependency** — see [`ragas_report.md`](ragas_report.md) (hit-rate 1.0, faithfulness ~0.80).

_All data synthetic; coordination aid only — not medical advice._
