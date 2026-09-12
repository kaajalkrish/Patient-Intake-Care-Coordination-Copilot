"""Summarization / compression middleware for long threads (NFR-08, "compress" strategy).

When a conversation exceeds a character/turn threshold, older turns are collapsed into a running
summary while the most recent turns are kept verbatim. The summary is returned so callers can also
WRITE it to memory (nothing is lost — see docs/context-engineering.md).

Uses Gemini when available; falls back to a deterministic extractive summary so the module works and
is testable without an API key.
"""
from __future__ import annotations

from typing import Callable

DEFAULT_CHAR_THRESHOLD = 4000
DEFAULT_KEEP_RECENT = 4


def _to_text(msg) -> str:
    if isinstance(msg, dict):
        return f"{msg.get('role', 'user')}: {msg.get('content', '')}"
    role = getattr(msg, "type", getattr(msg, "role", "msg"))
    return f"{role}: {getattr(msg, 'content', str(msg))}"


def total_chars(messages: list) -> int:
    return sum(len(_to_text(m)) for m in messages)


def _extractive_summary(texts: list[str], max_chars: int = 600) -> str:
    """Deterministic fallback summary (no LLM): keep first + salient lines, truncate."""
    joined = " | ".join(t.strip().replace("\n", " ") for t in texts if t.strip())
    if len(joined) <= max_chars:
        return joined
    return joined[: max_chars - 3] + "..."


def summarize_if_needed(
    messages: list,
    *,
    char_threshold: int = DEFAULT_CHAR_THRESHOLD,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    llm_summarizer: Callable[[str], str] | None = None,
) -> tuple[list, str | None]:
    """Compress `messages` if over threshold.

    Returns `(new_messages, summary_or_None)`. When compression happens, `new_messages` is
    `[summary_marker, *recent]` and `summary` is the text of the summary (for WRITE-to-memory).
    When no compression is needed, returns `(messages, None)`.
    """
    if total_chars(messages) <= char_threshold or len(messages) <= keep_recent:
        return messages, None

    older = messages[:-keep_recent] if keep_recent else messages
    recent = messages[-keep_recent:] if keep_recent else []
    older_texts = [_to_text(m) for m in older]

    if llm_summarizer is not None:
        try:
            summary = llm_summarizer("\n".join(older_texts))
        except Exception:
            summary = _extractive_summary(older_texts)
    else:
        summary = _extractive_summary(older_texts)

    summary_marker = {"role": "system", "content": f"[SUMMARY OF EARLIER TURNS] {summary}"}
    return [summary_marker, *recent], summary
