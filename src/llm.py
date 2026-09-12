"""Gemini LLM wrapper with timeouts, retries, and graceful degradation (NFR-07).

Google Gemini is the only approved provider. This module centralizes model construction so timeouts,
retries, and structured-output binding are consistent, and so the rest of the code never imports the
provider SDK directly. A `LLMUnavailable` error is raised (not a crash) when no key is configured, so
callers can fall back deterministically (supports the self-healing loop, AC-12).
"""
from __future__ import annotations

import time
from typing import Any, TypeVar

from pydantic import BaseModel

from .config import settings

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """Raised when the LLM cannot be used (no key, repeated failures)."""


def _content_to_text(content) -> str:
    """Normalize a LangChain message `content` to a plain string.

    langchain-core 1.x returns content as a list of typed blocks
    (e.g. [{'type': 'text', 'text': '...'}]); older versions returned a str.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", "") or block.get("content", ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def _build_chat(temperature: float = 0.1):
    if not settings.has_api_key:
        raise LLMUnavailable("GOOGLE_API_KEY is not configured; running in offline/fallback mode.")
    # Imported lazily so the package imports without the provider installed/keyed.
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,  # we handle retries ourselves for explicit backoff + tracing
    )


def _with_retries(fn, *, max_retries: int | None = None):
    """Run `fn`, retrying on transient errors with exponential backoff (NFR-07)."""
    attempts = (max_retries if max_retries is not None else settings.llm_max_retries) + 1
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except LLMUnavailable:
            raise
        except Exception as e:  # transient / rate-limit / timeout
            last_err = e
            if i < attempts - 1:
                time.sleep(min(2 ** i, 8))
    raise LLMUnavailable(f"LLM failed after {attempts} attempts: {last_err}") from last_err


def chat_text(prompt: str, *, temperature: float = 0.1, system: str | None = None) -> str:
    """Plain text completion with retries. Raises LLMUnavailable on failure."""
    chat = _build_chat(temperature)
    messages: list[Any] = []
    if system:
        messages.append(("system", system))
    messages.append(("human", prompt))
    resp = _with_retries(lambda: chat.invoke(messages))
    return _content_to_text(resp.content) if hasattr(resp, "content") else str(resp)


def chat_structured(prompt: str, schema: type[T], *, temperature: float = 0.0,
                    system: str | None = None) -> T:
    """Structured completion validated against a Pydantic `schema` (AC-04).

    Uses Gemini's structured-output binding. Raises LLMUnavailable on failure so the caller's
    reflection/fallback path can take over.
    """
    chat = _build_chat(temperature)
    structured = chat.with_structured_output(schema)
    messages: list[Any] = []
    if system:
        messages.append(("system", system))
    messages.append(("human", prompt))
    return _with_retries(lambda: structured.invoke(messages))


def get_chat(temperature: float = 0.1):
    """Return a raw chat model for agents that bind their own tools (e.g. ReAct)."""
    return _build_chat(temperature)
