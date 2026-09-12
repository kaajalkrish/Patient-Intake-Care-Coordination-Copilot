"""Tiered memory API (AC-06) — short-term working buffer + long-term semantic store.

- **Short-term / working**: a plain dict scratchpad for the current turn (also mirrored into the
  LangGraph state's `working_memory`, which the checkpointer persists for pause/resume).
- **Long-term / semantic**: `SemanticMemoryStore`, persistent across sessions (AC-07) with an
  eviction/importance policy (AC-08).

`recall()` is the "select" strategy: it pulls only the most relevant long-term facts for a query.
"""
from __future__ import annotations

import time
from pathlib import Path

from ..config import settings
from .store import SemanticMemoryStore


class TieredMemory:
    def __init__(self, db_path: str | Path | None = None, *,
                 ttl_seconds: int | None = None, max_items: int | None = None):
        db_path = db_path or settings.path(settings.memory_db)
        self.store = SemanticMemoryStore(
            db_path,
            ttl_seconds=ttl_seconds if ttl_seconds is not None else settings.memory_ttl_seconds,
            max_items=max_items if max_items is not None else settings.memory_max_items,
        )
        self.working: dict = {}  # short-term, current turn

    # ---- short-term ----
    def remember_working(self, key: str, value) -> None:
        self.working[key] = value

    def get_working(self, key: str, default=None):
        return self.working.get(key, default)

    # ---- long-term ----
    def remember_fact(self, patient_id: str, text: str, *, importance: float = 0.5,
                      kind: str = "note", now: float | None = None) -> int:
        return self.store.add(patient_id, text, importance=importance, kind=kind, now=now)

    def recall(self, patient_id: str, query: str, *, k: int = 3) -> list[dict]:
        return self.store.recall(patient_id, query, k=k)

    def recall_text(self, patient_id: str, query: str, *, k: int = 3) -> list[str]:
        return [f["text"] for f in self.recall(patient_id, query, k=k)]

    def count(self, patient_id: str) -> int:
        return self.store.count(patient_id)

    def close(self) -> None:
        self.store.close()

    # context manager convenience (used to simulate a session boundary in tests, AC-07)
    def __enter__(self) -> "TieredMemory":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


# Importance presets so safety-critical facts survive eviction (see eviction.PROTECTED_IMPORTANCE).
IMPORTANCE = {
    "allergy": 0.95,
    "condition": 0.85,
    "medication": 0.8,
    "preference": 0.4,
    "smalltalk": 0.1,
    "note": 0.5,
}


def classify_importance(kind: str) -> float:
    return IMPORTANCE.get(kind, 0.5)


def _now() -> float:
    return time.time()
