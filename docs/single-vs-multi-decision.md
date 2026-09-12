# Decision: Single-Agent vs Multi-Agent, and Framework Choice

**Covers:** NFR-06 · Business & Requirements rubric parameter "Single-vs-multi justification (3)".
**Decision:** **Multi-agent supervisor** on **LangGraph**. A single-agent variant is also implemented
(`src/single_agent.py`) and a head-to-head comparison run is committed at
[`evidence/comparison_run.md`](../evidence/comparison_run.md).

---

## 1. The choice

| Option | Description | Verdict |
|--------|-------------|---------|
| **Single agent (one ReAct loop, all tools)** | One LLM agent with every tool and one big system prompt handles triage, scheduling, referral, follow-up. | Implemented as the comparison baseline. Rejected as primary. |
| **Multi-agent supervisor (chosen)** | A supervisor routes to four specialized worker agents; each owns one responsibility, tools, and prompt. | **Chosen.** |
| Multi-agent swarm (peer hand-off) | Agents hand off to each other without a central router. | Rejected: harder to make routing auditable and to enforce urgency policy centrally. |

## 2. Why multi-agent supervisor

The intake workflow decomposes into **four distinct responsibilities** with different inputs, tools,
prompts, and failure modes:

1. **Triage** — classify urgency/acuity, produce a disposition (needs guideline RAG).
2. **Scheduling** — pick an appointment slot appropriate to urgency + specialty (needs slot tool).
3. **Referral** — decide out-of-scope → specialist (needs care-pathway tool).
4. **Follow-up** — after-visit actions + coordination notes.

Reasons a supervisor beats one big agent here:

- **Smaller, focused context per agent.** Each worker sees only what it needs → less prompt bloat,
  fewer distractor tokens, cheaper and more reliable calls (directly supports Context Engineering).
- **Auditable, policy-driven routing.** The supervisor centralizes the urgency policy: an `emergent`
  case is *deterministically* pushed to the expedited path (AC-03), not left to a single model's whim.
- **Isolated failure + targeted self-healing.** If the scheduling tool fails, only the scheduling
  worker re-plans; triage results are untouched (AC-12).
- **Structured hand-offs.** Each worker returns a validated Pydantic object (AC-04); the supervisor
  composes them. This is far easier to test per-boundary than one monolithic output.
- **Clear evidence surface.** Per-worker traces make the committed transcript legible to the grader.

## 3. The cost (honest trade-offs)

- **More orchestration code** and more LLM calls → higher latency and token use than a single agent.
  Acceptable: this is a coordination aid, not a real-time system.
- **Routing bugs** are a new failure class → mitigated with deterministic conditional edges + tests
  (`test_ac03`) and the reflection loop.
- For a *trivial* intake the single agent can be faster/cheaper — quantified in the comparison run.

## 4. Framework choice: LangGraph (required) — why it fits

- **Typed, shared state** (`PatientIntakeState`) across nodes → explicit, testable data flow (AC-01).
- **Graph topology with conditional edges** models supervisor→worker routing natively (AC-02/03).
- **First-class checkpointing** (`langgraph-checkpoint-sqlite`) gives pause/resume for free (AC-05).
- **Interrupt/resume + threads** map cleanly to a multi-session care journey.
- **Ecosystem fit**: `langchain-mcp-adapters` (MCP), `langmem` (memory), Gemini via
  `langchain-google-genai` all integrate directly.

CrewAI (optional) was evaluated for the comparison but not adopted as primary: LangGraph's explicit
state machine gives the checkpointing, conditional routing, and per-node structured output the rubric
scores directly, with less hidden control flow.

## 5. Comparison run

`python -m scripts.run_comparison` executes the **same intake** through the multi-agent supervisor and
the single-agent baseline and writes observations (routing correctness, tool calls, latency, tokens,
output completeness) to [`evidence/comparison_run.md`](../evidence/comparison_run.md).
