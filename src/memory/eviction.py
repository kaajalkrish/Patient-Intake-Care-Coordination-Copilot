"""Memory eviction / importance policy (AC-08).

Hybrid **importance-weighted + TTL + LRU** policy (see docs/memory-design.md). Pure functions so the
policy is unit-testable without a database.

A fact dict has at least: `importance` (0..1), `created_at` (epoch s), `last_access` (epoch s),
`recall_count` (int).
"""
from __future__ import annotations

import math

# Facts at/above this importance are never silently expired by TTL (e.g. allergies).
PROTECTED_IMPORTANCE = 0.9


def is_expired(fact: dict, now: float, ttl_seconds: int) -> bool:
    """True if `fact` is past TTL AND not importance-protected."""
    if fact.get("importance", 0.0) >= PROTECTED_IMPORTANCE:
        return False
    return (now - fact.get("created_at", now)) > ttl_seconds


def eviction_priority(fact: dict, now: float, *, half_life_seconds: float = 604_800.0) -> float:
    """Higher = keep. Lower = evict first.

    Blends importance, recency (exponential decay, default 7-day half-life), and recall frequency
    (log). This single score gives importance-weighted behavior with an LRU-like recency term.
    """
    importance = float(fact.get("importance", 0.0))
    age = max(0.0, now - fact.get("last_access", fact.get("created_at", now)))
    recency = math.exp(-age * math.log(2) / half_life_seconds)  # 1.0 fresh -> 0 old
    frequency = 1.0 + math.log1p(int(fact.get("recall_count", 0)))
    return importance * recency * frequency


def select_evictions(
    facts: list[dict], *, now: float, ttl_seconds: int, max_items: int
) -> list[dict]:
    """Return the facts that should be evicted, with a `reason` set on each.

    1. TTL-expired (non-protected) facts are evicted first.
    2. If still over `max_items`, evict lowest-priority survivors until within capacity.
    """
    evictions: list[dict] = []
    survivors: list[dict] = []
    for f in facts:
        if is_expired(f, now, ttl_seconds):
            evictions.append({**f, "reason": "ttl_expired"})
        else:
            survivors.append(f)

    overflow = len(survivors) - max_items
    if overflow > 0:
        ranked = sorted(survivors, key=lambda f: eviction_priority(f, now))
        for f in ranked[:overflow]:
            evictions.append({**f, "reason": "capacity_lru"})
    return evictions
