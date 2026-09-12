"""AC-02: A supervisor routes an intake request to specialized workers."""
from __future__ import annotations

from src.agents.supervisor import WORKERS, decide_next
from src.runner import run_intake
from src.state import new_state


def _blank_state(**over):
    st = new_state(patient_id="SYN-1001", session_id="s", thread_id="t",
                   quarantined_input={"raw": "", "sanitized": "", "injection_flagged": False})
    st.update(over)
    return st


def test_supervisor_routes_triage_first():
    decision = decide_next(_blank_state())
    assert decision.next_worker == "triage"


def test_supervisor_dispatches_to_all_specialized_workers_in_a_full_run():
    final = run_intake(patient_id="SYN-1004",
                       text="crushing chest pain radiating to my left arm, short of breath",
                       use_checkpointer=False)
    done = set(final["completed_workers"])
    # triage + scheduling + referral + followup all reached via the supervisor.
    assert {"triage", "scheduling", "referral", "followup"}.issubset(done)


def test_route_history_records_supervisor_dispatch():
    final = run_intake(patient_id="SYN-1001", text="itchy rash on forearm, no fever",
                       use_checkpointer=False)
    hist = " ".join(final["route_history"])
    assert "supervisor->" in hist
    assert all(w in WORKERS or w == "finish" for w in
               [h.split("->")[1] for h in final["route_history"] if h.startswith("supervisor->")])
