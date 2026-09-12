# Business Case — Patient Intake & Care-Coordination Copilot

**Business Case ID:** AAIE_AGT_008_HLC
**Domain:** Healthcare — Care Coordination
**Project Type:** Agentic AI Capstone (Agentic AI Core + Context Engineering & Memory + MCP & Interoperability)

> ⚠️ **Not a diagnostic tool.** This copilot is a *coordination aid*. It never provides
> individualized medical advice, never diagnoses, and never issues clinical orders. All data
> is **synthetic** (see [Synthetic-Data Rule](#7-applicable-rules)).

---

## 1. Problem

A clinic wants to streamline **patient intake and care coordination**. Today, when a patient
presents (in person, by phone, or via a portal message), front-desk and nursing staff manually:

1. Read the patient's free-text description of why they are here.
2. Judge urgency (is this an emergency? routine? self-care?).
3. Book an appointment with the right kind of provider.
4. Decide whether a referral to a specialist is needed.
5. Set up follow-up and after-visit instructions.
6. Remember context about the patient across visits ("she mentioned a penicillin allergy last time").

This is slow, error-prone, and loses context between sessions. Staff re-ask the same questions,
urgent cases can wait behind routine ones, and hand-offs drop details.

## 2. Proposed Solution

A **multi-agent copilot** built on **LangGraph** that acts as a coordination layer:

- A **supervisor** agent reads the intake request and routes it to specialized workers.
- Four **worker agents** — **Triage**, **Scheduling**, **Referral**, **Follow-up** — each own one
  step of the journey and return validated, structured results.
- A **custom MCP server** exposes the clinic's operational tools (patient lookup, appointment
  slots, care pathways) so the agent interoperates with clinic systems through a standard protocol.
- **Engineered context** keeps the model focused: untrusted patient free-text is quarantined,
  long threads are summarized, and only relevant memory is selected into the prompt.
- **Tiered memory** carries facts *within* a visit and *across* sessions, so the copilot recalls
  prior-visit details (allergies, preferences, open referrals).
- An **agentic-RAG** tool lets the agent look up care-pathway and triage guidelines on demand.
- A **reflection / self-healing loop** re-plans when a tool fails or a result is low-confidence.

The system is a **coordination aid**: it proposes appointments, referrals, and follow-ups as
structured recommendations for a human to confirm. It executes no real actions (stubs only).

## 3. Actors

| Actor | Role in the workflow |
|---|---|
| **Patient** | Provides the intake request as free text. This text is **untrusted** and quarantined. |
| **Intake Copilot (system)** | Orchestrates triage → scheduling → referral → follow-up and maintains memory. |
| **Supervisor agent** | Routes the request and decides which workers run, in what order. |
| **Triage worker** | Classifies urgency/acuity and recommends a disposition. |
| **Scheduling worker** | Proposes an appointment slot appropriate to urgency and specialty. |
| **Referral worker** | Decides whether an out-of-scope need requires a specialist referral. |
| **Follow-up worker** | Produces follow-up actions and after-visit coordination notes. |
| **Front-desk / nurse (human)** | Reviews and confirms the copilot's recommendations. Not automated. |
| **Clinic systems (via MCP)** | Patient directory, appointment calendar, care-pathway manual — exposed as MCP tools/resource. |

## 4. Success Metrics

These are the measurable outcomes the workflow targets. In this capstone they are demonstrated on
**synthetic** data and verified by committed tests/evidence (see the AC each maps to).

| # | Metric | Target | Evidence |
|---|---|---|---|
| M1 | **Correct routing** — request reaches the right worker(s) | 100% of sample intakes routed per policy | `tests/test_ac02_supervisor_routing.py`, `tests/test_ac03_conditional_routing.py` |
| M2 | **Urgency safety** — emergent cases expedited, never queued behind routine | All `emergent` samples take the expedited path | `tests/test_ac03_conditional_routing.py` |
| M3 | **Context continuity** — facts from earlier turns/sessions are recalled | Prior-session fact recalled in a new session | `tests/test_ac07_cross_session_memory.py` + `evidence/memory_persistence_log.txt` |
| M4 | **Structured, valid hand-offs** — every worker output validates against its schema | 0 schema violations | `tests/test_ac04_structured_output.py` |
| M5 | **Resilience** — system degrades gracefully on tool/model failure | Re-plan/fallback fires, run still completes | `tests/test_ac12_reflection_selfhealing.py` + `evidence/reflection_trace.json` |
| M6 | **Interoperability** — agent invokes clinic tools via MCP | ≥1 MCP tool call in a committed transcript | `tests/test_ac10_mcp_adapter.py` + `evidence/mcp_toolcall_transcript.json` |
| M7 | **Reproducibility** — one command runs the whole workflow | Single documented command from README | `tests/test_nfr02_single_command_run.py` |

## 5. Scope

**In scope:** LangGraph multi-agent graph (typed state, supervisor + workers, conditional routing,
checkpointing, structured output); custom MCP server (≥2 tools + 1 resource) + adapter integration;
context engineering (write/select/compress/isolate) + summarization + quarantine; tiered memory with
cross-session persistence + eviction policy; agentic-RAG tool + reflection loop; a minimal CLI/UI.

**Out of scope:** real EHR connectivity, diagnosis, clinical order entry, real/confidential data,
production deployment, auth, and real action execution (heuristics + stubs are sufficient).

## 6. Single-vs-Multi-Agent Decision (summary)

We chose a **multi-agent supervisor** architecture over a single agent. Full rationale, trade-offs,
and a committed comparison run are in [single-vs-multi-decision.md](single-vs-multi-decision.md).
Short version: the workflow has **four distinct responsibilities** with different tools, prompts, and
failure modes; a supervisor keeps each worker's context small and auditable, enables urgency-aware
routing, and isolates failures — at the cost of extra orchestration and latency, which is acceptable
for a coordination (non-real-time) aid.

## 7. Applicable Rules

- **Synthetic-Data Rule** — only self-generated synthetic data; no real patient data / PHI; no
  Virtusa confidential data. See [`scripts/generate_synthetic_data.py`](../scripts/generate_synthetic_data.py).
- **Evidence-in-Repo Rule** — only committed artifacts are scored (see [`evidence/`](../evidence/)).
- **Reproducibility Rule** — single documented command + committed sample inputs + README quick-start.
- **AC-Traceability Rule** — every AC-NN is referenced by a test/evidence artifact. See
  [traceability-matrix.md](traceability-matrix.md).
- **Context-Isolation Rule** — patient free-text is untrusted and quarantined; never treated as
  instructions. See [context-engineering.md](context-engineering.md).
- **Open-Source & No-Docker Rule** — approved open-source stack + Google Gemini; runs with pip +
  Python alone; no Docker, no external DB service.
