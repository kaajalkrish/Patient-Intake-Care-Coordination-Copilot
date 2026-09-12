"""DEEP AC-06/07/08: tiered memory, cross-session persistence, eviction policy — exhaustive.

- AC-06 tiered: short-term working buffer + long-term semantic recall.
- AC-07 cross-session: a fact written by one TieredMemory instance is recalled by a NEW instance
  opened on the same on-disk db (simulating a new process/session).
- AC-08 eviction: TTL expiry, importance protection, capacity LRU — via pure policy functions.
"""
from __future__ import annotations

import time

import pytest

from src.memory.eviction import (
    PROTECTED_IMPORTANCE,
    eviction_priority,
    is_expired,
    select_evictions,
)
from src.memory.tiered_memory import IMPORTANCE, TieredMemory, classify_importance


# ---------------------------------------------------------------- AC-06 tiered

def test_short_term_working_buffer(tmp_memory):
    tmp_memory.remember_working("chief_complaint", "chest pain")
    assert tmp_memory.get_working("chief_complaint") == "chest pain"
    assert tmp_memory.get_working("missing", "def") == "def"


def test_long_term_semantic_recall(tmp_memory):
    tmp_memory.remember_fact("SYN-1001", "Patient is allergic to penicillin",
                             importance=0.95, kind="allergy")
    tmp_memory.remember_fact("SYN-1001", "Patient enjoys morning appointments",
                             importance=0.4, kind="preference")
    hits = tmp_memory.recall_text("SYN-1001", "any drug allergies?", k=1)
    assert hits and "penicillin" in hits[0].lower()


def test_recall_is_patient_scoped(tmp_memory):
    tmp_memory.remember_fact("SYN-1001", "fact A", kind="note")
    tmp_memory.remember_fact("SYN-2002", "fact B", kind="note")
    assert tmp_memory.count("SYN-1001") == 1
    assert tmp_memory.count("SYN-2002") == 1
    assert tmp_memory.recall_text("SYN-2002", "fact") == ["fact B"]


# ---------------------------------------------------------------- AC-07 cross-session

def test_cross_session_persistence(tmp_path):
    db = tmp_path / "persist.sqlite"
    # ---- session 1: write, then close (end of session) ----
    with TieredMemory(db_path=db) as s1:
        s1.remember_fact("SYN-1001", "Allergic to penicillin", importance=0.95, kind="allergy")
        assert s1.count("SYN-1001") == 1
    # ---- session 2: brand-new instance on the same file recalls the prior fact ----
    with TieredMemory(db_path=db) as s2:
        assert s2.count("SYN-1001") == 1
        recalled = s2.recall_text("SYN-1001", "allergies", k=1)
        assert recalled and "penicillin" in recalled[0].lower()


def test_cross_session_multiple_facts_survive(tmp_path):
    db = tmp_path / "multi.sqlite"
    with TieredMemory(db_path=db) as s1:
        s1.remember_fact("P", "takes metformin", importance=0.8, kind="medication")
        s1.remember_fact("P", "type 2 diabetes", importance=0.85, kind="condition")
    with TieredMemory(db_path=db) as s2:
        assert s2.count("P") == 2


# ---------------------------------------------------------------- AC-08 eviction policy

def test_importance_presets_ordered():
    assert IMPORTANCE["allergy"] > IMPORTANCE["condition"] > IMPORTANCE["preference"]
    assert classify_importance("allergy") == IMPORTANCE["allergy"]
    assert classify_importance("unknown_kind") == 0.5


def test_ttl_expiry_for_low_importance():
    now = 1_000_000.0
    old = {"importance": 0.5, "created_at": now - 100, "last_access": now - 100}
    assert is_expired(old, now, ttl_seconds=10) is True
    fresh = {"importance": 0.5, "created_at": now - 5, "last_access": now - 5}
    assert is_expired(fresh, now, ttl_seconds=10) is False


def test_protected_importance_never_ttl_expires():
    now = 1_000_000.0
    critical = {"importance": PROTECTED_IMPORTANCE, "created_at": now - 10_000,
                "last_access": now - 10_000}
    assert is_expired(critical, now, ttl_seconds=1) is False


def test_select_evictions_ttl_then_capacity():
    now = 1_000_000.0
    facts = [
        {"id": 1, "importance": 0.5, "created_at": now - 999, "last_access": now - 999,
         "recall_count": 0},  # expired
        {"id": 2, "importance": 0.95, "created_at": now - 999, "last_access": now - 999,
         "recall_count": 0},  # protected -> survives TTL
        {"id": 3, "importance": 0.6, "created_at": now, "last_access": now, "recall_count": 5},
        {"id": 4, "importance": 0.3, "created_at": now, "last_access": now, "recall_count": 0},
    ]
    evicted = select_evictions(facts, now=now, ttl_seconds=100, max_items=2)
    reasons = {f["id"]: f["reason"] for f in evicted}
    assert reasons.get(1) == "ttl_expired"
    assert 2 not in reasons  # protected
    # after TTL, 3 survivors (2,3,4) but capacity 2 -> lowest priority evicted
    assert any(r == "capacity_lru" for r in reasons.values())


def test_eviction_priority_prefers_important_recent_frequent():
    now = 1_000_000.0
    high = {"importance": 0.9, "created_at": now, "last_access": now, "recall_count": 10}
    low = {"importance": 0.1, "created_at": now - 1_000_000, "last_access": now - 1_000_000,
           "recall_count": 0}
    assert eviction_priority(high, now) > eviction_priority(low, now)


def test_store_enforces_capacity_on_add(tmp_path):
    # Real store path: adding beyond capacity triggers enforce_policy (AC-08 integrated).
    mem = TieredMemory(db_path=tmp_path / "cap.sqlite", ttl_seconds=10**9, max_items=3)
    for i in range(6):
        mem.remember_fact("P", f"note {i}", importance=0.5, kind="note")
    assert mem.count("P") <= 3
    mem.close()
