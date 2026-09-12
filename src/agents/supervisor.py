"""Supervisor / orchestrator (AC-02/03).

The supervisor routes the intake request to the specialized workers and decides the order using
CONDITIONAL logic driven by state:

  - Always triage first.
  - self_care  -> skip scheduling (no appointment) ; referral only if out-of-scope ; then follow-up.
  - emergent/urgent/routine -> scheduling (expedited for emergent/urgent) -> referral (if needed)
    -> follow-up.
  - When all needed workers have run -> finish.

`decide_next()` is a PURE function of state so the routing policy is directly unit-testable
(test_ac02, test_ac03). The graph wires it as a conditional edge.
"""
from __future__ import annotations

from ..schemas import SupervisorDecision, TriageResult
from ..state import PatientIntakeState
from ..tracing import Trace
from .base import IN_SCOPE_SPECIALTIES

WORKERS = ("triage", "scheduling", "referral", "followup")


def _needs_referral(triage: TriageResult | None) -> bool:
    if triage is None:
        return False
    spec = triage.specialty
    # Out of scope OR an in-scope specialty other than general practice needs a referral.
    if spec not in IN_SCOPE_SPECIALTIES:
        return True
    return spec != "general_practice"


def decide_next(state: PatientIntakeState) -> SupervisorDecision:
    """Return the next worker to run (or 'finish'), with a reason. Pure function of state."""
    done = set(state.get("completed_workers", []))
    triage: TriageResult | None = state.get("triage_result")
    urgency = state.get("urgency") or (triage.urgency.value if triage else "")

    if "triage" not in done:
        return SupervisorDecision(next_worker="triage", reason="Triage the request first.")

    # Post-triage branching (conditional on urgency + scope).
    if "scheduling" not in done and urgency != "self_care":
        expedite = urgency in ("emergent", "urgent")
        return SupervisorDecision(
            next_worker="scheduling",
            reason=("Expedited scheduling for high-acuity case." if expedite
                    else "Standard scheduling."),
        )

    if "referral" not in done and _needs_referral(triage):
        return SupervisorDecision(
            next_worker="referral",
            reason=f"Specialty '{triage.specialty}' requires a referral decision.",
        )

    if "followup" not in done:
        return SupervisorDecision(next_worker="followup", reason="Set up follow-up/coordination.")

    return SupervisorDecision(next_worker="finish", reason="All required workers complete.")


def supervisor_node(state: PatientIntakeState, trace: Trace | None = None) -> dict:
    """Graph node: compute the routing decision and record it in state (AC-02)."""
    decision = decide_next(state)
    if trace:
        trace.event("supervisor_route", next=decision.next_worker, reason=decision.reason,
                    urgency=state.get("urgency", ""))
    return {
        "next_worker": decision.next_worker,
        "route_history": [f"supervisor->{decision.next_worker}"],
        "messages": [{"role": "assistant",
                      "content": f"[supervisor] -> {decision.next_worker}: {decision.reason}"}],
    }
