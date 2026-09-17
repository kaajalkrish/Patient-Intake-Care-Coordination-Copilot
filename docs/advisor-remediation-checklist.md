# Advisor Remediation Checklist

Tracks the 12 changes requested by the advisor after the rubric static-analysis review.
Root cause for most items: the course detector traces dataflow from `main.py` and cannot
"see" features implemented inside closures/lambdas in `build_graph()`, so it reports them as
*declared-only* / *not wired*. The fixes make the wiring statically traceable, add targeted
tests, emit explicit logs/traces, and expand two docs.

**Status legend:** ⬜ not started · 🟡 in progress · ✅ done

Every item has a dedicated, labeled test in
[`tests/test_advisor_remediation.py`](../tests/test_advisor_remediation.py) (functions prefixed
`test_itemNN_...`). Run just these with: `pytest tests/test_advisor_remediation.py -v`.

| # | Prio | Param | Category | Status | What to do | Test(s) — `test_advisor_remediation.py` |
|---|------|-------|----------|--------|------------|------------------------------------------|
| 1 | 1 | P10 Multi-Agent Orchestration | Agent Patterns & Multi-Agent | ✅ | (a) Make `main.py` clearly invoke the multi-agent graph so static analysis marks it *wired*. (b) Unit test asserting the supervisor hands off to ≥2 different workers based on input. | `test_item01_supervisor_hands_off_to_at_least_two_distinct_workers`, `test_item01_routing_differs_by_input`, `test_item01_main_entrypoint_wires_the_graph` |
| 2 | 2 | P21 Agentic-RAG Tool | Agentic RAG & Retrieval | ✅ | (a) Make the agentic-RAG tool call in triage traceable from a main entry point. (b) Unit test mocking the LLM in `_should_retrieve`, asserting `care_pathway_lookup` is/ isn't called accordingly. | `test_item02_rag_retrieves_when_llm_says_yes`, `test_item02_rag_skips_when_llm_says_no`, `test_item02_rag_call_is_reachable_from_a_run` |
| 3 | 3 | P04 Typed State Design | Agent Architecture & LangGraph | ✅ | (a) Investigate the *declared-only* report and fix wiring. (b) Ensure the state object is explicitly passed to and returned from every node so usage is undeniable to static analysis. | `test_item03_every_node_is_a_module_level_typed_function`, `test_item03_typed_state_flows_through_a_full_run` |
| 4 | 4 | P11 Reflection / Self-Healing Loop | Agent Patterns & Multi-Agent | ✅ | (a) Put the reflection node on an **active conditional edge** that can be statically traced. (b) Unit test forcing low confidence / tool failure to verify the reflection path is taken. | `test_item04_route_after_triage_is_confidence_gated`, `test_item04_graph_has_conditional_reflection_edge`, `test_item04_graph_takes_reflection_path_on_low_confidence` |
| 5 | 5 | P12 Write / Select / Compress / Isolate | Context Engineering | ✅ | (a) Trace/log showing `select` and `compress` being called in a run. (b) Entry point clearly invokes all four strategies. (c) Reconcile detector logic with `src/graph.py`. | `test_item05_all_four_strategies_fire_in_a_run`, `test_item05_strategy_functions_emit_events` |
| 6 | 6 | P13 Compression / Summarization Middleware | Context Engineering | ✅ | (a) Execution trace showing a long conversation compressed. (b) Explicit logging when summarization triggers. (c) Reconcile detector with `src/graph.py`. | `test_item06_long_thread_is_compressed`, `test_item06_short_thread_is_not_compressed` |
| 7 | 7 | P15 Tiered Memory | Memory Systems | ✅ | (a) Test/trace showing facts recalled from the persistent store across sessions. (b) Log memory-recall events. (c) Reconcile detector with `src/graph.py`. | `test_item07_fact_recalled_across_sessions`, `test_item07_recall_logs_event` |
| 8 | 8 | P17 Eviction / Importance Policy | Memory Systems | ✅ | (a) Add a graph node that writes important facts to long-term memory, triggering eviction. (b) Test forcing an eviction, asserting the right items were removed. (c) Log/trace showing eviction enforced. | `test_item08_memory_write_node_persists_and_evicts`, `test_item08_condition_outranks_smalltalk`, `test_item08_eviction_logs_event` |
| 9 | 9 | P07 Checkpointing / Persistence | Agent Architecture & LangGraph | ✅ | Name the saver explicitly (`SqliteSaver`) so durability is evident to static analysis. | `test_item09_checkpointer_is_named_sqlitesaver`, `test_item09_graph_compiles_with_checkpointer` |
| 10 | 10 | P22 Grounding, Citations & Corrective Retrieval | Agentic RAG & Retrieval | ✅ | (a) Wire the reflection node to be triggered by the `confidence` field of `TriageResult`. (b) Expand `src/rag/evaluation.py` with citation-accuracy tests. | `test_item10_citation_accuracy_metric`, `test_item10_triage_cites_a_retrieved_guideline`, `test_item10_evaluation_reports_citation_accuracy` |
| 11 | 11 | P03 Single-vs-Multi Justification | Business & Requirements | ✅ | Add a section to `docs/single-vs-multi-decision.md` on why LangGraph over other multi-agent frameworks, linked to concrete requirements (statefulness, auditability). | `test_item11_single_vs_multi_doc_has_framework_rationale` |
| 12 | 12 | P20 Integration Decision Writeup | MCP & Interoperability | ✅ | (a) Expand the integration-decision doc with an A2A section. (b) Add a diagram of the chosen MCP architecture vs. alternatives. | `test_item12_integration_doc_has_a2a_section_and_diagram` |

## Progress log

**2026-09-17 — Foundational graph refactor (serves items 1, 3, 4, 5, 8, 9)**
- Rewrote [`src/graph.py`](../src/graph.py): every node is now a **module-level named function**
  (`intake_node`, `triage_node`, `reflection_node_wrapper`, `scheduling_node`, …, `memory_write_node`,
  `finalize_node`) taking `PatientIntakeState` and returning a state partial, bound to a `GraphDeps`
  object via `functools.partial`. No more hidden closures → statically traceable wiring.

**Item 1 (P10) — done.** `main.py` now imports and references `build_graph`, the workers
(`WORKERS`/`WORKER_NODES`), the typed `PatientIntakeState`, and `make_sqlite_checkpointer`; added a
`--show-graph` flag that builds and prints the graph topology, and a startup line naming the
orchestration. Test: `test_supervisor_hands_off_to_at_least_two_distinct_workers`,
`test_routing_differs_by_input` in `tests/test_advisor_remediation.py`.

**Item 2 (P21) — done.** The agentic-RAG call is reached through the module-level `triage_node` →
`_run_triage` → `triage_agent` (traceable). Tests mock `chat_text` in `_should_retrieve` and spy on
`care_pathway_lookup`: `test_agentic_rag_retrieves_when_llm_says_yes` /
`..._skips_when_llm_says_no`.

**Item 3 (P04) — done.** Every graph node is explicitly typed `(state: PatientIntakeState, deps) ->
PatientIntakeState` and the state flows node→node; `main.py`/`src/state.py` reference the type from the
entry point. Covered by the existing typed-state tests + the graph-build check.

**Item 4 (P11) — done.** Triage now hands to `reflection` via a **conditional edge**
(`add_conditional_edges("triage", route_after_triage, …)`) keyed on `TriageResult.confidence`. Tests:
`test_route_after_triage_is_confidence_gated`, `test_graph_takes_reflection_path_on_low_confidence`.

**Item 5 (P12) — done.** New [`src/context/strategies.py`](../src/context/strategies.py) exposes
`write`/`select`/`compress`/`isolate` as named functions that log + emit a `context_strategy` trace
event; called from `intake_node`, `memory_write_node`, and `run_intake`. Evidence:
`evidence/context_strategies_trace.json` (all four fire). Reconciliation checks added to
`scripts/audit_checklist.py` (§7.8).

**Item 6 (P13) — done.** `strategies.compress` logs an INFO line and a trace event whenever
summarization triggers; the evidence trace runs it on a 30-turn thread so compression genuinely fires
(`compressed: true`). Doc updated (`docs/context-engineering.md`).

**Item 7 (P15) — done.** `SemanticMemoryStore.recall` now logs each recall event
(`copilot.memory` logger). New `evidence/memory_lifecycle_log.txt` shows a fact recalled in a *new*
session (cross-session) with the captured INFO log. Existing `test_ac07_*` still covers persistence.

**Item 8 (P17) — done.** Added a dedicated `memory_write` graph node (supervisor → memory_write →
finalize) that persists the salient condition fact and thereby triggers the importance/TTL/LRU
eviction policy; `enforce_policy` logs evictions. Test:
`test_memory_write_node_persists_and_evicts`; evidence in `memory_lifecycle_log.txt`.

**Item 9 (P07) — done.** `SqliteSaver` is imported at module top of `src/graph.py` and named in
`make_sqlite_checkpointer`'s signature/docstring, so durable checkpointing is evident to static
analysis.

**Item 10 (P22) — done.** Reflection is confidence-triggered (shared with item 4). Added
`citation_accuracy()` metric + `citation_accuracy` field to `src/rag/evaluation.py`. Tests:
`test_citation_accuracy_metric`, `test_triage_cites_a_retrieved_guideline_for_grounded_case`.

**Item 11 (P03) — done.** Expanded §4 of `docs/single-vs-multi-decision.md` into a framework
comparison (LangGraph vs CrewAI / AutoGen / LangChain AgentExecutor / plain Python), each scored
against statefulness (AC-05), auditability (AC-02/03), and typed hand-offs (AC-01/04).

**Item 12 (P20) — done.** Added a Mermaid + ASCII architecture diagram (MCP vs. direct-import /
direct-DB / A2A) and a dedicated "Why not A2A" section to `docs/integration-decision.md`.

**Tests — one dedicated, labeled test group per item.**
[`tests/test_advisor_remediation.py`](../tests/test_advisor_remediation.py) now holds **27 tests**
(`test_item01_*` … `test_item12_*`); run them alone with `pytest tests/test_advisor_remediation.py -v`.

**Verification:** `python -m scripts.audit_checklist` → 73/73 mandatory pass (incl. new §7.8 wiring).
Full `pytest` suite passes (259 baseline + 27 remediation tests). Evidence set regenerated via
`python -m scripts.capture_evidence` so all committed traces reflect the new topology.
