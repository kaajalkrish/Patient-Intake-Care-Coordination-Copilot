# Memory Design — Tiered Memory, Persistence & Eviction

**Covers:** Memory Systems rubric category (14) · AC-06, AC-07, AC-08.

## 1. Tiers

| Tier | Lifetime | Backing store | Purpose | Code |
|------|----------|---------------|---------|------|
| **Short-term / working** | One turn (lives in graph state) | In-memory `PatientIntakeState.working_memory` + LangGraph checkpointer | Scratchpad for the current intake turn; carried across nodes; checkpointed for pause/resume. | `src/state.py`, `src/graph.py` |
| **Long-term / semantic** | Across turns **and sessions** | SQLite (facts + metadata) **+ Chroma** (embeddings for semantic recall) | Durable patient facts (allergies, preferences, open referrals) recalled by meaning, not exact match. | `src/memory/tiered_memory.py`, `src/memory/store.py` |

Embeddings: **Sentence-Transformers** `all-MiniLM-L6-v2` (local, open-source, no API key) by default;
Gemini embeddings optionally via env. Recall = cosine top-k over the patient's stored facts.

## 2. Cross-session persistence (AC-07)

- Facts are written to an on-disk SQLite DB + Chroma collection keyed by `patient_id`.
- `test_ac07_cross_session_memory.py` proves persistence by:
  1. **Session A**: constructing a fresh memory bound to a temp DB path, storing a fact
     (`"allergic to penicillin"`), then **disposing** the object.
  2. **Session B**: constructing a *brand-new* memory object bound to the *same* DB path (simulating a
     process restart) and recalling the fact by a semantically different query
     (`"any drug allergies?"`).
  3. Asserting the fact is recovered, and **appending the proof to
     [`evidence/memory_persistence_log.txt`](../evidence/memory_persistence_log.txt)** (committed).

## 3. Eviction / importance policy (AC-08)

The store enforces a **hybrid importance-weighted policy** with TTL and a capacity bound:

- **Importance score** ∈ [0,1] assigned per fact at write time (clinical safety facts like allergies =
  high; small talk = low). Score is boosted on each recall (frequently-useful facts survive).
- **TTL** — facts older than `MEMORY_TTL_SECONDS` (default 30 days) are expired, **except** facts with
  importance ≥ `PROTECTED_IMPORTANCE` (safety-critical facts like allergies never silently expire).
- **Capacity bound** — when a patient's fact count exceeds `MEMORY_MAX_ITEMS`, evict the lowest
  `eviction_priority = importance × recency_decay × (1 + log(1+recall_count))`. This blends
  **importance-weighted** + **LRU** behavior in one rule.
- Every eviction is logged to the run trace (NFR-04) with the reason (`ttl_expired` / `capacity_lru`).

`test_ac08_eviction_policy.py` verifies: (a) over-capacity eviction removes the lowest-priority item and
retains a high-importance one; (b) an expired low-importance item is evicted while a protected
high-importance item past TTL is retained.

## 4. Why this design

- Semantic (not keyword) recall matches how clinicians re-reference prior context ("drug allergies?"
  should find "penicillin rash").
- Protecting safety-critical facts from TTL/LRU eviction is a domain-appropriate safety choice.
- SQLite + Chroma satisfy the No-Docker / No-external-DB rule (both are embedded, file-based).
