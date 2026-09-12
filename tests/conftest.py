"""Shared pytest fixtures.

Tests run WITHOUT a Gemini API key: agents fall back to deterministic behavior (NFR-07), so the whole
suite is offline-reproducible. Tests that specifically exercise the LLM are skipped when no key is set.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_synthetic_data import main as gen_data  # noqa: E402
from src.config import settings  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def ensure_synthetic_data():
    """Guarantee synthetic data exists before any test runs."""
    if not (REPO_ROOT / "data" / "synthetic" / "patients.json").exists():
        gen_data()
    yield


@pytest.fixture
def tmp_memory(tmp_path):
    """A TieredMemory bound to a throwaway on-disk SQLite db."""
    from src.memory.tiered_memory import TieredMemory

    mem = TieredMemory(db_path=tmp_path / "mem.sqlite", ttl_seconds=2_592_000, max_items=200)
    yield mem
    mem.close()


@pytest.fixture
def sample_intakes():
    import json

    d = REPO_ROOT / "data" / "sample_intakes"
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in d.glob("*.json")}


def has_api_key() -> bool:
    return settings.has_api_key


requires_llm = pytest.mark.skipif(not has_api_key(), reason="GOOGLE_API_KEY not set; LLM test skipped")
