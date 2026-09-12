"""Custom MCP server: `clinic` (AC-09).

Exposes >= 2 tools and 1 resource relevant to care coordination, over stdio, using the MCP Python SDK
(FastMCP). Consumed by the agent via langchain-mcp-adapters (see client.py, AC-10).

Tools:
  - patient_lookup(patient_id)          -> synthetic patient record
  - appointment_slots(specialty, urgency) -> available synthetic slots
  - care_pathway(condition)             -> structured care-pathway steps
Resource:
  - care://coordination-manual          -> the care-coordination manual (synthetic)

Run standalone:  python -m src.mcp.server
All data is synthetic (Synthetic-Data Rule).
"""
from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[2]
SYN = REPO_ROOT / "data" / "synthetic"

mcp = FastMCP("clinic")


def _load(name: str, default):
    p = SYN / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


@mcp.tool()
def patient_lookup(patient_id: str) -> dict:
    """Look up a synthetic patient record by patient_id (e.g. 'SYN-1001').

    Returns the record (name, dob, allergies, conditions, medications, primary provider) or an
    error dict if not found. Synthetic data only — no real PHI.
    """
    patients = _load("patients.json", [])
    for p in patients:
        if p.get("patient_id") == patient_id:
            return p
    return {"error": "not_found", "patient_id": patient_id}


@mcp.tool()
def appointment_slots(specialty: str = "general_practice", urgency: str = "routine") -> list[dict]:
    """List available synthetic appointment slots for a specialty and urgency band.

    urgency is one of: emergent, urgent, routine, self_care. Returns up to 5 matching slots.
    """
    slots = _load("appointment_slots.json", [])
    matches = [
        s for s in slots
        if s.get("specialty") == specialty and s.get("urgency_band") == urgency
    ]
    if not matches:  # fall back to specialty-only so scheduling can still proceed
        matches = [s for s in slots if s.get("specialty") == specialty]
    return matches[:5]


@mcp.tool()
def care_pathway(condition: str) -> dict:
    """Return the structured care pathway for a condition (e.g. 'chest_pain', 'rash', 'low_mood').

    Includes default urgency, specialty, steps, and red flags. Coordination guidance, not diagnosis.
    """
    pathways = _load("care_pathways.json", {})
    key = condition.strip().lower().replace(" ", "_")
    if key in pathways:
        return pathways[key]
    # loose contains-match
    for k, v in pathways.items():
        if k in key or key in k:
            return v
    return {"error": "no_pathway", "condition": condition,
            "available": list(pathways.keys())}


@mcp.resource("care://coordination-manual")
def coordination_manual() -> str:
    """The clinic's care-coordination manual (synthetic MCP resource)."""
    p = SYN / "care_coordination_manual.md"
    return p.read_text(encoding="utf-8") if p.exists() else "Manual not found."


if __name__ == "__main__":
    mcp.run(transport="stdio")
