"""Dedicated test per advisor remediation item (see docs/advisor-remediation-checklist.md).

One clearly-labeled section per rubric parameter (P03..P22). These assert the behaviors the course
static-analysis detector could not "see" from the wiring alone, plus the doc deliverables.

    ITEM  1  P10  Multi-Agent Orchestration
    ITEM  2  P21  Agentic-RAG Tool (retrieval-in-the-loop)
    ITEM  3  P04  Typed State Design
    ITEM  4  P11  Reflection / Self-Healing Loop
    ITEM  5  P12  Write / Select / Compress / Isolate
    ITEM  6  P13  Compression / Summarization Middleware
    ITEM  7  P15  Tiered Memory
    ITEM  8  P17  Eviction / Importance Policy
    ITEM  9  P07  Checkpointing / Persistence
    ITEM 10  P22  Grounding, Citations & Corrective Retrieval
    ITEM 11  P03  Single-vs-Multi-Agent Justification
    ITEM 12  P20  Integration Decision Writeup
"""
from __future__ import annotations

from pathlib import Path

import src.agents.triage as triage_mod
import src.graph as graph_mod
from src.agents.triage import triage_agent
from src.context import strategies
from src.context.quarantine import quarantine
from src.graph import (
    GraphDeps,
    SqliteSaver,
    build_graph,
    make_sqlite_checkpointer,
    memory_write_node,
    route_after_triage,
)
from src.memory.tiered_memory import TieredMemory, classify_importance
from src.rag.evaluation import citation_accuracy
from src.rag.retriever import reset_index
from src.reflection import LOW_CONFIDENCE_THRESHOLD
from src.runner import run_intake
from src.schemas import TriageResult, Urgency
from src.state import PatientIntakeState, new_state
from src.tracing import Trace

REPO = Path(__file__).resolve().parents[1]

TYPED_STATE_KEYS = {
    "session_id", "thread_id", "patient_id", "quarantined_input", "working_memory",
    "recalled_facts", "route_history", "next_worker", "completed_workers", "urgency",
    "triage_result", "final_plan",
}
GRAPH_NODE_FUNCS = [
    "intake_node", "triage_node", "reflection_node_wrapper", "scheduling_node",
    "referral_node", "followup_node", "supervisor", "memory_write_node", "finalize_node",
]


def _state(text="", **over):
    st = new_state(patient_id="SYN-1001", session_id="s", thread_id="t",
                   quarantined_input=quarantine(text))
    st.update(over)
    return st


def _run_with_trace(patient_id, text):
    trace = Trace("t")
    final = run_intake(patient_id=patient_id, text=text, use_checkpointer=False, trace=trace)
    return final, trace


# ══════════════════════════ ITEM 1 · P10 Multi-Agent Orchestration ═══════════════════════

def test_item01_supervisor_hands_off_to_at_least_two_distinct_workers():
    final, _ = _run_with_trace("SYN-1004",
                               "crushing chest pain radiating to my left arm, short of breath")
    dispatched = {h.split("->", 1)[1] for h in final["route_history"]
                  if h.startswith("supervisor->")} - {"finish"}
    assert len(dispatched) >= 2, f"supervisor only dispatched to {dispatched}"
    assert "triage" in dispatched


def test_item01_routing_differs_by_input():
    emergent = run_intake(patient_id="SYN-1004",
                          text="crushing chest pain radiating to my left arm, short of breath",
                          use_checkpointer=False)
    self_care = run_intake(patient_id="SYN-1001",
                           text="runny nose and mild cough since yesterday", use_checkpointer=False)
    assert set(emergent["completed_workers"]) != set(self_care["completed_workers"])
    assert "scheduling" in emergent["completed_workers"]
    assert "scheduling" not in self_care["completed_workers"]


def test_item01_main_entrypoint_wires_the_graph():
    import main
    assert main.build_graph is build_graph          # entry point references the graph builder
    assert hasattr(main, "_show_graph")             # and can print the wired topology
    assert set(main.WORKER_NODES) >= {"triage", "scheduling", "referral", "followup"}


# ══════════════════════════ ITEM 2 · P21 Agentic-RAG Tool ════════════════════════════════

def _spy_lookup():
    calls = {"n": 0}

    def spy(query, k=3):
        calls["n"] += 1
        return []

    return calls, spy


def test_item02_rag_retrieves_when_llm_says_yes(monkeypatch):
    calls, spy = _spy_lookup()
    monkeypatch.setattr(triage_mod, "care_pathway_lookup", spy)
    monkeypatch.setattr(triage_mod, "chat_text", lambda *a, **k: "yes")
    triage_agent(_state("runny nose and mild cough since yesterday"))
    assert calls["n"] == 1, "care_pathway_lookup must be called when the LLM decides 'yes'"


def test_item02_rag_skips_when_llm_says_no(monkeypatch):
    calls, spy = _spy_lookup()
    monkeypatch.setattr(triage_mod, "care_pathway_lookup", spy)
    monkeypatch.setattr(triage_mod, "chat_text", lambda *a, **k: "no")
    triage_agent(_state("runny nose and mild cough since yesterday"))
    assert calls["n"] == 0, "care_pathway_lookup must be skipped when the LLM decides 'no'"


def test_item02_rag_call_is_reachable_from_a_run():
    # The agentic-RAG decision is recorded in the trace of a full run (in-loop retrieval).
    _, trace = _run_with_trace("SYN-1004", "crushing chest pain radiating to my left arm")
    assert any(e["kind"] == "rag_decision" for e in trace.events)


# ══════════════════════════ ITEM 3 · P04 Typed State Design ══════════════════════════════

def test_item03_every_node_is_a_module_level_typed_function():
    for name in GRAPH_NODE_FUNCS:
        fn = getattr(graph_mod, name)
        assert callable(fn), f"{name} missing"
        ann = fn.__annotations__  # strings under `from __future__ import annotations`
        assert ann.get("state") == "PatientIntakeState", f"{name} state not typed"
        assert ann.get("return") == "PatientIntakeState", f"{name} return not typed"


def test_item03_typed_state_flows_through_a_full_run():
    final = run_intake(patient_id="SYN-1003", text="itchy rash on forearm, no fever",
                       use_checkpointer=False)
    # The typed state object is populated end-to-end (not declared-only).
    assert TYPED_STATE_KEYS.issubset(final.keys())
    assert final["triage_result"] is not None
    assert final["final_plan"] is not None
    assert isinstance(final["completed_workers"], list) and final["completed_workers"]


# ══════════════════════════ ITEM 4 · P11 Reflection / Self-Healing ═══════════════════════

def test_item04_route_after_triage_is_confidence_gated():
    low = TriageResult(urgency=Urgency.ROUTINE, chief_complaint="c", recommended_disposition="d",
                       confidence=LOW_CONFIDENCE_THRESHOLD - 0.1)
    high = TriageResult(urgency=Urgency.ROUTINE, chief_complaint="c", recommended_disposition="d",
                        confidence=LOW_CONFIDENCE_THRESHOLD + 0.1)
    assert route_after_triage(_state(triage_result=low)) == "reflection"
    assert route_after_triage(_state(triage_result=high)) == "supervisor"


def test_item04_graph_has_conditional_reflection_edge():
    edges = build_graph().get_graph().edges
    triage_targets = {e.target for e in edges if e.source == "triage"}
    assert {"reflection", "supervisor"} <= triage_targets
    assert all(e.conditional for e in edges if e.source == "triage")


def test_item04_graph_takes_reflection_path_on_low_confidence(monkeypatch):
    seen = {"triage_runs": 0}

    def low_conf_triage(state, trace=None):
        seen["triage_runs"] += 1
        return {"triage_result": TriageResult(
            urgency=Urgency.ROUTINE, chief_complaint="unclear", recommended_disposition="review",
            specialty="general_practice", confidence=0.1),
            "urgency": "routine", "completed_workers": ["triage"], "route_history": ["triage"]}

    monkeypatch.setattr(graph_mod, "triage_agent", low_conf_triage)
    trace = Trace("t")
    build_graph(trace=trace).invoke(_state("something feels off"),
                                    config={"configurable": {"thread_id": "t-refl"}})
    assert any(e["kind"] == "reflection" for e in trace.events)
    assert seen["triage_runs"] >= 2  # reflection re-planned (re-ran) triage


# ══════════════════════════ ITEM 5 · P12 Write / Select / Compress / Isolate ═════════════

def test_item05_all_four_strategies_fire_in_a_run():
    _, trace = _run_with_trace("SYN-1003", "itchy rash on forearm, no fever")
    fired = {e["strategy"] for e in trace.events if e["kind"] == "context_strategy"}
    assert set(strategies.STRATEGIES) <= fired, f"missing strategies: {set(strategies.STRATEGIES) - fired}"


def test_item05_strategy_functions_emit_events():
    trace = Trace("t")
    mem = TieredMemory(db_path=":memory:")
    strategies.write(mem, "P", "fact", importance=0.5, kind="note", trace=trace)
    strategies.isolate("hello", trace)
    strategies.select(mem, "P", "fact", k=1, trace=trace)
    strategies.compress([], trace)
    mem.close()
    fired = {e["strategy"] for e in trace.events if e["kind"] == "context_strategy"}
    assert fired == set(strategies.STRATEGIES)


# ══════════════════════════ ITEM 6 · P13 Compression / Summarization ═════════════════════

def test_item06_long_thread_is_compressed():
    long_thread = [{"role": "user", "content": f"Turn {i}: " + "detail " * 40} for i in range(30)]
    trace = Trace("t")
    summary = strategies.compress(long_thread, trace)
    assert summary, "long thread should be summarized"
    ev = [e for e in trace.events if e["kind"] == "context_strategy" and e["strategy"] == "compress"]
    assert ev and ev[0]["compressed"] is True


def test_item06_short_thread_is_not_compressed():
    trace = Trace("t")
    assert strategies.compress([{"role": "user", "content": "hi"}], trace) is None


# ══════════════════════════ ITEM 7 · P15 Tiered Memory ═══════════════════════════════════

def test_item07_fact_recalled_across_sessions(tmp_path):
    db = tmp_path / "mem.sqlite"
    pid = "SYN-1001"
    a = TieredMemory(db_path=db)
    a.remember_fact(pid, "Allergic to penicillin.", importance=0.95, kind="allergy")
    a.close()                                   # session boundary
    b = TieredMemory(db_path=db)                # new object, same DB (simulated restart)
    recalled = b.recall_text(pid, "any known drug allergies?", k=1)
    b.close()
    assert any("penicillin" in t.lower() for t in recalled)


def test_item07_recall_logs_event(caplog):
    import logging
    mem = TieredMemory(db_path=":memory:")
    mem.remember_fact("P", "prefers mornings", importance=0.4, kind="preference")
    with caplog.at_level(logging.INFO, logger="copilot.memory"):
        mem.recall("P", "appointment preference", k=1)
    mem.close()
    assert any("memory.recall" in r.message for r in caplog.records)


# ══════════════════════════ ITEM 8 · P17 Eviction / Importance Policy ════════════════════

def test_item08_memory_write_node_persists_and_evicts(tmp_path):
    mem = TieredMemory(db_path=tmp_path / "m.sqlite", max_items=2, ttl_seconds=10**9)
    pid = "SYN-1001"
    mem.remember_fact(pid, "smalltalk one", importance=0.1, kind="smalltalk")
    mem.remember_fact(pid, "smalltalk two", importance=0.1, kind="smalltalk")
    triage = TriageResult(urgency=Urgency.ROUTINE, chief_complaint="chest discomfort",
                          recommended_disposition="schedule", specialty="cardiology")
    trace = Trace("t")
    memory_write_node(_state(triage_result=triage, urgency="routine"),
                      GraphDeps(trace=trace, memory=mem))
    assert mem.count(pid) <= 2
    assert "chest discomfort" in " ".join(mem.recall_text(pid, "chest cardiology", k=3)).lower()
    ev = [e for e in trace.events if e["kind"] == "memory_write"]
    assert ev and ev[0]["evicted"] >= 1
    mem.close()


def test_item08_condition_outranks_smalltalk():
    assert classify_importance("condition") > classify_importance("smalltalk")


def test_item08_eviction_logs_event(tmp_path, caplog):
    import logging
    mem = TieredMemory(db_path=tmp_path / "m.sqlite", max_items=1, ttl_seconds=10**9)
    with caplog.at_level(logging.INFO, logger="copilot.memory"):
        mem.remember_fact("P", "a", importance=0.1, kind="smalltalk")
        mem.remember_fact("P", "b", importance=0.1, kind="smalltalk")  # forces eviction
    mem.close()
    assert any("memory.evict" in r.message for r in caplog.records)


# ══════════════════════════ ITEM 9 · P07 Checkpointing / Persistence ═════════════════════

def test_item09_checkpointer_is_named_sqlitesaver(tmp_path):
    ckpt = make_sqlite_checkpointer(tmp_path / "ckpt.sqlite")
    assert isinstance(ckpt, SqliteSaver)


def test_item09_graph_compiles_with_checkpointer(tmp_path):
    ckpt = make_sqlite_checkpointer(tmp_path / "ckpt.sqlite")
    graph = build_graph(checkpointer=ckpt, interrupt_before=["scheduling"])
    cfg = {"configurable": {"thread_id": "th"}}
    graph.invoke(_state("itchy rash on forearm"), config=cfg)
    snap = graph.get_state(cfg)
    assert snap.values["triage_result"] is not None  # state durably checkpointed
    assert snap.next


# ══════════════════════════ ITEM 10 · P22 Grounding, Citations & Corrective Retrieval ════

def test_item10_citation_accuracy_metric():
    assert citation_accuracy([], ["a.md"]) == 0.0
    assert citation_accuracy(["a.md"], ["a.md"]) == 1.0
    assert citation_accuracy(["a.md", "b.md"], ["a.md"]) == 0.5
    assert citation_accuracy(["wrong.md"], ["right.md"]) == 0.0


def test_item10_triage_cites_a_retrieved_guideline():
    reset_index()
    out = triage_agent(_state("crushing chest pain radiating to my left arm"))
    result = out["triage_result"]
    assert result.guideline_citations, "grounded triage must carry guideline citations"
    retrieved = {p["source"] for p in out["rag_context"]}
    assert citation_accuracy(result.guideline_citations, list(retrieved)) == 1.0


def test_item10_evaluation_reports_citation_accuracy():
    import json
    from src.rag.evaluation import aggregate, evaluate_item
    from src.rag.retriever import care_pathway_lookup
    reset_index()
    eval_set = json.loads((REPO / "data" / "synthetic" / "rag_eval_set.json").read_text("utf-8"))
    results = [evaluate_item(i, care_pathway_lookup, k=3) for i in eval_set["items"]]
    agg = aggregate(results)
    assert "citation_accuracy" in agg
    assert all(hasattr(r, "citation_accuracy") for r in results)


# ══════════════════════════ ITEM 11 · P03 Single-vs-Multi Justification ══════════════════

def test_item11_single_vs_multi_doc_has_framework_rationale():
    doc = (REPO / "docs" / "single-vs-multi-decision.md").read_text("utf-8").lower()
    # Compares LangGraph against other multi-agent frameworks...
    assert "langgraph" in doc
    assert "crewai" in doc and "autogen" in doc
    # ...and links the choice to concrete project requirements.
    assert "statefulness" in doc or "stateful" in doc
    assert "auditab" in doc  # auditable / auditability
    assert "ac-05" in doc and ("ac-02" in doc or "ac-03" in doc)


# ══════════════════════════ ITEM 12 · P20 Integration Decision Writeup ═══════════════════

def test_item12_integration_doc_has_a2a_section_and_diagram():
    doc = (REPO / "docs" / "integration-decision.md").read_text("utf-8")
    low = doc.lower()
    assert "why not a2a" in low or "a2a (agent-to-agent)" in low  # dedicated A2A discussion
    assert "```mermaid" in doc                                    # architecture diagram present
    assert "mcp" in low and "protocol boundary" in low
