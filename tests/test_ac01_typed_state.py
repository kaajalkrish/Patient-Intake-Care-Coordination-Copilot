"""AC-01: Built on LangGraph with an explicit typed state object shared across nodes."""
from __future__ import annotations

import typing

from src.graph import build_graph
from src.state import PatientIntakeState, new_state


def test_state_is_typeddict_with_required_fields():
    # TypedDict carries its field types in __annotations__.
    assert typing.is_typeddict(PatientIntakeState)
    ann = PatientIntakeState.__annotations__
    for field in ["patient_id", "quarantined_input", "messages", "working_memory",
                  "recalled_facts", "triage_result", "next_worker", "completed_workers"]:
        assert field in ann, f"typed state missing field {field}"


def test_new_state_factory_initializes_all_fields():
    st = new_state(
        patient_id="SYN-1001", session_id="s", thread_id="t",
        quarantined_input={"raw": "x", "sanitized": "x", "injection_flagged": False},
    )
    assert st["patient_id"] == "SYN-1001"
    assert st["completed_workers"] == []
    assert st["triage_result"] is None


def test_graph_uses_the_typed_state_schema():
    graph = build_graph()
    builder = graph.builder
    # Depending on langgraph version the schema is exposed as `schema` or `state_schema`.
    schema = getattr(builder, "schema", None) or getattr(builder, "state_schema", None)
    assert schema is PatientIntakeState


def test_typed_state_flows_through_nodes():
    """Behavioral proof the same typed state is read/written across nodes."""
    from src.runner import run_intake

    final = run_intake(patient_id="SYN-1001", text="mild cough since yesterday",
                       use_checkpointer=False)
    # Fields written by different nodes are all present in the one state object.
    assert "completed_workers" in final and "triage" in final["completed_workers"]
    assert final["patient_id"] == "SYN-1001"
