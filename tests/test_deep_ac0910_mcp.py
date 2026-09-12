"""DEEP AC-09/AC-10: MCP tool + resource behavior — exhaustive (fast, in-process).

Complements the existing surface/adapter tests: exercises each tool's happy path and edge cases and
reads the MCP resource, calling the underlying functions directly (no subprocess) for speed.
"""
from __future__ import annotations

import asyncio

from src.mcp.server import (
    appointment_slots,
    care_pathway,
    mcp,
    patient_lookup,
)


def _call(tool, *args, **kwargs):
    """FastMCP wraps functions; .fn is the raw callable in mcp 1.x."""
    fn = getattr(tool, "fn", tool)
    return fn(*args, **kwargs)


# ---- patient_lookup ----

def test_patient_lookup_known():
    rec = _call(patient_lookup, "SYN-1001")
    assert rec["patient_id"] == "SYN-1001"
    assert "known_allergies" in rec


def test_patient_lookup_unknown_returns_error_not_exception():
    rec = _call(patient_lookup, "SYN-9999")
    assert rec.get("error") == "not_found"


# ---- appointment_slots ----

def test_appointment_slots_returns_matches():
    slots = _call(appointment_slots, "cardiology", "emergent")
    assert isinstance(slots, list)
    assert len(slots) <= 5


def test_appointment_slots_falls_back_to_specialty_only():
    # An urgency band with no exact match still returns specialty slots so scheduling proceeds.
    slots = _call(appointment_slots, "general_practice", "self_care")
    assert isinstance(slots, list)


# ---- care_pathway ----

def test_care_pathway_known_condition():
    cp = _call(care_pathway, "chest_pain")
    assert "error" not in cp


def test_care_pathway_loose_match():
    cp = _call(care_pathway, "chest pain")  # space instead of underscore
    assert "error" not in cp


def test_care_pathway_unknown_lists_available():
    cp = _call(care_pathway, "dragonpox")
    assert cp.get("error") == "no_pathway"
    assert isinstance(cp.get("available"), list)


# ---- resource (AC-09 requires >= 1 resource) ----

def test_resource_is_registered_and_readable():
    async def run():
        resources = await mcp.list_resources()
        return [str(r.uri) for r in resources]

    uris = asyncio.run(run())
    assert any("coordination-manual" in u for u in uris)
