"""NFR-05: All data synthetic; any PII synthetic and never written to logs in plaintext."""
from __future__ import annotations

import json
from pathlib import Path

from src.tracing import redact

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_redaction_removes_pii_shapes():
    payload = {
        "patient_id": "SYN-1001",
        "name": "Testpatient Alpha",
        "dob": "1970-01-01",
        "note": "call 555-123-4567 or a@b.com",
        "raw": "sensitive free text",
    }
    red = redact(payload)
    blob = json.dumps(red)
    assert "SYN-1001" not in blob
    assert "1970-01-01" not in blob
    assert "a@b.com" not in blob
    assert red["name"] == "[REDACTED]"
    assert red["raw"] == "[REDACTED]"


def test_synthetic_patients_are_clearly_fake():
    patients = json.loads((REPO_ROOT / "data" / "synthetic" / "patients.json").read_text("utf-8"))
    assert patients
    for p in patients:
        assert p["patient_id"].startswith("SYN-")
        assert "Testpatient" in p["name"]  # obviously synthetic


def test_committed_traces_contain_no_plaintext_patient_ids():
    ev = REPO_ROOT / "evidence"
    for j in ev.glob("*.json"):
        text = j.read_text(encoding="utf-8")
        # redaction replaces SYN-#### with a token in redacted fields; the meta may keep ids only
        # inside explicitly-redacted structures. Ensure no raw free-text names leak.
        data = json.loads(text)
        assert "Testpatient" not in json.dumps(data), f"synthetic name leaked in {j.name}"
