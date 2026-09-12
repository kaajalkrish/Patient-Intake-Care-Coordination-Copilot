"""Scheduling worker (AC-02/03/04).

Proposes an appointment slot appropriate to urgency + specialty. Emergent/urgent cases are
EXPEDITED (AC-03). Slots come from the clinic MCP tool when available; otherwise from the local
synthetic slot file (graceful degradation, NFR-07). No appointment is booked for self_care.
"""
from __future__ import annotations

from ..schemas import SchedulingResult, TriageResult, Urgency
from ..state import PatientIntakeState
from ..tracing import Trace
from .base import load_slots

_EXPEDITE_BAND = {"emergent": "emergent", "urgent": "urgent"}


def _pick_slot(specialty: str, urgency: str) -> dict | None:
    slots = load_slots()
    band = _EXPEDITE_BAND.get(urgency, urgency)
    matches = [s for s in slots if s.get("specialty") == specialty and s.get("urgency_band") == band]
    if not matches:
        matches = [s for s in slots if s.get("specialty") == specialty]
    return matches[0] if matches else None


def scheduling_agent(state: PatientIntakeState, trace: Trace | None = None,
                     mcp_slot_fn=None) -> dict:
    triage: TriageResult | None = state.get("triage_result")
    urgency = state.get("urgency") or (triage.urgency.value if triage else "routine")
    specialty = triage.specialty if triage else "general_practice"

    # Self-care needs no appointment.
    if urgency == Urgency.SELF_CARE.value:
        result = SchedulingResult(
            appointment_recommended=False, specialty=specialty, expedited=False,
            notes="Self-care guidance provided; no appointment needed unless symptoms worsen.",
        )
        if trace:
            trace.event("scheduling_result", recommended=False, urgency=urgency)
        return _pack(result)

    # Emergent: expedite; recommend direct emergency care rather than a routine slot.
    slot = None
    if mcp_slot_fn is not None:
        try:
            slot = (mcp_slot_fn(specialty=specialty, urgency=urgency) or [None])[0]
        except Exception:
            slot = None
    if slot is None:
        slot = _pick_slot(specialty, urgency)

    expedited = urgency in _EXPEDITE_BAND
    if slot is None:
        result = SchedulingResult(
            appointment_recommended=False, specialty=specialty, expedited=expedited,
            notes="No matching slot available; escalate to staff for manual scheduling.",
        )
    else:
        notes = ("EXPEDITED due to urgency. If emergent, direct to emergency care first."
                 if expedited else "Routine scheduling.")
        result = SchedulingResult(
            appointment_recommended=True,
            slot_id=slot["slot_id"],
            provider=slot.get("provider"),
            specialty=specialty,
            when=slot.get("when"),
            expedited=expedited,
            notes=notes,
        )
    if trace:
        trace.event("scheduling_result", recommended=result.appointment_recommended,
                    expedited=result.expedited, urgency=urgency, specialty=specialty)
    return _pack(result)


def _pack(result: SchedulingResult) -> dict:
    return {
        "scheduling_result": result,
        "completed_workers": ["scheduling"],
        "route_history": ["scheduling"],
        "messages": [{"role": "assistant",
                      "content": f"[scheduling] recommended={result.appointment_recommended} "
                                 f"expedited={result.expedited}"}],
    }
