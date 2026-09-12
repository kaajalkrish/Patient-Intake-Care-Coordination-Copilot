"""DEEP AC-01: typed state object shared across nodes — exhaustive structural checks."""
from __future__ import annotations

import operator
import typing

from src.state import PatientIntakeState, QuarantinedText, new_state


def test_new_state_initializes_every_declared_key():
    st = new_state(patient_id="SYN-1001", session_id="s", thread_id="t",
                   quarantined_input=QuarantinedText(raw="hi", sanitized="hi",
                                                     injection_flagged=False))
    for key in PatientIntakeState.__annotations__:
        assert key in st, f"new_state did not initialize {key}"


def test_new_state_defaults_are_typed_containers():
    st = new_state(patient_id="p", session_id="s", thread_id="t",
                   quarantined_input=QuarantinedText(raw="", sanitized="", injection_flagged=False))
    assert st["messages"] == []
    assert st["working_memory"] == {}
    assert st["recalled_facts"] == []
    assert st["completed_workers"] == []
    assert st["route_history"] == []
    assert st["triage_result"] is None
    assert st["next_worker"] == "supervisor"


def test_quarantined_input_is_isolated_field():
    q = QuarantinedText(raw="secret", sanitized="secret", injection_flagged=False)
    st = new_state(patient_id="p", session_id="s", thread_id="t", quarantined_input=q)
    # untrusted text lives in its own field, not merged into messages (NFR-03 / AC-01)
    assert st["quarantined_input"]["raw"] == "secret"
    assert st["messages"] == []


def test_reducers_are_annotated_for_append():
    # route_history / completed_workers use operator.add reducers; messages uses add_messages.
    hints = typing.get_type_hints(PatientIntakeState, include_extras=True)
    for field in ("route_history", "completed_workers", "errors", "reflection_notes"):
        meta = getattr(hints[field], "__metadata__", ())
        assert operator.add in meta, f"{field} should reduce with operator.add"
    assert "messages" in hints  # add_messages reducer applied in state definition
