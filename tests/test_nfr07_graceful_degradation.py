"""NFR-07: Graceful degradation on tool/model failure: timeouts, retries, explicit exit."""
from __future__ import annotations

import src.llm as llm
from src.config import Settings
from src.llm import LLMUnavailable, chat_text


def test_llm_raises_unavailable_without_key(monkeypatch):
    monkeypatch.setattr(llm, "settings", Settings(google_api_key=None))
    try:
        chat_text("hello")
        assert False, "expected LLMUnavailable"
    except LLMUnavailable:
        pass


def test_retry_wrapper_retries_then_raises(monkeypatch):
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise TimeoutError("slow")

    monkeypatch.setattr(llm, "settings", Settings(google_api_key="x", llm_max_retries=2))
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)  # no real backoff sleeps
    try:
        llm._with_retries(boom)
        assert False, "expected failure after retries"
    except LLMUnavailable:
        pass
    assert calls["n"] == 3  # initial + 2 retries (explicit exit condition)


def test_full_run_degrades_gracefully_without_llm():
    # With no API key the whole pipeline still completes via deterministic fallbacks.
    from src.runner import run_intake

    final = run_intake(patient_id="SYN-1004",
                       text="crushing chest pain radiating to my left arm, short of breath",
                       use_checkpointer=False)
    assert final["final_plan"] is not None
    assert final["triage_result"] is not None
