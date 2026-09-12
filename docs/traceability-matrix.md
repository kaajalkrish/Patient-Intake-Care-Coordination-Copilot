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
| AC-11 | Agentic RAG (agent decides) | `tests/test_ac11_agentic_rag.py` | `evidence/rag_trace.json` |
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
| Agentic RAG & Reproducibility (8) | `src/rag/`, `evidence/rag_trace.json`, `README.md` |
