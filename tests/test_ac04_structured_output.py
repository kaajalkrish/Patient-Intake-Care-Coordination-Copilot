"""AC-04: Node/agent outputs are validated structured Pydantic objects at hand-off boundaries."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.runner import run_intake
from src.schemas import (
    FollowUpResult,
    ReferralResult,
    SchedulingResult,
    TriageResult,
    Urgency,
)


def test_worker_outputs_are_validated_pydantic_instances():
    final = run_intake(patient_id="SYN-1004",
                       text="crushing chest pain radiating to left arm, short of breath",
                       use_checkpointer=False)
    assert isinstance(final["triage_result"], TriageResult)
    assert isinstance(final["scheduling_result"], SchedulingResult)
    assert isinstance(final["referral_result"], ReferralResult)
    assert isinstance(final["followup_result"], FollowUpResult)


def test_invalid_triage_output_raises_validation_error():
    with pytest.raises(ValidationError):
        TriageResult(urgency=Urgency.ROUTINE, chief_complaint="", recommended_disposition="x")
    with pytest.raises(ValidationError):
        TriageResult(urgency="not_a_level", chief_complaint="c", recommended_disposition="d")


def test_cross_field_validation_at_boundary():
    # slot_id is required when an appointment is recommended.
    with pytest.raises(ValidationError):
        SchedulingResult(appointment_recommended=True, slot_id=None)
    # referred_specialty required when a referral is needed.
    with pytest.raises(ValidationError):
        ReferralResult(referral_needed=True, referred_specialty=None)


def test_final_plan_is_serializable_structured_object():
    final = run_intake(patient_id="SYN-1001", text="itchy rash, no fever", use_checkpointer=False)
    plan = final["final_plan"]
    assert isinstance(plan, dict)
    assert plan["patient_id"] == "SYN-1001"
    assert "disclaimer" in plan
