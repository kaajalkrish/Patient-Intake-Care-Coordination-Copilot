"""Persistent semantic memory store — SQLite (metadata) + embedded vectors (AC-06/07/08).

Backed by an on-disk SQLite file so facts persist across sessions/process restarts (AC-07). Each fact
stores its embedding (JSON blob); recall is cosine top-k. No external DB service (No-Docker rule).

This is a from-scratch embedded vector store (open-source, deterministic). A Chroma-backed alternative
is available via `MEMORY_BACKEND=chroma`, but the default SQLite backend is used for deterministic
cross-session tests.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path

from .embeddings import cosine, embed
from .eviction import select_evictions

log = logging.getLogger("copilot.memory")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   TEXT NOT NULL,
    text         TEXT NOT NULL,
    kind         TEXT DEFAULT 'note',
    importance   REAL DEFAULT 0.5,
    created_at   REAL NOT NULL,
    last_access  REAL NOT NULL,
    recall_count INTEGER DEFAULT 0,
    embedding    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_patient ON facts(patient_id);
"""


class SemanticMemoryStore:
    """On-disk semantic memory with importance + eviction."""

    def __init__(self, db_path: str | Path, *, ttl_seconds: int = 2_592_000, max_items: int = 200):
        self.db_path = str(db_path)
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ---- write ----
    def add(self, patient_id: str, text: str, *, importance: float = 0.5,
            kind: str = "note", now: float | None = None) -> int:
        now = now or time.time()
        vec = json.dumps(embed(text))
        cur = self._conn.execute(
            "INSERT INTO facts(patient_id,text,kind,importance,created_at,last_access,"
            "recall_count,embedding) VALUES (?,?,?,?,?,?,0,?)",
            (patient_id, text, kind, float(importance), now, now, vec),
        )
        self._conn.commit()
        self.enforce_policy(patient_id, now=now)
        return int(cur.lastrowid)

    # ---- read / select ----
    def recall(self, patient_id: str, query: str, *, k: int = 3,
               now: float | None = None) -> list[dict]:
        """Return top-k semantically-similar facts, updating recall stats (Select strategy)."""
        now = now or time.time()
        rows = self._conn.execute(
            "SELECT * FROM facts WHERE patient_id=?", (patient_id,)
        ).fetchall()
        if not rows:
            return []
        qv = embed(query)
        scored = []
        for r in rows:
            score = cosine(qv, json.loads(r["embedding"]))
            scored.append((score, r))
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:k]
        results = []
        for score, r in top:
            self._conn.execute(
                "UPDATE facts SET recall_count=recall_count+1, last_access=? WHERE id=?",
                (now, r["id"]),
            )
            results.append({
                "id": r["id"], "text": r["text"], "kind": r["kind"],
                "importance": r["importance"], "score": round(score, 4),
                "recall_count": r["recall_count"] + 1,
            })
        self._conn.commit()
        # Explicit recall-event log so cross-session recall is observable in traces (AC-06/07, P15).
        log.info("memory.recall: patient=%s query=%r -> %d hit(s) top_score=%s",
                 patient_id, query[:60], len(results),
                 results[0]["score"] if results else None)
        return results

    def all_facts(self, patient_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM facts WHERE patient_id=?", (patient_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self, patient_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM facts WHERE patient_id=?", (patient_id,)
        ).fetchone()
        return int(row["c"])

    # ---- eviction (AC-08) ----
    def enforce_policy(self, patient_id: str, *, now: float | None = None) -> list[dict]:
        now = now or time.time()
        facts = self.all_facts(patient_id)
        to_evict = select_evictions(
            facts, now=now, ttl_seconds=self.ttl_seconds, max_items=self.max_items
        )
        for f in to_evict:
            self._conn.execute("DELETE FROM facts WHERE id=?", (f["id"],))
        self._conn.commit()
        if to_evict:
            # Explicit eviction log so the importance/TTL/LRU policy is observable (AC-08, P17).
            reasons = {}
            for f in to_evict:
                reasons[f["reason"]] = reasons.get(f["reason"], 0) + 1
            log.info("memory.evict: patient=%s removed %d fact(s) reasons=%s",
                     patient_id, len(to_evict), reasons)
        return to_evict

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
