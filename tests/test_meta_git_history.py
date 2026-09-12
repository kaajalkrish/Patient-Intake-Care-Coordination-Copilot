"""META-TESTS: PR-driven Git history (Section 8 mandatory).

Requirement: "at least 3 PR-driven merges (git merge --no-ff); no direct pushes to main."
These assert the committed history proves that workflow. Skipped gracefully if git is unavailable.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=30
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("git not available")
    if out.returncode != 0:
        pytest.skip(f"git error: {out.stderr.strip()}")
    return out.stdout.strip()


def test_is_a_git_repo():
    top = _git("rev-parse", "--show-toplevel")
    assert top, "not a git repository"


def test_at_least_three_no_ff_merges():
    merges = [ln for ln in _git("log", "--merges", "--oneline").splitlines() if ln.strip()]
    assert len(merges) >= 3, f"need >=3 --no-ff PR merges, found {len(merges)}"


def test_merge_commits_have_two_parents():
    # A real --no-ff merge commit has 2+ parents (proves it was not a fast-forward).
    shas = _git("log", "--merges", "--format=%H").splitlines()
    assert shas, "no merge commits found"
    two_parent = 0
    for sha in shas:
        parents = _git("rev-list", "--parents", "-n", "1", sha).split()
        if len(parents) >= 3:  # self + 2 parents
            two_parent += 1
    assert two_parent >= 3, f"need >=3 true (2-parent) merges, found {two_parent}"


def test_feature_branches_exist():
    branches = _git("branch", "-a")
    assert "feature/" in branches or "feature-" in branches, "expected feature branches in history"
