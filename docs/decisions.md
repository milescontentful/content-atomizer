# Open Decision Gates — Phase F

Three decisions must be made **before** building `deck-composer` and finalizing
the editor experience. Each has a recommended path for the POC, but requires
stakeholder confirmation.

---

## Decision 1 — Retrieval Substrate

**Required before:** `deck-composer`, `change-propagator`

### The question
How will the system retrieve atoms when composing a new deck?
Atoms live in Contentful as draft entries. Retrieval needs to answer:
"Find proof atoms about personalization that prove a given value prop."

### Options

| Option | What it is | POC fit | Production fit |
|--------|-----------|---------|---------------|
| **A. Contentful-native CDA queries** | Use `content_type`, `fields.atomType`, `fields.relatedTo.concepts` filters via the CDA | ✅ Zero new infra, ready now | ⚠️ No semantic/vector search; keyword filters only |
| **B. Contentful + external vector DB** | Embed `semanticSummary` text into a vector store (Pinecone, Weaviate, pgvector); Contentful is still the system of record | ⚠️ Needs LLM embed API key + infra | ✅ Best recall quality |
| **C. Contentful + OpenSearch/Elastic** | Full-text search index over atom bodies | ⚠️ More infra than A, less semantic than B | ✅ Good for keyword+facet hybrid |

### Recommendation for POC
**Option A (CDA-native)** — zero additional infra. Compose by filtering:
`atomType=proof AND relatedTo.concepts contains "product:contentful-personalization"`.
Gate the deck-composer behind this decision; do not build retrieval code until confirmed.

### Action required
- [ ] Confirm retrieval approach with stakeholder
- [ ] If A: proceed with `deck-composer` using CDA SDK queries
- [ ] If B: provision embed API key (e.g. OpenAI), choose vector store, set up sync job

---

## Decision 2 — Editor / Review Surface

**Status: Locked to native-first** (per Phase F plan decision). No code action
required — this is a documentation commitment.

### What this means for the POC
1. **Saved Views in Contentful** — filter content by `atomType` and `authorState`.
   - Create a "Needs Review" view: `authorState = incomplete OR body contains [NEEDS REVIEW]`
   - Create an "All Proofs" view: `atomType = proof`
   - Create "By Product" views: filter by `relatedTo.concepts`

2. **References panel** — in any atom entry, the References tab shows every other
   atom that links to it (`proves`, `illustrates`, `contains`). One-edit propagation
   is free: edit the canonical atom, all references reflect it on next retrieval.

3. **Tasks / Workflows** (Contentful Enterprise) — assign `[NEEDS REVIEW]` atoms
   to a reviewer as a task. The 2 flagged atoms from the current load are on slide 4
   (87% and 78% stats — awaiting GAS v2 re-export for correct label association).

### What defers a custom App Framework view
A custom view becomes necessary when:
- The native filter UI can't surface the relationships graph visually
- Volume > ~500 atoms and native performance degrades
- Content editors need bulk-edit or diff workflows not possible natively

For the POC these thresholds are not met.

### Action required
- [x] Decision locked: native-first ✓
- [ ] Set up three saved views in Contentful UI (manual, no code required)
- [ ] Assign the 2 `[NEEDS REVIEW]` atoms from slide 4 to a reviewer via Tasks

---

## Decision 3 — POC Success Criteria + Open Questions

**Required before:** declaring POC complete or building Phase F components.

### Open questions from master-build-doc Section 10

#### #6 — Internal-results leakage governance
Who sets the `internalExternal` gate at atom level?
- Currently `sourceDocument.internalExternal` gates the whole deck.
- Individual atoms may need per-atom gating (e.g. a KraftHeinz result in an internal-only deck).
- **Decision needed:** section-level gating vs atom-level field (`authorState = incomplete` = not surfaced).
- **Recommended:** use `authorState = incomplete` as the atom-level "do not surface" flag
  for now; full governance model is production scope.

#### #10 — Build/buy engine boundary (Section 23.4)
Who owns what?
- **Contentful owns:** governed layer (atoms), context entries (`projectContext`), CDA retrieval, the reference graph.
- **Meta owns:** generation engine, prompt engineering, output rendering, final delivery.
- The master build doc resolves this in Section 23.4. Confirm with stakeholder that this boundary is correct.
- **Action:** walkthrough Section 23.4 with the Meta AI Knowledge Base stakeholder.

#### #11 — POC success criteria
Define BEFORE building deck-composer and change-propagator. Suggested criteria:

| Criterion | Measurement |
|-----------|-------------|
| Retrieval precision | For a given query ("proof atoms for personalization"), what % of returned atoms are actually relevant? Target ≥ 80% |
| Attribution accuracy | 0 stat-label crossovers after GAS v2 re-export + eval gate passes green |
| Edit propagation | Change one canonical atom; verify all downstream references pick it up on next retrieval. 100% required. |
| Governance | No `internal_experiment` atoms surfaced via deck-composer in external output. 0 leaks allowed. |
| Authoring velocity | Time to add a new proof atom and link it to a value prop: target < 5 minutes via native Contentful UI. |

### Action required
- [ ] Confirm engine boundary (#10) with stakeholder
- [ ] Confirm internal-results governance approach (#6)
- [ ] Review and sign off on POC success criteria (#11)
- [ ] Document confirmed criteria in `docs/poc-success-criteria.md`

---

## Summary — What's Blocking Phase F

| Gate | Blocked by | Who unblocks |
|------|-----------|-------------|
| `deck-composer` code | Retrieval substrate decision | You + stakeholder |
| `change-propagator` code | Retrieval substrate decision | You + stakeholder |
| Editor saved views | Manual Contentful UI setup | Content editor |
| POC sign-off | Success criteria definition | Stakeholder |

**Nothing is blocked by code.** All three gates are stakeholder decisions.
Once Decision 1 is confirmed, the next engineering step is a 1-day build:
`deck-composer` using CDA queries (Option A) or vector embed (Option B).
