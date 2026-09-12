"""AC-12: Reflection / self-healing / fallback loop with an evidenced trace."""
from __future__ import annotations

from src.agents.scheduling import scheduling_agent
from src.reflection import guard, reflection_node
from src.schemas import TriageResult, Urgency
from src.state import new_state
from src.tracing import Trace


def _state(**over):
    st = new_state(patient_id="SYN-1001", session_id="s", thread_id="t",
                   quarantined_input={"raw": "", "sanitized": "", "injection_flagged": False})
    st.update(over)
    return st


def test_guard_retries_then_recovers():
    calls = {"n": 0}

    def flaky(state):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient tool failure")
        return {"completed_workers": ["triage"]}

    trace = Trace("t")
    out = guard("triage", flaky, _state(), trace)
    assert out == {"completed_workers": ["triage"]}
    kinds = [e["kind"] for e in trace.events]
    assert "worker_error" in kinds and "self_heal" in kinds


def test_guard_falls_back_after_exhausting_retries():
    def always_fail(state):
        raise RuntimeError("permanent failure")

    trace = Trace("t")
    out = guard("scheduling", always_fail, _state(), trace,
                fallback={"completed_workers": ["scheduling"]})
    assert "scheduling" in out["completed_workers"]
    assert out["errors"] and out["reflection_notes"]
    assert any(e["kind"] == "fallback" for e in trace.events)


def test_scheduling_self_heals_when_mcp_tool_fails():
    def broken_mcp(**kwargs):
        raise ConnectionError("MCP slot service down")

    triage = TriageResult(urgency=Urgency.ROUTINE, chief_complaint="rash",
                          recommended_disposition="schedule", specialty="dermatology")
    trace = Trace("t")
    # scheduling_agent must fall back to local slots when the MCP tool raises.
    out = scheduling_agent(_state(triage_result=triage, urgency="routine"), trace,
                           mcp_slot_fn=broken_mcp)
    assert out["scheduling_result"].appointment_recommended is True  # recovered via local fallback


def test_reflection_replans_on_low_confidence():
    triage = TriageResult(urgency=Urgency.ROUTINE, chief_complaint="unclear",
                          recommended_disposition="review", specialty="general_practice",
                          confidence=0.1)
    replans = {"n": 0}

    def redo_triage(state):
        replans["n"] += 1
        return {"triage_result": TriageResult(
            urgency=Urgency.ROUTINE, chief_complaint="clarified",
            recommended_disposition="schedule", specialty="general_practice", confidence=0.7)}

    trace = Trace("t")
    out = reflection_node(_state(triage_result=triage), trace, triage_fn=redo_triage)
    assert replans["n"] == 1  # re-planned once
    assert any(e["kind"] == "reflection" and e.get("verdict") == "re_plan" for e in trace.events)
    assert out["triage_result"].confidence > 0.35
