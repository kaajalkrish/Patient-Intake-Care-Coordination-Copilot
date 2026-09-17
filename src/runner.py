"""Run an intake request through the graph and collect evidence.

`run_intake` is the reusable entry point used by the CLI (main.py), the evidence capture script, and
the tests. It wires the trace, tiered memory, and (optionally) MCP-backed scheduling.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from .config import settings
from .context import strategies
from .graph import build_graph, make_sqlite_checkpointer
from .memory.tiered_memory import TieredMemory
from .state import new_state
from .tracing import Trace


def run_intake(
    *,
    patient_id: str,
    text: str,
    session_id: str | None = None,
    thread_id: str | None = None,
    memory: TieredMemory | None = None,
    use_checkpointer: bool = True,
    mcp_slot_fn=None,
    trace: Trace | None = None,
    checkpoint_db: str | Path | None = None,
) -> dict:
    """Execute one intake turn. Returns the final graph state (dict)."""
    session_id = session_id or f"sess-{uuid.uuid4().hex[:8]}"
    thread_id = thread_id or f"thread-{uuid.uuid4().hex[:8]}"
    trace = trace or Trace("intake_run", {"patient_id": patient_id, "session_id": session_id})

    owns_memory = memory is None
    memory = memory or TieredMemory()

    # ISOLATE strategy (P12/NFR-03): quarantine untrusted patient free-text before anything else.
    q = strategies.isolate(text, trace)
    trace.event("input_quarantined", injection_flagged=q["injection_flagged"])

    checkpointer = None
    if use_checkpointer:
        checkpointer = make_sqlite_checkpointer(checkpoint_db or settings.path(settings.checkpoint_db))

    graph = build_graph(checkpointer=checkpointer, trace=trace, memory=memory,
                        mcp_slot_fn=mcp_slot_fn)

    init = new_state(patient_id=patient_id, session_id=session_id,
                     thread_id=thread_id, quarantined_input=q)
    config = {"configurable": {"thread_id": thread_id}}
    final_state = graph.invoke(init, config=config)

    if owns_memory:
        memory.close()
    return final_state


def format_plan(final_state: dict) -> str:
    """Human-readable rendering of the final care plan for the CLI."""
    plan = final_state.get("final_plan")
    lines = ["=" * 60, "CARE COORDINATION PLAN (synthetic — not medical advice)", "=" * 60]
    if not plan:
        lines.append("No plan produced (intake incomplete).")
        return "\n".join(lines)
    lines.append(f"Patient:   {plan['patient_id']}")
    lines.append(f"Urgency:   {plan['urgency']}")
    t = plan["triage"]
    lines.append(f"Triage:    {t['chief_complaint']} -> {t['recommended_disposition']}")
    lines.append(f"           specialty={t['specialty']} confidence={t['confidence']}")
    if t.get("red_flags"):
        lines.append(f"           RED FLAGS: {', '.join(t['red_flags'])}")
    if t.get("guideline_citations"):
        lines.append(f"           guidelines: {', '.join(t['guideline_citations'])}")
    s = plan.get("scheduling")
    if s:
        lines.append(f"Schedule:  recommended={s['appointment_recommended']} "
                     f"expedited={s['expedited']} slot={s.get('slot_id')} when={s.get('when')}")
    r = plan.get("referral")
    if r:
        lines.append(f"Referral:  needed={r['referral_needed']} to={r.get('referred_specialty')} "
                     f"out_of_scope={r['out_of_scope']}")
    f = plan.get("followup")
    if f:
        lines.append(f"Follow-up: window={f['follow_up_window']}")
        for a in f["follow_up_actions"]:
            lines.append(f"           - {a}")
    lines.append("-" * 60)
    lines.append(plan["disclaimer"])
    return "\n".join(lines)
