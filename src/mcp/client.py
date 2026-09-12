"""Consume the custom MCP servers via langchain-mcp-adapters (AC-10).

`MultiServerMCPClient` launches both stdio servers and exposes their tools as LangChain tools that the
agent can bind and call. A committed transcript of a real tool call is produced by
scripts/capture_evidence.py -> evidence/mcp_toolcall_transcript.json.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _server_config() -> dict:
    py = sys.executable
    return {
        "clinic": {
            "command": py,
            "args": ["-m", "src.mcp.server"],
            "transport": "stdio",
            "cwd": str(REPO_ROOT),
        },
        "filesystem": {
            "command": py,
            "args": ["-m", "src.mcp.server2_filesystem"],
            "transport": "stdio",
            "cwd": str(REPO_ROOT),
        },
    }


def build_client():
    """Construct a MultiServerMCPClient for the clinic + filesystem servers."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    return MultiServerMCPClient(_server_config())


async def get_mcp_tools() -> list:
    """Async: return the MCP tools from both servers as LangChain tools."""
    client = build_client()
    return await client.get_tools()


def get_mcp_tools_sync() -> list:
    """Sync wrapper around get_mcp_tools() for non-async callers."""
    return asyncio.run(get_mcp_tools())


async def read_manual_resource() -> str:
    """Read the care://coordination-manual MCP resource from the clinic server."""
    client = build_client()
    async with client.session("clinic") as session:
        content = await session.read_resource("care://coordination-manual")
        # content.contents is a list of resource contents; join their text
        parts = []
        for c in getattr(content, "contents", []) or []:
            parts.append(getattr(c, "text", ""))
        return "\n".join(p for p in parts if p)
