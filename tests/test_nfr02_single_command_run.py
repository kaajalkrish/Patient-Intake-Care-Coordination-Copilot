"""NFR-02: End-to-end run from a single documented command with committed sample inputs."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_sample_intakes_are_committed():
    samples = list((REPO_ROOT / "data" / "sample_intakes").glob("*.json"))
    assert len(samples) >= 3


def test_single_command_runs_end_to_end():
    # The documented command: python main.py --sample <name>
    proc = subprocess.run(
        [sys.executable, "main.py", "--sample", "routine_rash"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "CARE COORDINATION PLAN" in proc.stdout
    assert "Trace written to" in proc.stdout


def test_readme_documents_the_command():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "python main.py" in readme
