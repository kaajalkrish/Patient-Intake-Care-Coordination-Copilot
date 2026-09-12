"""Shared clinical heuristics for the worker agents.

These are deterministic, non-diagnostic keyword/pattern rules used (a) as a safety pre-screen and
(b) as the offline fallback when the LLM is unavailable (NFR-07 graceful degradation). They are
intentionally simple — the rubric does not score the sophistication of domain heuristics.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SYN = REPO_ROOT / "data" / "synthetic"

# condition -> keywords that suggest it
_CONDITION_KEYWORDS = {
    "chest_pain": ["chest pain", "chest tightness", "pressure in my chest", "crushing chest"],
    "rash": ["rash", "itchy", "hives", "skin"],
    "knee_pain": ["knee", "joint pain", "twisted", "sprain"],
    "low_mood": ["low", "depress", "hopeless", "sad", "anxious", "self-harm", "suicid"],
    "cold_symptoms": ["cold", "runny nose", "cough", "sore throat", "congestion", "sneez"],
}

# universal emergency red flags -> force emergent
_EMERGENT_RED_FLAGS = [
    "can't breathe", "cannot breathe", "difficulty breathing", "short of breath",
    "radiat", "left arm", "jaw", "sweaty", "sweating", "fainted", "passed out",
    "slurred speech", "face drooping", "worst headache", "unconscious",
]
# urgent signals
_URGENT_SIGNALS = ["self-harm", "suicid", "hopeless with", "getting worse fast", "severe"]


def detect_condition(text: str) -> str:
    t = (text or "").lower()
    for cond, kws in _CONDITION_KEYWORDS.items():
        if any(k in t for k in kws):
            return cond
    return "general"


def scan_red_flags(text: str) -> list[str]:
    t = (text or "").lower()
    return [f for f in _EMERGENT_RED_FLAGS if f in t]


def heuristic_urgency(text: str, condition: str) -> str:
    """Deterministic urgency: red flags -> emergent; pathway default otherwise."""
    if scan_red_flags(text):
        return "emergent"
    t = (text or "").lower()
    if any(s in t for s in _URGENT_SIGNALS):
        return "urgent"
    pathways = load_pathways()
    if condition in pathways:
        return pathways[condition].get("default_urgency", "routine")
    return "routine"


def load_pathways() -> dict:
    p = SYN / "care_pathways.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_patients() -> list[dict]:
    p = SYN / "patients.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def load_slots() -> list[dict]:
    p = SYN / "appointment_slots.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


IN_SCOPE_SPECIALTIES = {
    "general_practice", "cardiology", "dermatology",
    "orthopedics", "mental_health", "endocrinology",
}
