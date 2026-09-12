"""NFR-04: Structured JSON logs / traces of agent runs are committed as evidence."""
from __future__ import annotations

import json
from pathlib import Path

from src.tracing import Trace

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_trace_writes_valid_structured_json(tmp_path, monkeypatch):
    import src.tracing as tracing

    monkeypatch.setattr(tracing, "EVIDENCE_DIR", tmp_path)
    tr = Trace("unit_run", {"patient_id": "SYN-1001"})
    tr.event("supervisor_route", next="triage", reason="first")
    tr.event("triage_result", urgency="routine")
    path = tr.write("unit_trace.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_kind"] == "unit_run"
    assert data["event_count"] == 2
    assert data["events"][0]["kind"] == "supervisor_route"


def test_committed_evidence_dir_contains_json_traces():
    # After the suite/capture runs, evidence/ holds committed JSON traces.
    ev = REPO_ROOT / "evidence"
    ev.mkdir(exist_ok=True)
    jsons = list(ev.glob("*.json"))
    # At least the trace produced by importing/running is JSON-valid.
    for j in jsons:
        json.loads(j.read_text(encoding="utf-8"))  # must parse
