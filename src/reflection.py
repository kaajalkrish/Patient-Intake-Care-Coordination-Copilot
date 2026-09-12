"""Reflection / self-healing / fallback loop (AC-12, NFR-07).

Two mechanisms, both producing an evidenced trace:

1. `guard(...)` wraps any worker node so that on an exception (tool failure, LLM outage, schema
   validation error) it RETRIES with backoff and, if still failing, falls back to a safe default —
   recording each step as an error + reflection event.

2. `reflection_node(...)` inspects the triage output and, if confidence is below threshold, RE-PLANS:
   it re-runs triage once more (self-healing) and records the reflection.

Both record events consumed by evidence/reflection_trace.json.
"""
from __future__ import annotations

from typing import Callable

from .state import PatientIntakeState
from .tracing import Trace

LOW_CONFIDENCE_THRESHOLD = 0.35
MAX_WORKER_RETRIES = 2


def guard(worker_name: str, fn: Callable[[PatientIntakeState], dict],
          state: PatientIntakeState, trace: Trace | None = None,
          *, fallback: dict | None = None) -> dict:
    """Run a worker with retry + fallback self-healing (AC-12)."""
    retries = dict(state.get("retry_counts", {}))
    last_err: Exception | None = None
    for attempt in range(MAX_WORKER_RETRIES + 1):
        try:
            result = fn(state)
            if attempt > 0 and trace:
                trace.event("self_heal", worker=worker_name, outcome="recovered_on_retry",
                            attempt=attempt)
            return result
        except Exception as e:  # tool/model/validation failure
            last_err = e
            retries[worker_name] = retries.get(worker_name, 0) + 1
            if trace:
                trace.event("worker_error", worker=worker_name, attempt=attempt,
                            error=type(e).__name__, detail=str(e)[:200])
    # Exhausted retries -> safe fallback (explicit exit condition, NFR-07).
    if trace:
        trace.event("fallback", worker=worker_name,
                    reason=f"exhausted retries: {type(last_err).__name__ if last_err else 'unknown'}")
    out = dict(fallback or {})
    out.setdefault("errors", []).append(
        {"worker": worker_name, "error": str(last_err) if last_err else "unknown"}
    )
    out.setdefault("reflection_notes", []).append(
        f"{worker_name}: fell back to safe default after {MAX_WORKER_RETRIES + 1} attempts."
    )
    out["retry_counts"] = retries
    return out


def reflection_node(state: PatientIntakeState, trace: Trace | None = None,
                    triage_fn: Callable[[PatientIntakeState], dict] | None = None) -> dict:
    """Re-plan on low-confidence triage (self-healing). Runs after triage."""
    triage = state.get("triage_result")
    if triage is None:
        return {}
    if triage.confidence >= LOW_CONFIDENCE_THRESHOLD:
        if trace:
            trace.event("reflection", verdict="accept", confidence=triage.confidence)
        return {"reflection_notes": [f"triage accepted (confidence={triage.confidence})"]}

    # Low confidence -> re-plan once.
    if trace:
        trace.event("reflection", verdict="re_plan", confidence=triage.confidence,
                    reason="triage confidence below threshold")
    if triage_fn is not None and not state.get("_reflected"):
        redo = triage_fn({**state, "_reflected": True})
        redo.setdefault("reflection_notes", []).append(
            f"re-planned triage due to low confidence ({triage.confidence})"
        )
        return redo
    return {"reflection_notes": [f"low confidence noted ({triage.confidence}); accepted with caution"]}
