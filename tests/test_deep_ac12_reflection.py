"""DEEP AC-12 / NFR-07: reflection + self-healing / fallback loop — exhaustive.

Two mechanisms:
  - guard(): retry-with-fallback around a worker (tool/model/validation failure).
  - reflection_node(): re-plan when triage confidence is below threshold.
"""
from __future__ import annotations

from src.reflection import (
    LOW_CONFIDENCE_THRESHOLD,
    MAX_WORKER_RETRIES,
    guard,
    reflection_node,
)
from src.schemas import TriageResult, Urgency
from src.state import new_state
from src.tracing import Trace


def _state():
    return new_state(patient_id="P", session_id="s", thread_id="t",
                     quarantined_input={"raw": "", "sanitized": "", "injection_flagged": False})


# ---------------------------------------------------------------- guard()

def test_guard_passes_through_on_success():
    out = guard("triage", lambda st: {"ok": True}, _state())
    assert out == {"ok": True}


def test_guard_recovers_on_retry():
    calls = {"n": 0}

    def flaky(st):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient tool failure")
        return {"recovered": True}

    trace = Trace("t", {})
    out = guard("scheduling", flaky, _state(), trace)
    assert out == {"recovered": True}
    assert calls["n"] == 2
    assert any(e["kind"] == "self_heal" for e in trace.events)


def test_guard_falls_back_after_exhausting_retries():
    def always_fail(st):
        raise RuntimeError("permanent outage")

    trace = Trace("t", {})
    fallback = {"scheduling_result": None}
    out = guard("scheduling", always_fail, _state(), trace, fallback=fallback)
    # explicit exit condition -> safe fallback with recorded error + reflection note (NFR-07)
    assert "errors" in out and out["errors"]
    assert "reflection_notes" in out and out["reflection_notes"]
    assert out["retry_counts"]["scheduling"] == MAX_WORKER_RETRIES + 1
    assert any(e["kind"] == "fallback" for e in trace.events)


# ---------------------------------------------------------------- reflection_node()

def test_reflection_accepts_high_confidence():
    st = _state()
    st["triage_result"] = TriageResult(
        urgency=Urgency.ROUTINE, chief_complaint="c", recommended_disposition="d",
        confidence=0.9)
    trace = Trace("t", {})
    out = reflection_node(st, trace)
    assert any(e.get("verdict") == "accept" for e in trace.events)
    assert "accepted" in " ".join(out["reflection_notes"]).lower()


def test_reflection_replans_on_low_confidence():
    st = _state()
    st["triage_result"] = TriageResult(
        urgency=Urgency.ROUTINE, chief_complaint="c", recommended_disposition="d",
        confidence=LOW_CONFIDENCE_THRESHOLD - 0.1)
    replanned = {"called": False}

    def triage_fn(state):
        replanned["called"] = True
        return {"reflection_notes": ["re-triaged"]}

    trace = Trace("t", {})
    out = reflection_node(st, trace, triage_fn=triage_fn)
    assert replanned["called"] is True
    assert any(e.get("verdict") == "re_plan" for e in trace.events)
    assert any("re-plan" in n.lower() or "re-triaged" in n.lower()
               for n in out["reflection_notes"])


def test_reflection_low_confidence_without_triage_fn_notes_caution():
    st = _state()
    st["triage_result"] = TriageResult(
        urgency=Urgency.ROUTINE, chief_complaint="c", recommended_disposition="d",
        confidence=0.1)
    out = reflection_node(st)  # no triage_fn -> can't re-plan, but must note it
    assert out["reflection_notes"]


def test_reflection_noop_without_triage():
    assert reflection_node(_state()) == {}
