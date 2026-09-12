"""Second MCP server: `filesystem` (Good-to-Have — demonstrates multi-server interoperability).

Exposes sandboxed read-only access to the synthetic intake-notes directory. Path traversal outside
the sandbox is refused. Run standalone:  python -m src.mcp.server2_filesystem
"""
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTES_DIR = (REPO_ROOT / "data" / "synthetic" / "intake_notes").resolve()

mcp = FastMCP("filesystem")


def _safe(path: str) -> Path | None:
    candidate = (NOTES_DIR / path).resolve()
    try:
        candidate.relative_to(NOTES_DIR)  # refuse traversal outside sandbox
    except ValueError:
        return None
    return candidate


@mcp.tool()
def list_intake_notes() -> list[str]:
    """List the filenames of available synthetic intake notes."""
    if not NOTES_DIR.exists():
        return []
    return sorted(p.name for p in NOTES_DIR.glob("*.txt"))


@mcp.tool()
def read_intake_note(filename: str) -> str:
    """Read a synthetic intake note by filename (sandboxed to the intake_notes directory)."""
    p = _safe(filename)
    if p is None or not p.exists():
        return f"error: note not found or outside sandbox: {filename}"
    return p.read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run(transport="stdio")
