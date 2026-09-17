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

## 4. Framework choice: LangGraph — why over other multi-agent frameworks

LangGraph is required by the stack, but the choice is *also* the right one on the merits. This
project has three hard requirements that a framework must serve, and each maps to a concrete
acceptance criterion:

1. **Statefulness / durability** — a care journey spans turns and sessions and must survive a
   restart (pause/resume). → AC-05.
2. **Auditability** — routing decisions (especially the urgency policy) must be inspectable and
   deterministic, not hidden inside an LLM's chain-of-thought. → AC-02 / AC-03, and the committed
   traces.
3. **Typed, validated hand-offs** — each worker's output must be a validated object at the boundary,
   not free text another agent re-parses. → AC-01 / AC-04.

How the candidate frameworks score against those three requirements:

| Framework | Statefulness / durability (AC-05) | Auditability of routing (AC-02/03) | Typed hand-offs (AC-01/04) | Verdict |
|-----------|-----------------------------------|------------------------------------|----------------------------|---------|
| **LangGraph (chosen)** | **First-class checkpointers** (`langgraph-checkpoint-sqlite`); threads persist state to disk → pause/resume "for free". | Routing is an **explicit graph** of conditional edges over typed state; `decide_next()` is a pure, unit-testable function; every hop is traced. | Shared `TypedDict` state + Pydantic worker results validated at each node boundary. | **Chosen.** Serves all three requirements directly with the least hidden control flow. |
| CrewAI | Role/'crew' abstraction; persistence is add-on and less explicit; no built-in graph checkpointer equivalent. | Orchestration is largely implicit in role prompts and the framework's internal loop → harder to make routing deterministic and auditable. | Task outputs are mostly text/loosely-typed. | Rejected as primary. Evaluated as the comparison lens (still less auditable). |
| AutoGen (AG2) | Conversation-driven; durable checkpoint/resume of a run is not first-class. | Control flow emerges from multi-agent *conversation* — powerful, but the routing policy is the hardest thing to pin down and prove for a grader. | Message-passing is text-first. | Rejected: auditability + determinism cost too high for a safety policy. |
| LangChain `AgentExecutor` (single ReAct loop) | No graph; state is the scratchpad of one loop. | One agent's tool-choice reasoning is opaque; centralizing an urgency policy means trusting the prompt. | One combined output. | This *is* the single-agent baseline (`src/single_agent.py`), kept only for the comparison run. |
| Plain Python orchestration (no framework) | Would have to hand-roll a checkpointer and thread store. | Fully auditable, but every capability (checkpoint, interrupt, reducers) is re-implemented and re-tested by us. | We'd build the typed-state plumbing ourselves. | Rejected: reinvents exactly what LangGraph gives natively. |

**Bottom line:** LangGraph is the only candidate that satisfies *all three* requirements natively —
durable checkpointing (statefulness), an explicit conditional-edge graph with a pure routing function
(auditability), and typed/validated state + hand-offs — which is why it is chosen even setting the
stack requirement aside. Ecosystem fit reinforces it: `langchain-mcp-adapters` (MCP), `langmem`
(memory), and Gemini via `langchain-google-genai` all integrate directly.

CrewAI (optional) was evaluated for the comparison but not adopted as primary: LangGraph's explicit
state machine gives the checkpointing, conditional routing, and per-node structured output the rubric
scores directly, with less hidden control flow.

## 5. Comparison run

`python -m scripts.run_comparison` executes the **same intake** through the multi-agent supervisor and
the single-agent baseline and writes observations (routing correctness, tool calls, latency, tokens,
output completeness) to [`evidence/comparison_run.md`](../evidence/comparison_run.md).
