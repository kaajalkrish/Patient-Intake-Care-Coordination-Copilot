# Integration Decision — MCP vs API vs Direct-DB vs A2A

**Covers:** MCP & Interoperability rubric parameter "Integration decision (3)".
**Decision:** Expose the clinic's operational capabilities through a **custom MCP server (stdio)**,
consumed by the agent via **langchain-mcp-adapters**. A second MCP server (filesystem) is added as a
good-to-have to demonstrate multi-server interoperability.

---

## The options considered

| Option | What it is | Pros | Cons | Fit here |
|--------|-----------|------|------|----------|
| **MCP server (chosen)** | Tools/resources exposed over the Model Context Protocol; agent connects via adapters. | Standard, model-portable contract; tools + resources + prompts in one protocol; hot-swappable servers; matches the "interoperability" learning goal; discoverable tool schemas. | Extra process + protocol overhead; stdio plumbing. | **Primary.** Directly satisfies AC-09/AC-10 and the interoperability track. |
| Direct Python API calls | Import clinic functions directly into the agent. | Simplest, lowest latency. | Tight coupling; no standard contract; not interoperable across languages/teams; doesn't demonstrate MCP. | Rejected as primary — used only for pure local heuristics that aren't "clinic systems". |
| Direct DB access | Agent queries a DB directly. | No service layer. | Leaks schema into the agent; no access control/validation boundary; **No-external-DB rule**; unsafe for untrusted input. | Rejected. |
| A2A (agent-to-agent) | Delegate to remote autonomous agents over an agent protocol. | Great for cross-org autonomous collaboration. | Overkill for calling deterministic clinic tools; heavier; our "systems" are tools, not agents. | Rejected as primary (noted as a possible extension). |

## Why MCP wins for this workflow

- The clinic capabilities (patient directory, appointment calendar, care-pathway manual) are exactly
  **tools + a resource** — MCP's native model. `care_coordination_manual` fits MCP **resources**;
  `patient_lookup` / `appointment_slots` / `care_pathway` fit MCP **tools**.
- MCP gives a **typed, discoverable, model-portable** contract, so the grader's Gemini-based agent (or
  any MCP client) can consume the same server unchanged.
- Servers are **hot-swappable and isolated** — we run the clinic server and a filesystem server side by
  side through one adapter client, demonstrating true interoperability.
- The protocol boundary is a natural **trust boundary** for untrusted patient input (defense in depth
  with the quarantine layer).

## What we expose (AC-09)

**Server 1 — `clinic` (`src/mcp/server.py`):**
- Tool `patient_lookup(patient_id)` → synthetic patient record.
- Tool `appointment_slots(specialty, urgency)` → available synthetic slots.
- Tool `care_pathway(condition)` → structured pathway steps.
- Resource `care://coordination-manual` → the care-coordination manual text.

**Server 2 — `filesystem` (`src/mcp/server2_filesystem.py`, good-to-have):**
- Tool `read_intake_note(path)` / `list_intake_notes()` over a sandboxed synthetic notes dir.

## Consumption (AC-10)

`src/mcp/client.py` uses `langchain-mcp-adapters` `MultiServerMCPClient` to load both servers' tools as
LangChain tools and hand them to the agent. A committed transcript
([`evidence/mcp_toolcall_transcript.json`](../evidence/mcp_toolcall_transcript.json)) shows the agent
invoking an MCP tool with arguments and receiving a result.
