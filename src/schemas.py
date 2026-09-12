"""Pydantic structured-output models validated at node hand-off boundaries (AC-04).

Every worker agent returns one of these models. Invalid output (missing/extra/typed-wrong
fields) raises `ValidationError`, which the reflection loop can catch and re-plan on (AC-12).
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Urgency(str, Enum):
    """Acuity level. Ordered emergent > urgent > routine > self_care."""

    EMERGENT = "emergent"      # potential emergency — expedite / direct to ED
    URGENT = "urgent"          # same/next-day
    ROUTINE = "routine"        # standard scheduling
    SELF_CARE = "self_care"    # education / self-management, no appointment needed

    @property
    def rank(self) -> int:
        return {"emergent": 3, "urgent": 2, "routine": 1, "self_care": 0}[self.value]


class TriageResult(BaseModel):
    """Output of the triage worker."""

    urgency: Urgency
    chief_complaint: str = Field(..., min_length=1, description="Normalized chief complaint")
    recommended_disposition: str = Field(..., min_length=1)
    specialty: str = Field(
        default="general_practice",
        description="Care specialty the request maps to (e.g. cardiology).",
    )
    red_flags: list[str] = Field(default_factory=list)
    guideline_citations: list[str] = Field(
        default_factory=list, description="Care-pathway/guideline snippets used (from RAG)."
    )
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    rationale: str = Field(default="", description="Short, non-diagnostic reasoning.")

    model_config = {"use_enum_values": False}


class SchedulingResult(BaseModel):
    """Output of the scheduling worker."""

    appointment_recommended: bool
    slot_id: str | None = None
    provider: str | None = None
    specialty: str = "general_practice"
    when: str | None = Field(default=None, description="ISO-ish datetime string of the proposed slot.")
    expedited: bool = Field(default=False, description="True if urgency forced an expedited slot.")
    notes: str = ""

    @field_validator("slot_id")
    @classmethod
    def _slot_required_if_recommended(cls, v, info):
        if info.data.get("appointment_recommended") and not v:
            raise ValueError("slot_id required when appointment_recommended is True")
        return v


class ReferralResult(BaseModel):
    """Output of the referral worker."""

    referral_needed: bool
    referred_specialty: str | None = None
    reason: str = ""
    out_of_scope: bool = Field(
        default=False, description="True if the need is outside clinic scope (refer out)."
    )

    @field_validator("referred_specialty")
    @classmethod
    def _specialty_required(cls, v, info):
        if info.data.get("referral_needed") and not v:
            raise ValueError("referred_specialty required when referral_needed is True")
        return v


class FollowUpResult(BaseModel):
    """Output of the follow-up worker."""

    follow_up_actions: list[str] = Field(default_factory=list)
    follow_up_window: str = Field(default="", description="e.g. '2 weeks', '48 hours'.")
    coordination_notes: str = ""
    patient_instructions: str = Field(
        default="", description="Non-diagnostic, general coordination instructions only."
    )


class SupervisorDecision(BaseModel):
    """Supervisor routing decision — which worker runs next (AC-02/AC-03)."""

    next_worker: Literal["triage", "scheduling", "referral", "followup", "finish"]
    reason: str = ""


class CarePlan(BaseModel):
    """Final composed, validated coordination plan returned to the caller."""

    patient_id: str
    urgency: Urgency
    triage: TriageResult
    scheduling: SchedulingResult | None = None
    referral: ReferralResult | None = None
    followup: FollowUpResult | None = None
    summary: str = ""
    disclaimer: str = (
        "Coordination aid only. Not medical advice or a diagnosis. "
        "A clinician must review all recommendations."
    )
