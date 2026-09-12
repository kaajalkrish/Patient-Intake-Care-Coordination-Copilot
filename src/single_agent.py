"""Single-agent baseline for the single-vs-multi comparison (NFR-06, Good-to-Have).

One agent handles triage + scheduling + referral + follow-up in a single pass, with NO supervisor and
NO per-worker routing. Reuses the same domain heuristics/tools so the comparison isolates the
*architecture* difference, not the domain logic. Used by scripts/run_comparison.py.
"""
from __future__ import annotations

import time

from .agents.base import detect_condition, load_pathways, scan_red_flags
from .agents.followup import followup_agent
from .agents.referral import referral_agent
from .agents.scheduling import scheduling_agent
from .agents.triage import triage_agent
from .context.quarantine import quarantine
from .schemas import CarePlan, Urgency
from .state import new_state
from .tracing import Trace


def run_single_agent(patient_id: str, text: str, trace: Trace | None = None) -> dict:
    """Run the whole intake in one combined agent pass (no orchestration graph)."""
    t0 = time.time()
    trace = trace or Trace("single_agent_run", {"patient_id": patient_id})
    st = new_state(patient_id=patient_id, session_id="single", thread_id="single",
                   quarantined_input=quarantine(text))

    # Single pass: the one agent calls each capability itself, in fixed order, no supervisor.
    st.update(triage_agent(st, trace))
    st.update(scheduling_agent(st, trace))
    st.update(referral_agent(st, trace))
    st.update(followup_agent(st, trace))

    triage = st["triage_result"]
    plan = CarePlan(
        patient_id=patient_id,
        urgency=triage.urgency,
        triage=triage,
        scheduling=st.get("scheduling_result"),
        referral=st.get("referral_result"),
        followup=st.get("followup_result"),
        summary=f"[single-agent] {triage.chief_complaint} / {triage.urgency.value}",
    )
    return {
        "final_plan": plan.model_dump(mode="json"),
        "urgency": triage.urgency.value,
        "latency_s": round(time.time() - t0, 4),
        "agent_steps": 4,          # no supervisor decision steps
        "route_history": st.get("route_history", []),
    }
