"""AC-08: Memory eviction / importance policy (TTL + capacity/LRU + importance protection)."""
from __future__ import annotations

import time

from src.memory.eviction import (
    PROTECTED_IMPORTANCE,
    eviction_priority,
    is_expired,
    select_evictions,
)
from src.memory.tiered_memory import TieredMemory


def _fact(imp, created, last=None, recalls=0, _id=0):
    return {"id": _id, "importance": imp, "created_at": created,
            "last_access": last if last is not None else created, "recall_count": recalls}


def test_ttl_expiry_respects_importance_protection():
    now = time.time()
    old = now - 10_000
    low = _fact(0.2, old, _id=1)
    protected = _fact(PROTECTED_IMPORTANCE, old, _id=2)
    assert is_expired(low, now, ttl_seconds=5_000) is True
    assert is_expired(protected, now, ttl_seconds=5_000) is False


def test_capacity_eviction_removes_lowest_priority_first():
    now = time.time()
    facts = [
        _fact(0.95, now, recalls=5, _id=1),   # important + used -> keep
        _fact(0.1, now - 500_000, recalls=0, _id=2),  # low + stale -> evict
        _fact(0.5, now, recalls=1, _id=3),
    ]
    evicted = select_evictions(facts, now=now, ttl_seconds=10**9, max_items=2)
    assert len(evicted) == 1
    assert evicted[0]["id"] == 2
    assert evicted[0]["reason"] == "capacity_lru"


def test_priority_orders_importance_and_recency():
    now = time.time()
    fresh_important = eviction_priority(_fact(0.9, now, recalls=3), now)
    stale_trivial = eviction_priority(_fact(0.1, now - 1_000_000, recalls=0), now)
    assert fresh_important > stale_trivial


def test_store_enforces_capacity_on_write(tmp_path):
    mem = TieredMemory(db_path=tmp_path / "m.sqlite", max_items=3, ttl_seconds=10**9)
    pid = "SYN-1001"
    mem.remember_fact(pid, "allergic to penicillin", importance=0.95, kind="allergy")
    for i in range(5):
        mem.remember_fact(pid, f"small talk note {i}", importance=0.1, kind="smalltalk")
    assert mem.count(pid) <= 3
    # The important allergy fact survives eviction.
    assert any("penicillin" in t.lower() for t in mem.recall_text(pid, "allergy", k=3))
    mem.close()
