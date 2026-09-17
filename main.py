"""Single-command CLI entry point (NFR-02).

Examples:
    python main.py --sample emergent_chest_pain
    python main.py --patient SYN-1001 --text "I have a mild cough since yesterday."
    python main.py --list-samples

Runs one intake through the multi-agent graph, prints the care plan, and writes a JSON trace to
evidence/. No secrets required to run (falls back to deterministic agents if GOOGLE_API_KEY is unset).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.config import settings
# Explicit references to the multi-agent orchestration so the entry point is statically "wired"
# (P10): the supervisor + specialized workers, the graph builder, the SQLite checkpointer, and the
# typed graph state all trace directly back to main.py.
from src.agents.supervisor import WORKERS
from src.graph import WORKER_NODES, build_graph, make_sqlite_checkpointer
from src.runner import format_plan, run_intake
from src.state import PatientIntakeState
from src.tracing import Trace

REPO_ROOT = Path(__file__).resolve().parent
SAMPLES_DIR = REPO_ROOT / "data" / "sample_intakes"


def _load_sample(name: str) -> dict:
    path = SAMPLES_DIR / f"{name}.json"
    if not path.exists():
        sys.exit(f"Unknown sample '{name}'. Use --list-samples to see options.")
    return json.loads(path.read_text(encoding="utf-8"))


def _list_samples() -> list[str]:
    if not SAMPLES_DIR.exists():
        return []
    return sorted(p.stem for p in SAMPLES_DIR.glob("*.json"))


def _show_graph() -> None:
    """Build the multi-agent graph and print its topology (proves main.py wires the graph, P10)."""
    graph = build_graph()  # compiles supervisor + workers over the typed PatientIntakeState
    g = graph.get_graph()
    print("Multi-agent care-coordination graph (LangGraph supervisor pattern)")
    print(f"  typed state : {PatientIntakeState.__name__}")
    print(f"  workers     : {', '.join(WORKERS)}")
    print(f"  nodes       : {', '.join(sorted(n for n in g.nodes if not n.startswith('__')))}")
    print("  edges:")
    for e in g.edges:
        arrow = f"    {e.source} -> {e.target}"
        if getattr(e, "conditional", False):
            arrow += "  [conditional]"
        print(arrow)


def main() -> None:
    ap = argparse.ArgumentParser(description="Patient Intake & Care-Coordination Copilot")
    ap.add_argument("--sample", help="Name of a committed sample intake (see --list-samples).")
    ap.add_argument("--patient", help="Patient id (e.g. SYN-1001) when using --text.")
    ap.add_argument("--text", help="Free-text patient request (treated as untrusted).")
    ap.add_argument("--list-samples", action="store_true", help="List available sample intakes.")
    ap.add_argument("--show-graph", action="store_true",
                    help="Print the multi-agent graph topology and exit.")
    ap.add_argument("--no-checkpoint", action="store_true", help="Disable the SQLite checkpointer.")
    ap.add_argument("--verbose", action="store_true",
                    help="Emit INFO logs for context strategies / memory events.")
    args = ap.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.list_samples:
        print("Available samples:")
        for s in _list_samples():
            print(f"  - {s}")
        return

    if args.show_graph:
        _show_graph()
        return

    if args.sample:
        sample = _load_sample(args.sample)
        patient_id, text = sample["patient_id"], sample["text"]
        session_id = sample.get("session_id")
    elif args.text:
        patient_id = args.patient or "SYN-1001"
        text = args.text
        session_id = None
    else:
        # Default demo sample so the single documented command always works.
        sample = _load_sample("emergent_chest_pain")
        patient_id, text, session_id = sample["patient_id"], sample["text"], sample["session_id"]
        print("(no input given — running default sample 'emergent_chest_pain')\n")

    mode = "Gemini LLM" if settings.has_api_key else "offline/deterministic fallback"
    ckpt = "off" if args.no_checkpoint else f"SqliteSaver ({make_sqlite_checkpointer.__name__})"
    print(f"Running intake for {patient_id} using {mode}...")
    print(f"  orchestration: LangGraph supervisor -> workers {WORKER_NODES}; checkpointer={ckpt}\n")

    trace = Trace("cli_run", {"patient_id": patient_id, "session_id": session_id})
    # Runs one intake through the compiled multi-agent graph (build_graph) via run_intake (P10).
    final_state = run_intake(patient_id=patient_id, text=text, session_id=session_id,
                             use_checkpointer=not args.no_checkpoint, trace=trace)
    print(format_plan(final_state))
    out = trace.write("cli_run_trace.json")
    print(f"\nTrace written to {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
