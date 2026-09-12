"""NFR-06: Single-vs-multi decision and framework choice documented with rationale."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"


def test_single_vs_multi_decision_doc_exists_with_rationale():
    doc = (DOCS / "single-vs-multi-decision.md").read_text(encoding="utf-8").lower()
    assert "multi-agent" in doc and "single" in doc
    assert "langgraph" in doc  # framework choice justified
    for kw in ["trade-off", "why", "chosen"]:
        assert kw in doc, f"decision doc missing rationale keyword '{kw}'"


def test_integration_decision_doc_covers_alternatives():
    doc = (DOCS / "integration-decision.md").read_text(encoding="utf-8").lower()
    for kw in ["mcp", "api", "direct", "a2a"]:
        assert kw in doc, f"integration decision missing '{kw}'"


def test_core_docs_present():
    for name in ["business-case.md", "acceptance-criteria.md", "context-engineering.md",
                 "memory-design.md", "traceability-matrix.md"]:
        assert (DOCS / name).exists(), f"missing doc {name}"
