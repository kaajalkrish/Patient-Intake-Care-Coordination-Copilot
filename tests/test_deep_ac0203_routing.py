"""DEEP AC-02 / AC-03: supervisor orchestration + conditional routing — exhaustive matrix.

`decide_next` is a pure function of state, so we can exercise every urgency x scope combination and
assert the exact next-worker decision and the full route ordering.
"""
from __future__ import annotations

import pytest

from src.agents.supervisor import decide_next
from src.schemas import TriageResult, Urgency
from src.state import new_state


def _st(urgency, specialty="general_practice", out_of_scope=False, done=None):
    st = new_state(patient_id="SYN-1001", session_id="s", thread_id="t",
                   quarantined_input={"raw": "", "sanitized": "", "injection_flagged": False})
    st["triage_result"] = TriageResult(
        urgency=Urgency(urgency), chief_complaint="c", recommended_disposition="d",
        specialty=specialty, out_of_scope=out_of_scope)
    st["urgency"] = urgency
    st["completed_workers"] = done or []
    return st


def _full_route(urgency, specialty="general_practice", out_of_scope=False):
    """Simulate the supervisor loop to completion, returning the ordered worker sequence."""
    done: list[str] = []
    seq: list[str] = []
    for _ in range(10):
        st = _st(urgency, specialty, out_of_scope, done=list(done))
        nxt = decide_next(st).next_worker
        seq.append(nxt)
        if nxt == "finish":
            break
        done.append(nxt)
    return seq


# ---- always triage first (AC-02) ----

@pytest.mark.parametrize("urgency", ["emergent", "urgent", "routine", "self_care"])
def test_triage_runs_first(urgency):
    assert decide_next(_st(urgency, done=[])).next_worker == "triage"


# ---- conditional routing on urgency (AC-03) ----

def test_emergent_routes_to_scheduling_after_triage():
    d = decide_next(_st("emergent", done=["triage"]))
    assert d.next_worker == "scheduling"
    assert "expedit" in d.reason.lower()


def test_urgent_is_expedited():
    d = decide_next(_st("urgent", done=["triage"]))
    assert d.next_worker == "scheduling"
    assert "expedit" in d.reason.lower()


def test_routine_uses_standard_scheduling():
    d = decide_next(_st("routine", done=["triage"]))
    assert d.next_worker == "scheduling"
    assert "expedit" not in d.reason.lower()


def test_self_care_skips_scheduling():
    d = decide_next(_st("self_care", done=["triage"]))
    assert d.next_worker != "scheduling"


# ---- conditional routing on scope (AC-03) ----

def test_out_of_scope_triggers_referral():
    d = decide_next(_st("routine", out_of_scope=True, done=["triage", "scheduling"]))
    assert d.next_worker == "referral"


def test_non_gp_specialty_triggers_referral():
    d = decide_next(_st("routine", specialty="cardiology", done=["triage", "scheduling"]))
    assert d.next_worker == "referral"


def test_gp_in_scope_skips_referral():
    d = decide_next(_st("routine", specialty="general_practice",
                        done=["triage", "scheduling"]))
    assert d.next_worker == "followup"


# ---- terminal state ----

def test_finish_when_all_workers_done():
    d = decide_next(_st("routine", done=["triage", "scheduling", "referral", "followup"]))
    assert d.next_worker == "finish"


# ---- full ordered routes (end-to-end supervisor policy) ----

def test_full_route_emergent_cardiology():
    seq = _full_route("emergent", specialty="cardiology")
    assert seq == ["triage", "scheduling", "referral", "followup", "finish"]


def test_full_route_routine_gp_skips_referral():
    seq = _full_route("routine", specialty="general_practice")
    assert seq == ["triage", "scheduling", "followup", "finish"]


def test_full_route_self_care_gp_skips_scheduling_and_referral():
    seq = _full_route("self_care", specialty="general_practice")
    assert "scheduling" not in seq
    assert seq[-1] == "finish"


def test_full_route_self_care_out_of_scope_still_refers():
    seq = _full_route("self_care", specialty="general_practice", out_of_scope=True)
    assert "referral" in seq
    assert "scheduling" not in seq
