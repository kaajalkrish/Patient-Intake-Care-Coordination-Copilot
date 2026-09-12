"""AC-10: Agent consumes the MCP server via langchain-mcp-adapters; tool invocation is logged.

Writes evidence/mcp_toolcall_transcript.json (committed) showing a real MCP tool call + result.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path

from src.mcp.client import get_mcp_tools
from src.tracing import redact

REPO_ROOT = Path(__file__).resolve().parents[1]


def _redact_mcp_result(result):
    """Redact synthetic PII from an MCP tool result before committing it as evidence (NFR-05)."""
    def parse_piece(piece):
        if isinstance(piece, dict) and "text" in piece:
            try:
                return redact(json.loads(piece["text"]))
            except Exception:
                return redact(piece["text"])
        return redact(piece)

    if isinstance(result, list):
        return [parse_piece(p) for p in result]
    if isinstance(result, str):
        try:
            return redact(json.loads(result))
        except Exception:
            return redact(result)
    return redact(result)


def test_adapter_loads_tools_and_invokes_mcp_tool(tmp_path):
    # Committed transcript is produced by scripts/capture_evidence.py; the test writes to a
    # throwaway path so it never clobbers canonical evidence.
    transcript = tmp_path / "mcp_toolcall_transcript.json"

    async def run():
        tools = await get_mcp_tools()
        by_name = {t.name: t for t in tools}
        assert "patient_lookup" in by_name  # loaded via langchain-mcp-adapters
        # Invoke a real MCP tool through the adapter.
        call_args = {"patient_id": "SYN-1001"}
        result = await by_name["patient_lookup"].ainvoke(call_args)
        slots = await by_name["appointment_slots"].ainvoke(
            {"specialty": "cardiology", "urgency": "emergent"})
        return [t.name for t in tools], call_args, result, slots

    names, call_args, result, slots = asyncio.run(run())

    result_text = result if isinstance(result, str) else json.dumps(result, default=str)
    assert "SYN-1001" in result_text  # the raw MCP call really returned this patient's record

    transcript.write_text(json.dumps({
        "description": "AC-10 evidence: agent invoking MCP tools via langchain-mcp-adapters. "
                       "Tool results are PII-redacted for the committed log (NFR-05).",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "loaded_tools": names,
        "invocations": [
            {"tool": "patient_lookup", "server": "clinic",
             "arguments": redact(call_args), "result_redacted": _redact_mcp_result(result)},
            {"tool": "appointment_slots", "server": "clinic",
             "arguments": {"specialty": "cardiology", "urgency": "emergent"},
             "result_redacted": _redact_mcp_result(slots)},
        ],
    }, indent=2, default=str), encoding="utf-8")
    assert transcript.exists()


def test_both_servers_are_integrated():
    async def run():
        return [t.name for t in await get_mcp_tools()]

    names = asyncio.run(run())
    # clinic server tools + filesystem server tools both present via one adapter client.
    assert "care_pathway" in names           # clinic server
    assert "list_intake_notes" in names      # filesystem server
