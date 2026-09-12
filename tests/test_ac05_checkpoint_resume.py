"""AC-05: A checkpointer persists graph state so an intake case can be paused and resumed."""
from __future__ import annotations

from src.context.quarantine import quarantine
from src.graph import build_graph, make_sqlite_checkpointer
from src.memory.tiered_memory import TieredMemory
from src.state import new_state


def test_pause_and_resume_via_checkpointer(tmp_path):
    ckpt = make_sqlite_checkpointer(tmp_path / "ckpt.sqlite")
    mem = TieredMemory(db_path=tmp_path / "mem.sqlite")
    # Interrupt BEFORE scheduling so we can prove state was persisted mid-run.
    graph = build_graph(checkpointer=ckpt, memory=mem, interrupt_before=["scheduling"])

    q = quarantine("crushing chest pain radiating to my left arm, short of breath")
    init = new_state(patient_id="SYN-1004", session_id="s", thread_id="thread-1",
                     quarantined_input=q)
    config = {"configurable": {"thread_id": "thread-1"}}

    # First invoke pauses at the interrupt.
    graph.invoke(init, config=config)
    snapshot = graph.get_state(config)
    # Triage already ran and its result is persisted; scheduling has not.
    assert snapshot.values["triage_result"] is not None
    assert "triage" in snapshot.values["completed_workers"]
    assert "scheduling" not in snapshot.values.get("completed_workers", [])
    assert snapshot.next  # there is a pending next node -> the run is paused

    # Resume from the checkpoint (no new input) — completes the run.
    graph.invoke(None, config=config)
    final = graph.get_state(config)
    assert "scheduling" in final.values["completed_workers"]
    assert final.values["final_plan"] is not None
    mem.close()


def test_resume_recovers_prior_state_in_a_fresh_graph_object(tmp_path):
    """A brand-new graph object bound to the same checkpoint DB resumes the paused run."""
    db = tmp_path / "ckpt.sqlite"
    mem = TieredMemory(db_path=tmp_path / "mem.sqlite")
    q = quarantine("itchy rash on forearm, no fever")
    config = {"configurable": {"thread_id": "thread-resume"}}

    ckpt1 = make_sqlite_checkpointer(db)
    g1 = build_graph(checkpointer=ckpt1, memory=mem, interrupt_before=["scheduling"])
    g1.invoke(new_state(patient_id="SYN-1003", session_id="s", thread_id="thread-resume",
                        quarantined_input=q), config=config)

    # New checkpointer + graph over the same DB file (simulates a process restart).
    ckpt2 = make_sqlite_checkpointer(db)
    g2 = build_graph(checkpointer=ckpt2, memory=mem)
    restored = g2.get_state(config)
    assert restored.values["triage_result"] is not None  # recovered from disk
    g2.invoke(None, config=config)
    assert g2.get_state(config).values["final_plan"] is not None
    mem.close()
