"""AC-03: Conditional edges route on state (urgent->expedited; out-of-scope->referral)."""
from __future__ import annotations

from src.agents.supervisor import decide_next
from src.runner import run_intake
from src.schemas import TriageResult, Urgency
from src.state import new_state


def _state_with_triage(urgency: str, specialty: str, done=None):
    st = new_state(patient_id="SYN-1001", session_id="s", thread_id="t",
                   quarantined_input={"raw": "", "sanitized": "", "injection_flagged": False})
    st["triage_result"] = TriageResult(
        urgency=Urgency(urgency), chief_complaint="x", recommended_disposition="y",
        specialty=specialty)
    st["urgency"] = urgency
    st["completed_workers"] = done or ["triage"]
    return st


def test_emergent_takes_expedited_scheduling_path():
    final = run_intake(patient_id="SYN-1004",
                       text="crushing chest pain radiating to my left arm and I'm sweating",
                       use_checkpointer=False)
    assert final["urgency"] == "emergent"
    assert final["scheduling_result"].expedited is True


def test_self_care_skips_scheduling():
    # self_care should route past scheduling (no appointment recommended).
    decision = decide_next(_state_with_triage("self_care", "general_practice"))
    assert decision.next_worker in ("referral", "followup")  # not scheduling
    final = run_intake(patient_id="SYN-1001", text="runny nose and mild cough since yesterday",
                       use_checkpointer=False)
    assert final["urgency"] == "self_care"
    assert final["scheduling_result"] is None or \
        final["scheduling_result"].appointment_recommended is False


def test_out_of_scope_specialty_triggers_referral():
    # A specialty outside the clinic's scope must be referred out.
    st = _state_with_triage("routine", "neurosurgery", done=["triage", "scheduling"])
    decision = decide_next(st)
    assert decision.next_worker == "referral"


def test_in_scope_non_gp_specialty_produces_referral_in_full_run():
    final = run_intake(patient_id="SYN-1003", text="itchy rash on my forearm for a few days",
                       use_checkpointer=False)
    # dermatology is in-scope but not GP -> a referral decision is produced.
    assert final["referral_result"] is not None
    assert final["referral_result"].referral_needed is True
