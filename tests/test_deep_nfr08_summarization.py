"""DEEP NFR-08: summarization / compression middleware for long threads — exhaustive.

The 'compress' strategy collapses older turns into a running summary while keeping recent turns
verbatim, and returns the summary so callers can WRITE it to memory (nothing lost).
"""
from __future__ import annotations

from src.context.summarization import (
    DEFAULT_KEEP_RECENT,
    summarize_if_needed,
    total_chars,
)


def _msgs(n, size=1):
    return [{"role": "user", "content": "x" * size} for _ in range(n)]


def test_short_thread_is_not_compressed():
    msgs = _msgs(3, size=10)
    out, summary = summarize_if_needed(msgs, char_threshold=10_000)
    assert out is msgs
    assert summary is None


def test_few_messages_never_compressed_even_if_long():
    msgs = _msgs(DEFAULT_KEEP_RECENT, size=5000)  # over char threshold but <= keep_recent
    out, summary = summarize_if_needed(msgs, char_threshold=100, keep_recent=DEFAULT_KEEP_RECENT)
    assert summary is None
    assert out == msgs


def test_long_thread_is_compressed_and_keeps_recent():
    msgs = [{"role": "user", "content": f"turn {i} " + "y" * 200} for i in range(20)]
    out, summary = summarize_if_needed(msgs, char_threshold=500, keep_recent=4)
    assert summary is not None
    # compressed form = [summary_marker, *last 4]
    assert len(out) == 5
    assert "[SUMMARY OF EARLIER TURNS]" in out[0]["content"]
    assert out[-4:] == msgs[-4:]


def test_summary_returned_for_write_to_memory():
    msgs = [{"role": "assistant", "content": f"note {i} " + "z" * 100} for i in range(15)]
    _, summary = summarize_if_needed(msgs, char_threshold=300, keep_recent=3)
    assert isinstance(summary, str) and summary


def test_custom_llm_summarizer_is_used():
    called = {}

    def fake_llm(text: str) -> str:
        called["yes"] = True
        return "LLM_SUMMARY"

    msgs = [{"role": "user", "content": "long " * 100} for _ in range(10)]
    out, summary = summarize_if_needed(msgs, char_threshold=100, keep_recent=2,
                                       llm_summarizer=fake_llm)
    assert called.get("yes") is True
    assert summary == "LLM_SUMMARY"
    assert "LLM_SUMMARY" in out[0]["content"]


def test_llm_failure_falls_back_to_extractive():
    def broken_llm(text: str) -> str:
        raise RuntimeError("model down")

    msgs = [{"role": "user", "content": "content " * 50} for _ in range(10)]
    out, summary = summarize_if_needed(msgs, char_threshold=100, keep_recent=2,
                                       llm_summarizer=broken_llm)
    assert summary  # deterministic fallback still produced a summary
    assert "[SUMMARY OF EARLIER TURNS]" in out[0]["content"]


def test_total_chars_counts_role_and_content():
    assert total_chars([{"role": "user", "content": "abc"}]) >= 3
