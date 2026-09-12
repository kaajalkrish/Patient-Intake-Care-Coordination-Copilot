"""AC-09: Custom MCP server exposes >= 2 tools and 1 resource relevant to the domain."""
from __future__ import annotations

import asyncio

from src.mcp.server import mcp


def _introspect():
    async def run():
        tools = await mcp.list_tools()
        resources = await mcp.list_resources()
        return [t.name for t in tools], [str(r.uri) for r in resources]

    return asyncio.run(run())


def test_server_exposes_at_least_two_tools_and_one_resource():
    tool_names, resource_uris = _introspect()
    assert len(tool_names) >= 2, f"expected >=2 tools, got {tool_names}"
    assert len(resource_uris) >= 1, f"expected >=1 resource, got {resource_uris}"


def test_expected_domain_tools_and_resource_present():
    tool_names, resource_uris = _introspect()
    assert {"patient_lookup", "appointment_slots", "care_pathway"}.issubset(set(tool_names))
    assert any("coordination-manual" in u for u in resource_uris)


def test_patient_lookup_returns_synthetic_record():
    from src.mcp.server import patient_lookup

    rec = patient_lookup.fn("SYN-1001") if hasattr(patient_lookup, "fn") else patient_lookup("SYN-1001")
    assert rec["patient_id"] == "SYN-1001"
    assert "penicillin" in rec["known_allergies"]
