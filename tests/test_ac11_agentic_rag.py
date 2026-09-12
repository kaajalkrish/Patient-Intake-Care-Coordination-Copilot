"""AC-11: Agentic-RAG tool available; the agent DECIDES when to call it (in-loop retrieval)."""
from __future__ import annotations

from src.agents.triage import triage_agent
from src.context.quarantine import quarantine
from src.rag.retriever import care_pathway_lookup, reset_index
from src.state import new_state
from src.tracing import Trace


def _state(text):
    return new_state(patient_id="SYN-1001", session_id="s", thread_id="t",
                     quarantined_input=quarantine(text))


def test_rag_tool_retrieves_relevant_passages():
    reset_index()
    hits = care_pathway_lookup("chest pain triage urgency", k=3)
    assert hits, "RAG returned no passages"
    joined = " ".join(h["text"].lower() for h in hits)
    assert "chest" in joined or "emergent" in joined
    assert all("score" in h and "source" in h for h in hits)


def test_agent_decides_to_retrieve_for_guideline_dependent_case():
    trace = Trace("t")
    triage_agent(_state("crushing chest pain radiating to my left arm"), trace)
    decisions = [e for e in trace.events if e["kind"] == "rag_decision"]
    assert decisions and decisions[0]["retrieve"] is True
    assert decisions[0]["hits"] >= 1  # retrieval happened inside the loop


def test_agent_can_skip_retrieval_for_trivial_case_offline():
    # Offline (no LLM) a trivial cold with no red flags -> agent skips retrieval.
    from src.config import settings

    if settings.has_api_key:
        return  # with an LLM the decision is delegated to the model; skip the offline assertion
    trace = Trace("t")
    triage_agent(_state("runny nose and mild cough since yesterday"), trace)
    decisions = [e for e in trace.events if e["kind"] == "rag_decision"]
    assert decisions and decisions[0]["retrieve"] is False
