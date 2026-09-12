"""Follow-up worker (AC-02/04).

Produces follow-up actions, a follow-up window, and coordination notes based on urgency and whether a
referral was made. Non-diagnostic, coordination-only instructions.
"""
from __future__ import annotations

from ..schemas import FollowUpResult, ReferralResult, TriageResult
from ..state import PatientIntakeState
from ..tracing import Trace

_WINDOW = {
    "emergent": "immediately / same day",
    "urgent": "24-48 hours",
    "routine": "1-2 weeks",
    "self_care": "only if symptoms worsen or persist beyond 10 days",
}


def followup_agent(state: PatientIntakeState, trace: Trace | None = None) -> dict:
    triage: TriageResult | None = state.get("triage_result")
    referral: ReferralResult | None = state.get("referral_result")
    urgency = state.get("urgency") or (triage.urgency.value if triage else "routine")

    actions = []
    if urgency == "emergent":
        actions.append("Confirm the patient reached emergency care; flag for clinician review now.")
    else:
        actions.append("Confirm the appointment and send synthetic reminder.")
    if referral and referral.referral_needed:
        dest = referral.referred_specialty or "specialist"
        actions.append(f"Track the {dest} referral to completion.")
    actions.append("Reconcile allergies/medications from patient memory before the visit.")

    result = FollowUpResult(
        follow_up_actions=actions,
        follow_up_window=_WINDOW.get(urgency, "1-2 weeks"),
        coordination_notes=f"Urgency={urgency}. Human staff to confirm all steps.",
        patient_instructions=(
            "General coordination only: keep your appointment, bring your medication list, and "
            "seek emergency care if symptoms suddenly worsen. This is not medical advice."
        ),
    )
    if trace:
        trace.event("followup_result", window=result.follow_up_window, actions=len(actions))
    return {
        "followup_result": result,
        "completed_workers": ["followup"],
        "route_history": ["followup"],
        "messages": [{"role": "assistant", "content": "[followup] plan produced"}],
    }
