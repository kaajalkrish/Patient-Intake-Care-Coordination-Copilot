# Agentic-RAG Evaluation (RAGAS-style)

- generated_at: 2026-09-12T15:38:21
- mode: gemini_llm
- items evaluated: 5

## Aggregate metrics (mean, 0-1)

| metric | score |
|--------|-------|
| context precision | 0.4306 |
| context recall | 0.6171 |
| faithfulness | 0.7977 |
| answer relevancy | 0.6063 |
| retrieval hit-rate (expected source in top-3) | 1.0 |

## Per-item

| id | expected source retrieved | ctx_prec | ctx_recall | faithful | ans_rel |
|----|:-:|:-:|:-:|:-:|:-:|
| eval-chest-pain | yes | 0.4388 | 0.6058 | 0.7193 | 0.5914 |
| eval-mental-health | yes | 0.4299 | 0.5265 | 0.8251 | 0.5808 |
| eval-dermatology | yes | 0.436 | 0.5287 | 0.8223 | 0.5581 |
| eval-urgency-bands | yes | 0.4118 | 0.6298 | 0.7507 | 0.7131 |
| eval-referral-scope | yes | 0.4366 | 0.7948 | 0.8713 | 0.5881 |

_Coordination aid only — not medical advice. All data synthetic._