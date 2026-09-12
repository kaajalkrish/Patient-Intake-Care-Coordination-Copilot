"""NFR-01: No secrets committed; env-var config with a committed .env.example."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True)
    return [line for line in out.stdout.splitlines() if line.strip()]


def test_env_example_committed_and_env_ignored():
    tracked = _tracked_files()
    assert ".env.example" in tracked
    assert ".env" not in tracked  # real env must never be tracked
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore


def test_no_real_api_keys_in_tracked_files():
    # Google API keys look like 'AIza' + 35 chars. Ensure none are committed.
    key_pat = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
    for rel in _tracked_files():
        p = REPO_ROOT / rel
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        assert not key_pat.search(text), f"possible committed API key in {rel}"


def test_config_reads_key_from_env_only():
    from src.config import settings

    # The placeholder in .env.example must not count as a real key.
    assert settings.google_api_key != "your-gemini-api-key-here" or not settings.has_api_key
