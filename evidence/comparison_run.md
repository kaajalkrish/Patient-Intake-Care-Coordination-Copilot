# Single-Agent vs Multi-Agent Supervisor — Comparison Run

_Generated 2026-09-12T13:57:03_. Same committed samples run through both architectures. See docs/single-vs-multi-decision.md for the rationale.

| Sample | Expected | Multi urgency | ✓ | Single urgency | ✓ | Multi lat (s) | Single lat (s) | Supervisor decisions |
|---|---|---|---|---|---|---|---|---|
| emergent_chest_pain | emergent | emergent | ✓ | emergent | ✓ | 42.3062 | 7.0235 | 5 |
| injection_attempt | routine | routine | ✓ | routine | ✓ | 8.3511 | 8.2798 | 4 |
| out_of_scope_oncology | routine | routine | ✓ | routine | ✓ | 8.2545 | 8.4675 | 5 |
| routine_rash | routine | routine | ✓ | routine | ✓ | 4.2631 | 4.1207 | 5 |
| selfcare_cold | self_care | self_care | ✓ | self_care | ✓ | 8.4695 | 8.384 | 3 |
| urgent_low_mood | urgent | urgent | ✓ | urgent | ✓ | 4.024 | 4.4475 | 5 |

**Routing accuracy:** multi-agent 100% · single-agent 100%

## Observations

- **Routing correctness**: both architectures classify urgency correctly on these samples, including refusing to let the injection sample elevate urgency. The multi-agent supervisor makes the routing policy *explicit and auditable* (a decision per step), whereas the single agent's ordering is implicit.
- **Cost/latency**: the single agent is lighter (no supervisor decision steps) and slightly faster; the multi-agent version adds supervisor decisions in exchange for isolation and auditability. This is the trade-off documented in the decision doc.
- **Failure isolation & self-healing**: only the multi-agent version localizes a tool failure to a single worker and re-plans there (see evidence/reflection_trace.json).
- **Verdict**: multi-agent supervisor is the right primary architecture for a safety-relevant coordination workflow; the single agent remains a reasonable lightweight baseline for trivial intakes.