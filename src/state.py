"""Typed LangGraph state shared across all nodes (AC-01).

`PatientIntakeState` is a TypedDict — LangGraph's native, testable state schema. Structured
worker results are the Pydantic models from `schemas.py`, giving typed hand-off boundaries (AC-04).
Untrusted patient text is held separately in `quarantined_input` (NFR-03 / Context-Isolation Rule).
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages

from .schemas import (
    FollowUpResult,
    ReferralResult,
    SchedulingResult,
    TriageResult,
)


class QuarantinedText(TypedDict):
    """A wrapper marking free text as UNTRUSTED patient-reported content (NFR-03).

    `raw` is never placed in a system prompt. `sanitized` has delimiter/role markers
    neutralized. `injection_flagged` records whether prompt-injection heuristics fired.
    """

    raw: str
    sanitized: str
    injection_flagged: bool


class PatientIntakeState(TypedDict, total=False):
    """The single typed state object read/written by every node in the graph (AC-01)."""

    # ---- Identity / session ----
    session_id: str
    thread_id: str
    patient_id: str

    # ---- Input (untrusted patient free-text is quarantined) ----
    quarantined_input: QuarantinedText

    # ---- Conversation (append-only via reducer) ----
    messages: Annotated[list, add_messages]

    # ---- Memory tiers ----
    working_memory: dict[str, Any]           # short-term, current turn
    recalled_facts: list[dict[str, Any]]     # selected long-term/semantic facts

    # ---- Retrieval (agentic RAG) ----
    rag_context: list[dict[str, Any]]        # passages the agent chose to retrieve

    # ---- Routing / control (AC-02, AC-03) ----
    route_history: Annotated[list[str], operator.add]
    next_worker: str
    completed_workers: Annotated[list[str], operator.add]
    urgency: str

    # ---- Structured worker outputs (AC-04) ----
    triage_result: TriageResult | None
    scheduling_result: SchedulingResult | None
    referral_result: ReferralResult | None
    followup_result: FollowUpResult | None

    # ---- Reflection / self-healing (AC-12, NFR-07) ----
    errors: Annotated[list[dict[str, Any]], operator.add]
    retry_counts: dict[str, int]
    reflection_notes: Annotated[list[str], operator.add]

    # ---- Output ----
    final_plan: dict[str, Any] | None
    final_summary: str


def new_state(
    *,
    patient_id: str,
    session_id: str,
    thread_id: str,
    quarantined_input: QuarantinedText,
) -> PatientIntakeState:
    """Build a fresh, fully-initialized state object."""
    return PatientIntakeState(
        session_id=session_id,
        thread_id=thread_id,
        patient_id=patient_id,
        quarantined_input=quarantined_input,
        messages=[],
        working_memory={},
        recalled_facts=[],
        rag_context=[],
        route_history=[],
        next_worker="supervisor",
        completed_workers=[],
        urgency="",
        triage_result=None,
        scheduling_result=None,
        referral_result=None,
        followup_result=None,
        errors=[],
        retry_counts={},
        reflection_notes=[],
        final_plan=None,
        final_summary="",
    )
