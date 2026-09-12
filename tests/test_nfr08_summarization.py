"""NFR-08: Context-window management — summarization/compression applied for long threads."""
from __future__ import annotations

from src.context.summarization import summarize_if_needed, total_chars


def _long_thread(n=40):
    return [{"role": "user" if i % 2 == 0 else "assistant",
             "content": f"Turn {i}: the patient discussed symptom detail number {i} at length."}
            for i in range(n)]


def test_short_thread_is_not_compressed():
    msgs = [{"role": "user", "content": "hi"}]
    out, summary = summarize_if_needed(msgs, char_threshold=4000)
    assert out is msgs and summary is None


def test_long_thread_is_compressed_and_shrinks():
    msgs = _long_thread()
    assert total_chars(msgs) > 1000
    out, summary = summarize_if_needed(msgs, char_threshold=500, keep_recent=4)
    assert summary is not None
    assert len(out) < len(msgs)              # compressed
    assert out[0]["content"].startswith("[SUMMARY")
    assert len(out) == 5                      # summary marker + 4 recent turns kept verbatim


def test_llm_summarizer_is_used_when_provided():
    msgs = _long_thread()
    out, summary = summarize_if_needed(
        msgs, char_threshold=500, keep_recent=2,
        llm_summarizer=lambda text: "LLM_SUMMARY_OK")
    assert summary == "LLM_SUMMARY_OK"


def test_summarizer_falls_back_when_llm_raises():
    msgs = _long_thread()

    def broken(_):
        raise RuntimeError("llm down")

    out, summary = summarize_if_needed(msgs, char_threshold=500, llm_summarizer=broken)
    assert summary and summary != ""  # extractive fallback still produced a summary
