"""DEEP AC-04: structured output validated at hand-off boundaries — exhaustive cases.

Every worker returns a Pydantic model; invalid output must RAISE (so the reflection loop can catch it,
AC-12). These tests cover valid construction, each field validator, enum handling and bound checks.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas import (
    CarePlan,
    FollowUpResult,
    ReferralResult,
    SchedulingResult,
    SupervisorDecision,
    TriageResult,
    Urgency,
)


# ---- Urgency enum ----

def test_urgency_rank_ordering():
    assert Urgency.EMERGENT.rank > Urgency.URGENT.rank > Urgency.ROUTINE.rank > Urgency.SELF_CARE.rank


@pytest.mark.parametrize("value", ["emergent", "urgent", "routine", "self_care"])
def test_urgency_accepts_valid_values(value):
    assert Urgency(value).value == value


def test_urgency_rejects_invalid_value():
    with pytest.raises(ValueError):
        Urgency("super_urgent")


# ---- TriageResult ----

def test_triage_valid_minimal():
    t = TriageResult(urgency=Urgency.ROUTINE, chief_complaint="rash",
                     recommended_disposition="see GP")
    assert t.specialty == "general_practice"  # default
    assert t.out_of_scope is False
    assert t.confidence == 0.0


def test_triage_empty_chief_complaint_raises():
    with pytest.raises(ValidationError):
        TriageResult(urgency=Urgency.ROUTINE, chief_complaint="",
                     recommended_disposition="x")


def test_triage_empty_disposition_raises():
    with pytest.raises(ValidationError):
        TriageResult(urgency=Urgency.ROUTINE, chief_complaint="x",
                     recommended_disposition="")


def test_triage_invalid_specialty_raises():
    with pytest.raises(ValidationError):
        TriageResult(urgency=Urgency.ROUTINE, chief_complaint="x",
                     recommended_disposition="y", specialty="wizardry")


@pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0])
def test_triage_confidence_out_of_bounds_raises(bad):
    with pytest.raises(ValidationError):
        TriageResult(urgency=Urgency.ROUTINE, chief_complaint="x",
                     recommended_disposition="y", confidence=bad)


@pytest.mark.parametrize("ok", [0.0, 0.5, 1.0])
def test_triage_confidence_in_bounds_ok(ok):
    t = TriageResult(urgency=Urgency.ROUTINE, chief_complaint="x",
                     recommended_disposition="y", confidence=ok)
    assert t.confidence == ok


# ---- SchedulingResult ----

def test_scheduling_slot_required_when_recommended():
    with pytest.raises(ValidationError):
        SchedulingResult(appointment_recommended=True, slot_id=None)


def test_scheduling_no_slot_needed_when_not_recommended():
    s = SchedulingResult(appointment_recommended=False)
    assert s.slot_id is None
    assert s.expedited is False


def test_scheduling_valid_with_slot():
    s = SchedulingResult(appointment_recommended=True, slot_id="SLOT-1", expedited=True)
    assert s.slot_id == "SLOT-1"


# ---- ReferralResult ----

def test_referral_specialty_required_when_needed():
    with pytest.raises(ValidationError):
        ReferralResult(referral_needed=True, referred_specialty=None)


def test_referral_none_when_not_needed():
    r = ReferralResult(referral_needed=False)
    assert r.referred_specialty is None


# ---- SupervisorDecision ----

@pytest.mark.parametrize("worker", ["triage", "scheduling", "referral", "followup", "finish"])
def test_supervisor_decision_accepts_valid_workers(worker):
    assert SupervisorDecision(next_worker=worker).next_worker == worker


def test_supervisor_decision_rejects_unknown_worker():
    with pytest.raises(ValidationError):
        SupervisorDecision(next_worker="pharmacy")


# ---- CarePlan composition + disclaimer ----

def test_careplan_carries_disclaimer_and_children():
    t = TriageResult(urgency=Urgency.ROUTINE, chief_complaint="x", recommended_disposition="y")
    plan = CarePlan(patient_id="SYN-1001", urgency=Urgency.ROUTINE, triage=t)
    assert "not medical advice" in plan.disclaimer.lower()
    assert plan.followup is None


def test_followup_defaults_are_safe_lists():
    f = FollowUpResult()
    assert f.follow_up_actions == []
    assert f.follow_up_window == ""
