# Acceptance Criteria & Non-Functional Requirements (testable form)

Every criterion below is **testable** and carries an **AC-NN / NFR-NN** identifier. Each is referenced
by at least one pytest and/or a committed evidence artifact — see
[traceability-matrix.md](traceability-matrix.md) for the full mapping (AC-Traceability Rule).

Test files reference their AC id in the filename and in a module docstring, e.g.
`tests/test_ac01_typed_state.py` begins with `"""AC-01: ..."""`.

---

## Functional Acceptance Criteria

| ID | Criterion | Given / When / Then | Test / Evidence |
|----|-----------|---------------------|-----------------|
| **AC-01** | Built on LangGraph with an explicit **typed state** object (TypedDict/Pydantic) shared across nodes. | *Given* the compiled graph, *when* we inspect its state schema, *then* it is a typed object with the intake fields and is the same type read/written by every node. | `test_ac01_typed_state.py` |
| **AC-02** | A **supervisor** routes a patient intake request to specialized workers (triage, scheduling, referral, follow-up). | *Given* an intake request, *when* the graph runs, *then* the supervisor node executes first and dispatches to the named worker nodes. | `test_ac02_supervisor_routing.py` + `evidence/run_transcript.json` |
| **AC-03** | The graph uses **conditional edges** to route on state (urgent → expedited scheduling; out-of-scope → specialist referral). | *Given* an `emergent` intake, *when* routed, *then* it takes the expedited path; *given* an out-of-scope need, *then* a referral is produced. | `test_ac03_conditional_routing.py` |
| **AC-04** | Node/agent outputs are **validated structured objects (Pydantic)** at handoff boundaries. | *Given* each worker's output, *when* handed off, *then* it validates against a Pydantic model; invalid output raises. | `test_ac04_structured_output.py` |
| **AC-05** | A **checkpointer** persists graph state so an intake case can be **paused and resumed**. | *Given* a run interrupted mid-graph, *when* resumed with the same thread id, *then* prior state is restored and the run continues. | `test_ac05_checkpoint_resume.py` |
| **AC-06** | **Tiered memory** (short-term working + long-term/semantic); recalls a fact from an earlier turn. | *Given* a fact stated in turn 1, *when* asked in a later turn of the same session, *then* the fact is recalled. | `test_ac06_tiered_memory.py` |
| **AC-07** | **Memory persists across sessions**: a committed test starts a new session and recalls prior-session facts; its output log is committed. | *Given* a fact stored in session A, *when* a brand-new session B starts, *then* the fact is recalled from persistent store. | `test_ac07_cross_session_memory.py` + `evidence/memory_persistence_log.txt` |
| **AC-08** | A memory **eviction / importance policy** (TTL, LRU, or importance-weighted) implemented and documented. | *Given* memory over capacity or past TTL, *when* the policy runs, *then* low-importance/expired items are evicted, high-importance retained. | `test_ac08_eviction_policy.py` + [memory-design.md](memory-design.md) |
| **AC-09** | A **custom MCP server** exposes **≥2 tools and 1 resource** relevant to the domain. | *Given* the MCP server, *when* listed, *then* ≥2 tools and ≥1 resource are advertised (patient_lookup, appointment_slots, care_pathway; care_coordination_manual resource). | `test_ac09_mcp_server_surface.py` |
| **AC-10** | The agent consumes the MCP server via **langchain-mcp-adapters**; a committed transcript shows an MCP tool invocation. | *Given* the agent wired to MCP, *when* it needs a clinic tool, *then* it invokes an MCP tool and the call+result are logged. | `test_ac10_mcp_adapter.py` + `evidence/mcp_toolcall_transcript.json` |
| **AC-11** | An **agentic-RAG tool** is available and the agent **decides when to call it** for care-pathway/triage-guideline lookups (retrieval inside the loop, not a fixed step). | *Given* a query needing guidelines, *when* the agent runs, *then* it chooses to call the RAG tool and grounds its output in retrieved passages; for a trivial query it may skip retrieval. | `test_ac11_agentic_rag.py` + `evidence/rag_trace.json` |
| **AC-12** | A **reflection / self-healing / fallback loop** (re-plan on tool failure or low-confidence) with an evidenced trace. | *Given* a tool failure or low-confidence output, *when* detected, *then* the graph re-plans/retries/falls back and records the recovery in a trace. | `test_ac12_reflection_selfhealing.py` + `evidence/reflection_trace.json` |

---

## Non-Functional Requirements

| ID | Requirement | Test / Evidence |
|----|-------------|-----------------|
| **NFR-01** | No secrets/API keys committed; env-var config with committed `.env.example`. | `test_nfr01_no_secrets.py` + `.env.example` + `.gitignore` |
| **NFR-02** | Runs end-to-end from a **single documented command** with committed sample inputs + README quick-start. | `test_nfr02_single_command_run.py` + `README.md` + `data/sample_intakes/` |
| **NFR-03** | Untrusted patient free-text is **isolated (quarantine)** and never trusted as instructions. | `test_nfr03_context_quarantine.py` + [context-engineering.md](context-engineering.md) |
| **NFR-04** | Structured JSON logs / traces of agent runs committed as evidence. | `test_nfr04_json_traces.py` + `evidence/*.json` |
| **NFR-05** | All data synthetic; any PII synthetic and never written to logs in plaintext. | `test_nfr05_synthetic_pii_redaction.py` |
| **NFR-06** | Single-vs-multi decision and framework choice documented with rationale. | [single-vs-multi-decision.md](single-vs-multi-decision.md) + `test_nfr06_decision_docs.py` |
| **NFR-07** | Graceful degradation on tool/model failure: timeouts, retries, explicit exit conditions. | `test_nfr07_graceful_degradation.py` |
| **NFR-08** | Context-window management: summarization/compression applied for long threads. | `test_nfr08_summarization.py` |
