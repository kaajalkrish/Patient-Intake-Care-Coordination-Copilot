# Traceability Matrix (AC-Traceability Rule)

Every Acceptance Criterion and Non-Functional Requirement maps to at least one committed test and/or
evidence artifact carrying its identifier. This is the "don't miss a single criterion" guard.

## Functional Acceptance Criteria

| AC | Requirement (short) | Test(s) | Evidence artifact |
|----|---------------------|---------|-------------------|
| AC-01 | Typed LangGraph state | `tests/test_ac01_typed_state.py` | `src/state.py` |
| AC-02 | Supervisor routes to workers | `tests/test_ac02_supervisor_routing.py` | `evidence/run_transcript.json` |
| AC-03 | Conditional edges on state | `tests/test_ac03_conditional_routing.py` | `evidence/run_transcript.json` |
| AC-04 | Pydantic structured output at handoffs | `tests/test_ac04_structured_output.py` | `src/schemas.py` |
| AC-05 | Checkpointer pause/resume | `tests/test_ac05_checkpoint_resume.py` | — |
| AC-06 | Tiered memory + recall | `tests/test_ac06_tiered_memory.py` | — |
| AC-07 | Cross-session persistence | `tests/test_ac07_cross_session_memory.py` | `evidence/memory_persistence_log.txt` |
| AC-08 | Eviction / importance policy | `tests/test_ac08_eviction_policy.py` | `docs/memory-design.md` |
| AC-09 | MCP server ≥2 tools + 1 resource | `tests/test_ac09_mcp_server_surface.py` | — |
| AC-10 | Adapter integration + tool-call log | `tests/test_ac10_mcp_adapter.py` | `evidence/mcp_toolcall_transcript.json` |
| AC-11 | Agentic RAG (agent decides) | `tests/test_ac11_agentic_rag.py`, `tests/test_deep_ac11_rag.py`, `tests/test_deep_ac11_ragas_quality.py` | `evidence/rag_trace.json`, `evidence/ragas_report.json`, `evidence/ragas_report.md` |
| AC-12 | Reflection / self-healing | `tests/test_ac12_reflection_selfhealing.py` | `evidence/reflection_trace.json` |

## Non-Functional Requirements

| NFR | Requirement (short) | Test(s) | Evidence artifact |
|-----|---------------------|---------|-------------------|
| NFR-01 | No committed secrets | `tests/test_nfr01_no_secrets.py` | `.env.example`, `.gitignore` |
| NFR-02 | Single-command run | `tests/test_nfr02_single_command_run.py` | `README.md`, `data/sample_intakes/` |
| NFR-03 | Context quarantine | `tests/test_nfr03_context_quarantine.py` | `docs/context-engineering.md` |
| NFR-04 | JSON traces committed | `tests/test_nfr04_json_traces.py` | `evidence/*.json` |
| NFR-05 | Synthetic data + PII redaction | `tests/test_nfr05_synthetic_pii_redaction.py` | `evidence/*` (redacted) |
| NFR-06 | Decision docs w/ rationale | `tests/test_nfr06_decision_docs.py` | `docs/single-vs-multi-decision.md`, `docs/integration-decision.md` |
| NFR-07 | Graceful degradation | `tests/test_nfr07_graceful_degradation.py` | `evidence/reflection_trace.json` |
| NFR-08 | Summarization/compression | `tests/test_nfr08_summarization.py` | `docs/context-engineering.md` |

## Rubric category → evidence

| Category (marks) | Primary evidence |
|------------------|------------------|
| Business & Requirements (10) | `docs/business-case.md`, `docs/acceptance-criteria.md`, `docs/single-vs-multi-decision.md` |
| Agent Architecture & LangGraph (24) | `src/graph.py`, `src/state.py`, `src/schemas.py`, AC-01..05 tests |
| Patterns & Multi-Agent (18) | `src/agents/`, `evidence/run_transcript.json`, `evidence/reflection_trace.json` |
| Context Engineering (12) | `docs/context-engineering.md`, `src/context/`, NFR-03/08 tests |
| Memory Systems (14) | `src/memory/`, `evidence/memory_persistence_log.txt`, AC-06..08 tests |
| MCP & Interoperability (14) | `src/mcp/`, `evidence/mcp_toolcall_transcript.json`, `docs/integration-decision.md` |
| Agentic RAG & Reproducibility (8) | `src/rag/`, `evidence/rag_trace.json`, `evidence/ragas_report.md`, `README.md` |

## Exhaustive test layer (defense-in-depth for automated scoring)

Beyond the one-test-per-AC baseline, deep multi-case and meta tests assert both that every criterion
*works* (happy/edge/failure/boundary) and that every gradeable *artifact and keyword* exists — so both
LLM-judged and deterministic (presence/threshold) rubric parameters are covered.

| Test file | Purpose |
|-----------|---------|
| `tests/test_meta_rubric_evidence.py` | Every required file, doc section, keyword, evidence artifact, secret-hygiene & pin exists (all 7 categories) |
| `tests/test_meta_git_history.py` | ≥3 true `--no-ff` PR merges; feature branches present |
| `tests/test_meta_traceability.py` | Every AC-NN/NFR-NN referenced + has a dedicated test + listed here |
| `tests/test_deep_ac01_state.py` | Typed state init, reducers, quarantine isolation |
| `tests/test_deep_ac0203_routing.py` | Full urgency×scope routing matrix + ordered end-to-end routes |
| `tests/test_deep_ac04_schemas.py` | Pydantic validation raises/passes; every validator; enum/bounds |
| `tests/test_deep_ac060708_memory.py` | Tiered recall, cross-session persistence, TTL/LRU/importance eviction |
| `tests/test_deep_ac0910_mcp.py` | Each MCP tool + edge cases + resource read |
| `tests/test_deep_ac11_rag.py` | Retrieval relevance per condition, k-limit, ranking |
| `tests/test_deep_ac11_ragas_quality.py` | RAGAS-style quality gate (precision/recall/faithfulness/relevancy) |
| `tests/test_deep_ac12_reflection.py` | guard retry/recover/fallback; reflection re-plan |
| `tests/test_deep_nfr03_quarantine.py` | 11 prompt-injection payloads + neutralization + fenced prompt |
| `tests/test_deep_nfr08_summarization.py` | Threshold, keep-recent, LLM + fallback compression |
