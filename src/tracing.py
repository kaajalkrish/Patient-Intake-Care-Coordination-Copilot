"""Structured JSON tracing with PII redaction (NFR-04, NFR-05).

Every agent run appends structured events to an in-memory trace that is written to evidence/ as JSON.
Synthetic PII (names, DOBs, raw patient free-text) is redacted before anything is written to a log, so
no PII is ever persisted in plaintext (NFR-05).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO_ROOT / "evidence"

# Patterns for synthetic PII that must not be logged in plaintext.
_PII_PATTERNS = [
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[DOB_REDACTED]"),          # dates of birth
    (re.compile(r"\bSYN-\d{4}\b"), "[PATIENT_ID_REDACTED]"),          # patient ids
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE_REDACTED]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL_REDACTED]"),
]
_NAME_KEYS = {"name", "patient_name", "raw", "raw_patient_text", "free_text"}


def redact(value: Any) -> Any:
    """Recursively redact synthetic PII from any JSON-able value (NFR-05)."""
    if isinstance(value, str):
        out = value
        for pat, repl in _PII_PATTERNS:
            out = pat.sub(repl, out)
        return out
    if isinstance(value, dict):
        red = {}
        for k, v in value.items():
            if k in _NAME_KEYS and isinstance(v, str):
                red[k] = "[REDACTED]"
            else:
                red[k] = redact(v)
        return red
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class Trace:
    """Accumulates structured events for one run and writes redacted JSON evidence."""

    def __init__(self, run_kind: str, meta: dict | None = None):
        self.run_kind = run_kind
        self.started = time.time()
        self.meta = redact(meta or {})
        self.events: list[dict] = []

    def event(self, kind: str, **fields) -> None:
        self.events.append({
            "t": round(time.time() - self.started, 4),
            "kind": kind,
            **redact(fields),
        })

    def to_dict(self) -> dict:
        return {
            "run_kind": self.run_kind,
            "meta": self.meta,
            "duration_s": round(time.time() - self.started, 4),
            "event_count": len(self.events),
            "events": self.events,
        }

    def write(self, filename: str) -> Path:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        path = EVIDENCE_DIR / filename
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path
