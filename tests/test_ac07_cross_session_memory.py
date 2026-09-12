"""AC-07: Memory persists across sessions — new session recalls prior-session facts.

This test writes its proof to evidence/memory_persistence_log.txt (committed evidence).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from src.memory.tiered_memory import TieredMemory

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_LOG = REPO_ROOT / "evidence" / "memory_persistence_log.txt"


def test_memory_persists_across_sessions(tmp_path):
    db = tmp_path / "persist.sqlite"
    pid = "SYN-1001"
    fact = "Patient reported an allergy to penicillin during the first visit."

    # ---- Session A: store a fact, then dispose of the memory object. ----
    sess_a = TieredMemory(db_path=db)
    sess_a.remember_fact(pid, fact, importance=0.95, kind="allergy")
    count_a = sess_a.count(pid)
    sess_a.close()
    del sess_a

    # ---- Session B: a brand-new object over the SAME db (process-restart analogue). ----
    sess_b = TieredMemory(db_path=db)
    recalled = sess_b.recall_text(pid, "any known drug allergies?", k=1)
    count_b = sess_b.count(pid)
    sess_b.close()

    assert count_a == 1 and count_b == 1
    assert recalled and "penicillin" in recalled[0].lower()

    # ---- Commit the proof as evidence. ----
    EVIDENCE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_LOG.open("w", encoding="utf-8") as f:
        f.write("AC-07 CROSS-SESSION MEMORY PERSISTENCE — TEST OUTPUT LOG\n")
        f.write("=" * 60 + "\n")
        f.write(f"generated_at: {dt.datetime.now().isoformat(timespec='seconds')}\n\n")
        f.write("Session A (write):\n")
        f.write(f"  stored fact for {pid}: '{fact}'\n")
        f.write(f"  facts in store after write: {count_a}\n")
        f.write("  memory object closed and deleted (session ends).\n\n")
        f.write("Session B (new object, same on-disk DB = simulated restart):\n")
        f.write("  query: 'any known drug allergies?'\n")
        f.write(f"  recalled: {recalled}\n")
        f.write(f"  facts visible in new session: {count_b}\n\n")
        f.write("RESULT: PASS — prior-session fact recalled in a new session.\n")
    assert EVIDENCE_LOG.exists()
