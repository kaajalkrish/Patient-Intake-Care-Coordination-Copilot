# Patient Intake & Care-Coordination Copilot — Multi-Agent

**Business Case:** AAIE_AGT_008_HLC · Healthcare — Care Coordination
**Stack:** Python 3.11+ · LangGraph · Google Gemini · MCP (Python SDK + langchain-mcp-adapters) ·
SQLite checkpointer · Chroma / Sentence-Transformers · LangMem

A stateful **multi-agent** copilot that triages a patient intake request, schedules the right
appointment, arranges referrals, and sets up follow-up — carrying context across a multi-turn,
multi-session care journey. **Coordination aid only — not a diagnostic tool. All data is synthetic.**

```
        ┌──────────┐     ┌────────────┐   conditional routing on state
 intake │ quarantine│ →  │ supervisor │ ─────────────┬───────────┬───────────┐
  req   │  + recall │    └────────────┘              ▼           ▼           ▼
        └──────────┘        ▲   ▲   ▲            ┌────────┐  ┌────────┐  ┌────────┐
                            │   │   └────────────│ triage │  │schedule│  │referral│ ...
                            │   └─── reflection ◀┘(RAG?)  │  └────────┘  └────────┘
                            └──────────── loop back to supervisor ──────────┘ → finalize
```

## Quick start

```bash
# 1. Create a virtual environment (use a path OUTSIDE any OneDrive-synced folder on Windows)
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  macOS/Linux:  source .venv/bin/activate

# 2. Install
pip install -r requirements.txt

# 3. Configure the LLM key (free tier: https://aistudio.google.com/apikey)
cp .env.example .env        # then edit .env and set GOOGLE_API_KEY

# 4. Generate the synthetic data (patients, slots, care pathways, guidelines, sample intakes)
python -m scripts.generate_synthetic_data

# 5. Run the copilot on a committed sample — the single documented command:
python main.py --sample emergent_chest_pain
```

Other run options:

```bash
python main.py --list-samples                       # list committed sample intakes
python main.py --patient SYN-1001 --text "mild cough since yesterday"
python -m scripts.capture_evidence                  # regenerate all evidence artifacts
python -m scripts.run_ragas_eval                    # RAGAS-style agentic-RAG quality report
python -m scripts.run_comparison                    # single-agent vs multi-agent comparison
streamlit run ui/streamlit_app.py                   # optional UI (routing + memory view)
```

> **No key? It still runs.** Without `GOOGLE_API_KEY` the agents fall back to deterministic clinical
> heuristics (graceful degradation, NFR-07), so the whole system and test suite are fully reproducible
> offline. With a key, the triage agent uses Gemini for classification and the agentic-RAG decision.

## Tests

```bash
pytest -q                      # full suite (offline-safe; LLM-only tests auto-skip without a key)
pytest tests/test_ac07_cross_session_memory.py -q    # e.g. cross-session memory proof
pytest tests/test_meta_traceability.py -q            # every AC/NFR is referenced + tested
```

The suite has two layers: **one test per AC/NFR** (the baseline mapping) plus an **exhaustive layer**
of `test_deep_*` (multi-case happy/edge/failure/boundary) and `test_meta_*` tests. The meta tests
assert that every gradeable artifact, doc section, keyword, threshold and the PR-driven git history
physically exist in the repo — covering both the LLM-judged and the deterministic (presence/threshold)
rubric parameters. Every Acceptance Criterion (AC-NN) and NFR maps to a test and/or evidence
artifact — see [docs/traceability-matrix.md](docs/traceability-matrix.md).

> **RAGAS-style RAG evaluation.** `python -m scripts.run_ragas_eval` scores the agentic-RAG tool on
> context precision/recall, faithfulness and answer relevancy → `evidence/ragas_report.{json,md}`.
> The `ragas` package hard-depends on a removed `langchain_community` path and is incompatible with the
> pinned langchain 1.x stack, so the metrics are implemented self-contained on local embeddings (no
> extra dependency, runs offline).

## What's inside

| Area | Where |
|------|-------|
| Typed state / graph (AC-01–05) | [src/state.py](src/state.py), [src/graph.py](src/graph.py), [src/schemas.py](src/schemas.py) |
| Supervisor + workers | [src/agents/](src/agents/) |
| Tiered memory + eviction (AC-06–08) | [src/memory/](src/memory/) |
| Custom MCP servers + adapter (AC-09–10) | [src/mcp/](src/mcp/) |
| Context engineering (quarantine/compress) | [src/context/](src/context/) |
| Agentic RAG (AC-11) | [src/rag/](src/rag/) |
| Reflection / self-healing (AC-12) | [src/reflection.py](src/reflection.py) |
| Committed evidence | [evidence/](evidence/) |
| Design docs | [docs/](docs/) |

## Documentation

- [Business case](docs/business-case.md) · [Acceptance criteria](docs/acceptance-criteria.md)
- [Single-vs-multi & framework decision](docs/single-vs-multi-decision.md)
- [Context engineering](docs/context-engineering.md) · [Memory design](docs/memory-design.md)
- [Integration decision (MCP vs API vs DB vs A2A)](docs/integration-decision.md)
- [Traceability matrix](docs/traceability-matrix.md)

## Rules honored

Synthetic data only · no committed secrets · single-command reproducible run · AC-traceability ·
context isolation of untrusted patient text · open-source stack, pip + Python, **no Docker, no external
DB service**.
