"""AC-06: Tiered memory (short-term working + long-term/semantic); recalls an earlier fact."""
from __future__ import annotations


def test_short_term_working_memory(tmp_memory):
    tmp_memory.remember_working("chief_complaint", "chest pain")
    assert tmp_memory.get_working("chief_complaint") == "chest pain"


def test_long_term_semantic_recall_of_earlier_fact(tmp_memory):
    pid = "SYN-1001"
    tmp_memory.remember_fact(pid, "Patient is allergic to penicillin.", importance=0.95,
                             kind="allergy")
    tmp_memory.remember_fact(pid, "Patient prefers morning appointments.", importance=0.4,
                             kind="preference")
    # Semantically different query still recalls the allergy fact.
    hits = tmp_memory.recall_text(pid, "does the patient have any drug allergies?", k=1)
    assert any("penicillin" in h.lower() for h in hits)


def test_recall_is_scoped_per_patient(tmp_memory):
    tmp_memory.remember_fact("SYN-1001", "allergic to penicillin", importance=0.95, kind="allergy")
    tmp_memory.remember_fact("SYN-1002", "takes metformin", importance=0.8, kind="medication")
    assert tmp_memory.recall_text("SYN-1002", "allergies?", k=3)  # only 1002's facts
    assert all("penicillin" not in h.lower() for h in tmp_memory.recall_text("SYN-1002", "meds", k=3))
