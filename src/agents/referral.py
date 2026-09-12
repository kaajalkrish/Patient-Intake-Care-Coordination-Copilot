"""Referral worker (AC-02/03/04).

Decides whether the presenting need requires a specialist referral, and whether it is out of the
clinic's scope (refer out). Uses the triage specialty + scope list. Deterministic by design.
"""
from __future__ import annotations

from ..schemas import ReferralResult, TriageResult
from ..state import PatientIntakeState
from ..tracing import Trace
from .base import IN_SCOPE_SPECIALTIES

# Specialties handled by general practice directly (no referral needed).
_GP_HANDLED = {"general_practice"}


def referral_agent(state: PatientIntakeState, trace: Trace | None = None) -> dict:
    triage: TriageResult | None = state.get("triage_result")
    specialty = triage.specialty if triage else "general_practice"

    # Out-of-scope is signalled explicitly by triage (specialty itself is always in-scope).
    out_of_scope = bool(triage and triage.out_of_scope) or specialty not in IN_SCOPE_SPECIALTIES
    if out_of_scope:
        result = ReferralResult(
            referral_needed=True, referred_specialty="external specialist", out_of_scope=True,
            reason="Presenting need is outside clinic scope; refer to an external specialist.",
        )
    elif specialty in _GP_HANDLED:
        result = ReferralResult(
            referral_needed=False, out_of_scope=False,
            reason="Handled within general practice; no referral required.",
        )
    else:
        result = ReferralResult(
            referral_needed=True, referred_specialty=specialty, out_of_scope=False,
            reason=f"In-scope specialty referral to {specialty}.",
        )
    if trace:
        trace.event("referral_result", needed=result.referral_needed,
                    out_of_scope=result.out_of_scope, specialty=specialty)
    return {
        "referral_result": result,
        "completed_workers": ["referral"],
        "route_history": ["referral"],
        "messages": [{"role": "assistant",
                      "content": f"[referral] needed={result.referral_needed}"}],
    }
