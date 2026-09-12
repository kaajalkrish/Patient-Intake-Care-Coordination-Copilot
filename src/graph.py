"""LangGraph assembly (AC-01/02/03/04/05).

Topology (supervisor pattern):

    START -> intake -> supervisor -> {triage|scheduling|referral|followup|finalize}
    triage -> reflection -> supervisor        (self-healing re-plan on low confidence)
    scheduling/referral/followup -> supervisor (loop back for the next decision)
    finalize -> END

- Typed state: `PatientIntakeState` (AC-01).
- Supervisor routes to specialized workers (AC-02) via CONDITIONAL edges on `next_worker` (AC-03).
- Worker outputs are validated Pydantic objects at hand-off (AC-04).
- A checkpointer persists state for pause/resume (AC-05).
"""
from __future__ import annotations

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from .agents.base import detect_condition
from .agents.followup import followup_agent
from .agents.referral import referral_agent
from .agents.scheduling import scheduling_agent
from .agents.supervisor import supervisor_node
from .agents.triage import triage_agent
from .context.summarization import summarize_if_needed
from .memory.tiered_memory import TieredMemory, classify_importance
from .reflection import guard, reflection_node
from .schemas import CarePlan, Urgency
from .state import PatientIntakeState
from .tracing import Trace


def build_graph(*, checkpointer=None, trace: Trace | None = None,
                memory: TieredMemory | None = None, mcp_slot_fn=None,
                interrupt_before: list[str] | None = None):
    """Construct and compile the care-coordination graph.

    `interrupt_before` pauses the graph before the named nodes (used to demonstrate pause/resume
    via the checkpointer, AC-05).
    """

    def intake_node(state: PatientIntakeState) -> dict:
        q = state["quarantined_input"]
        pid = state["patient_id"]
        # SELECT: pull only relevant long-term facts for this patient/request.
        recalled = memory.recall(pid, q["sanitized"], k=3) if memory else []
        # COMPRESS: summarize the running thread if it is long (NFR-08).
        _, summary = summarize_if_needed(state.get("messages", []))
        wm = {"condition_hint": detect_condition(q["sanitized"])}
        if summary:
            wm["thread_summary"] = summary
        if trace:
            trace.event("intake", recalled_facts=len(recalled),
                        injection_flagged=q["injection_flagged"], compressed=bool(summary))
        return {"recalled_facts": recalled, "working_memory": wm}

    def _triage(state):  # bound for guard + reflection re-plan
        return triage_agent(state, trace)

    def triage_node(state: PatientIntakeState) -> dict:
        return guard("triage", _triage, state, trace, fallback={
            "triage_result": None, "urgency": "urgent",
            "completed_workers": ["triage"], "route_history": ["triage(fallback)"],
        })

    def reflection_wrapper(state: PatientIntakeState) -> dict:
        return reflection_node(state, trace, triage_fn=_triage)

    def scheduling_node(state: PatientIntakeState) -> dict:
        return guard("scheduling",
                     lambda s: scheduling_agent(s, trace, mcp_slot_fn=mcp_slot_fn),
                     state, trace, fallback={
                         "completed_workers": ["scheduling"],
                         "route_history": ["scheduling(fallback)"]})

    def referral_node(state: PatientIntakeState) -> dict:
        return guard("referral", lambda s: referral_agent(s, trace), state, trace,
                     fallback={"completed_workers": ["referral"],
                               "route_history": ["referral(fallback)"]})

    def followup_node(state: PatientIntakeState) -> dict:
        return guard("followup", lambda s: followup_agent(s, trace), state, trace,
                     fallback={"completed_workers": ["followup"],
                               "route_history": ["followup(fallback)"]})

    def supervisor(state: PatientIntakeState) -> dict:
        return supervisor_node(state, trace)

    def finalize_node(state: PatientIntakeState) -> dict:
        triage = state.get("triage_result")
        urgency = Urgency(state.get("urgency") or (triage.urgency.value if triage else "routine"))
        plan = None
        if triage is not None:
            plan = CarePlan(
                patient_id=state["patient_id"],
                urgency=urgency,
                triage=triage,
                scheduling=state.get("scheduling_result"),
                referral=state.get("referral_result"),
                followup=state.get("followup_result"),
                summary=_summarize_plan(state),
            )
            # WRITE: persist salient facts to long-term memory for future sessions.
            if memory is not None:
                memory.remember_fact(
                    state["patient_id"],
                    f"Presented with {triage.chief_complaint} (urgency {urgency.value}).",
                    importance=classify_importance("condition"),
                    kind="condition",
                )
        if trace:
            trace.event("finalize", urgency=urgency.value, has_plan=plan is not None)
        return {
            "final_plan": plan.model_dump(mode="json") if plan else None,
            "final_summary": _summarize_plan(state),
            "next_worker": "finish",
        }

    def route_from_supervisor(state: PatientIntakeState) -> str:
        nxt = state.get("next_worker", "finish")
        return "finalize" if nxt == "finish" else nxt

    g = StateGraph(PatientIntakeState)
    g.add_node("intake", intake_node)
    g.add_node("supervisor", supervisor)
    g.add_node("triage", triage_node)
    g.add_node("reflection", reflection_wrapper)
    g.add_node("scheduling", scheduling_node)
    g.add_node("referral", referral_node)
    g.add_node("followup", followup_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "intake")
    g.add_edge("intake", "supervisor")
    # Conditional routing driven by state (AC-03).
    g.add_conditional_edges("supervisor", route_from_supervisor, {
        "triage": "triage",
        "scheduling": "scheduling",
        "referral": "referral",
        "followup": "followup",
        "finalize": "finalize",
    })
    g.add_edge("triage", "reflection")
    g.add_edge("reflection", "supervisor")
    g.add_edge("scheduling", "supervisor")
    g.add_edge("referral", "supervisor")
    g.add_edge("followup", "supervisor")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer, interrupt_before=interrupt_before or [])


def _summarize_plan(state: PatientIntakeState) -> str:
    triage = state.get("triage_result")
    if not triage:
        return "Intake incomplete."
    parts = [f"Urgency: {state.get('urgency', '')}.",
             f"Complaint: {triage.chief_complaint}.",
             f"Disposition: {triage.recommended_disposition}"]
    sched = state.get("scheduling_result")
    if sched and sched.appointment_recommended:
        parts.append(f"Appointment: {sched.slot_id} ({'expedited' if sched.expedited else 'routine'}).")
    ref = state.get("referral_result")
    if ref and ref.referral_needed:
        parts.append(f"Referral: {ref.referred_specialty}.")
    return " ".join(parts)


def make_sqlite_checkpointer(db_path: str | Path):
    """Create a SQLite checkpointer for pause/resume (AC-05). Caller manages its lifecycle."""
    import sqlite3

    from langgraph.checkpoint.sqlite import SqliteSaver

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)
