"""Central configuration — all runtime knobs come from env vars (NFR-01).

Nothing secret is hard-coded. `GOOGLE_API_KEY` is read from the environment / .env only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present (never committed). Safe no-op if the file is absent.
REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(int(default))).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    # LLM
    google_api_key: str | None = os.getenv("GOOGLE_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    gemini_embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "models/text-embedding-004")
    llm_timeout_seconds: int = _int("LLM_TIMEOUT_SECONDS", 30)
    llm_max_retries: int = _int("LLM_MAX_RETRIES", 2)

    # Embeddings
    use_local_embeddings: bool = _bool("USE_LOCAL_EMBEDDINGS", True)
    local_embedding_model: str = os.getenv(
        "LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # Memory
    memory_ttl_seconds: int = _int("MEMORY_TTL_SECONDS", 2_592_000)  # 30 days
    memory_max_items: int = _int("MEMORY_MAX_ITEMS", 200)

    # Paths (relative to repo root unless absolute)
    checkpoint_db: str = os.getenv("CHECKPOINT_DB", "checkpoints/graph_state.sqlite")
    memory_db: str = os.getenv("MEMORY_DB", "checkpoints/memory.sqlite")
    vectorstore_dir: str = os.getenv("VECTORSTORE_DIR", "data/vectorstore")

    def path(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else (REPO_ROOT / p)

    @property
    def has_api_key(self) -> bool:
        return bool(self.google_api_key and self.google_api_key != "your-gemini-api-key-here")


settings = Settings()
