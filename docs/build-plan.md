# Build Plan — Content Atomization POC

Step-by-step build order for the POC. Grounded in [`master-build-doc.md`](master-build-doc.md) (the methodology) and [`plan-content-atomization-poc.md`](plan-content-atomization-poc.md) (the high-level plan). Phases are sequential; each ends with a **demo checkpoint** and **exit criteria** before moving on.

Principle (Section 12 of the build doc): **prove small, then scale.** Build the content model first, run the full loop on ONE slide, then widen to a section.

---

## Phase 0 — Scaffold (DONE)

- [x] Repo created at `~/Projects/content-atomization-poc`, git initialized
- [x] Config (`package.json`, `tsconfig.json`, eslint/prettier, `.gitignore`, `.env.example`)
- [x] Docs relocated (`docs/master-build-doc.md`, `docs/plan-*.md`)
- [x] Model stubs, 7 skills, taxonomy seed, eval anchor, pipeline stubs + `staging/`
- [ ] Initial git commit (optional — do before Phase 1 if you want a clean baseline)

---

## Phase 1 — New space + content model (the foundation)

Everything reads/writes against these types, so they come first.

### 1a. Provision the space
- [ ] Create the new space in org `0EJtkVUGWJCta9Kk8Q3ZCB` (MCP `create_space` or web UI)
- [ ] Generate a CMA token + CDA token for the space
- [ ] Fill `.env` from `.env.example` (`CTFL_SPACE_ID`, `CTFL_CMA_TOKEN`, `CTFL_CDA_TOKEN`)
- [ ] Confirm the 6 org taxonomy schemes resolve in the new space (`cs-meta-products`, `cs-audience-segment`, `cs-topic-use-case`, `cs-content-format`, `cs-region`, `cs-team`) — they should appear automatically (org-level)

### 1b. Apply the 5 corrections to `model/*.json`
- [ ] **Relationships → native references.** Add `proves`, `illustrates`, `contains` as `Array<Link → contentAtom>` fields on `contentAtom`; keep `relatedTo` (Object) for the long-tail verbs only
- [ ] **Drop redundant `status`.** Remove the `status` enum field; rely on Contentful's native publish state to gate retrieval. Add only an `authorState` enum (`complete | incomplete | template`, default `complete`) for the Section 20.7 "unfinished content" gate
- [ ] **`productLine` / `audience` → native taxonomy.** Remove these two `Link → "taxonomyTerm"` fields from `sourceDocument`; classify via `metadata.concepts` instead (the `"taxonomyTerm"` validation isn't real Contentful)
- [ ] **Tagging targets live org taxonomy**, not `taxonomy/scheme.json` (keep the JSON as a fallback/reference only)
- [ ] **Verify uniqueness** before enabling `unique` on `atomKey` / `sourceDocId` (fresh space = trivially unique)

### 1c. Create + publish the types
- [ ] Write `scripts/setup-content-model.ts` — idempotent create+publish of `sourceDocument`, `contentAtom`, `customer`, `projectContext` via CMA (read the `model/*.json` definitions)
- [ ] Run it; verify all 4 content types exist and are published in the space

**Demo checkpoint:** open the space — 4 content types, taxonomy schemes available.
**Exit criteria:** a human can create a `contentAtom` by hand and link it to a `sourceDocument` and a `customer`.

---

## Phase 2 — Extract + thin Load (the near-term "slides into Contentful" win)

Goal: get a real deck's slides into Contentful as drafts **before** the LLM Transform exists.

### 2a. Extract (TypeScript, reuse the importer)
- [ ] Locate the Slides parse in `~/Projects/google slides importer` (`apps/google-slides-addon/src/mapper.gs` + `services/importer`)
- [ ] Implement `pipeline/extract.ts`: authenticate (service account), fetch the presentation, walk slides in order, capture text runs + image refs + **speaker notes**
- [ ] Port the deterministic detectors from `pipeline/extract.py`: structured-notes parser (Goal/Talk Track/Discovery Questions), `unfinished` + `internal` flags
- [ ] Emit normalized IR to `staging/02_ir/{deck}.json`

### 2b. Trivial Transform + Load
- [ ] Minimal transform: map each slide → 1 coarse `contentAtom` (body = slide text) + 1 `sourceDocument` — just enough to land drafts
- [ ] `pipeline/load.ts`: build the dry-run manifest (`staging/04_manifest/`), then upsert by `atomKey`, **draft-only**, via CMA
- [ ] Run E → trivial T → L on a scoped deck (~8–12 slides); review the manifest; apply; verify drafts in Contentful

**Demo checkpoint:** "here's a Google Slides deck → here are draft entries in Contentful."
**Exit criteria:** re-running is idempotent (no duplicates); nothing is published.

---

## Phase 3 — Transform (real atoms)

The only LLM stage. Output must match `eval/example-slide-expected.json`.

- [ ] Wire the LLM client into `pipeline/transform.py` (or `.ts` — handoff is JSON on disk, so language is free)
- [ ] Implement atom extraction per the `ATOM_PROMPT`: granularity rule, **fused metrics**, self-contained `semanticSummary`
- [ ] Split structured speaker notes into separate atoms — at minimum **discovery questions** (highest reuse)
- [ ] Skip `unfinished` slides; write `[NEEDS REVIEW]` (never guess) and route to the review queue
- [ ] **Validate against the eval anchor on the Example-1 slide** — diff output vs `eval/example-slide-expected.json`; iterate until it matches
- [ ] Only then scale to the full scoped section

**Demo checkpoint:** open `03_atoms/{deck}.json` — "the slide became these atoms, summaries, fused stats, discovery questions, edges."
**Exit criteria:** Example-1 matches the regression anchor; stats are fused; unfinished content is skipped.

---

## Phase 4 — Enrich & govern

- [ ] `atom-tagger`: assign **live org taxonomy** via `metadata.concepts`; invalid/ambiguous → `[NEEDS REVIEW]`
- [ ] `relationship-mapper`: write the native ref fields (`proves`/`illustrates`/`contains`); long-tail verbs → `relatedTo`; layout-only bindings → `[NEEDS REVIEW]`
- [ ] `image-describer` + **asset two-layer ingestion** (Section 18): filter content vs chrome, hash-dedup the binary, link the `image` atom to the Asset, describe for retrievability
- [ ] Human-in-the-loop gate: draft → approve (publish); surface the `[NEEDS REVIEW]` queue (a simple list for now; a Content Preview app later)

**Demo checkpoint:** an atom with taxonomy, real reference edges, a linked image, and an approval action.
**Exit criteria:** only approved atoms are publishable; the review queue is visible and actionable.

---

## Phase 5 — Retrieval & compose (DECISION-GATED)

Do not start until the retrieval substrate is chosen.

- [ ] **DECISION (Section 22.1):** vector/hybrid substrate — Contentful-native vs external (pgvector/Pinecone) vs OpenSearch. Must support **taxonomy filter + semantic similarity together**. Treat the index as a derived artifact rebuilt from governed atoms
- [ ] Build the index from approved atoms (`body` + `semanticSummary`)
- [ ] `deck-composer`: query → taxonomy filter + semantic search → select a spine value_prop → **traverse relationships** for proof/visual/ordered steps → assemble → **cite atomKeys**. Never surface `internal_experiment` proof externally
- [ ] `change-propagator`: edit one stat → re-vectorize + re-tag → regenerate → show propagation with no full re-embed (the lifecycle payoff)
- [ ] `eval/golden-queries.json`: a handful of rep queries → atoms a correct answer must (and must not) retrieve; measure precision

**Demo checkpoint:** rep query → generated slide citing its source atoms; then one edit propagates.
**Exit criteria:** the full thesis runs live: real slide → governed atoms → generated, cited answer.

---

## Open decisions to resolve along the way

1. **Retrieval substrate** (blocks Phase 5) — the single biggest unproven piece
2. **Transform language** — Python (doc stubs) vs TS (matches Extract); JSON-on-disk handoff makes either fine
3. **POC success criteria** (build doc open question #11) — retrieval precision? generation quality? edit-propagation speed? governance? Define before scaling

## Deferred to production (named, not built)

Recursive `collection` tier · full notes sub-schema beyond discovery questions · dedup/conflict at scale · `provenanceClass` · structured diagram payloads · app/partner entities · multi-atom-family (PS offerings/pricing) · generate-slides rendering round-trip · context-as-content libraries beyond 2–3 seed entries.

## MVP scope guard

One clean external section, ~8–12 slides, draft-only, dry-run manifest before any write. Everything in the deferred list stays deferred.
