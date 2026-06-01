---
name: Content Atomization POC
overview: Stand up a new standalone repo and a new Contentful space for the Meta content-atomization POC, build the four lean content types (with Contentful-native corrections), and wire a staged Extract→Transform→Load pipeline that reuses the existing Google Slides importer's parse layer.
todos:
  - id: scaffold
    content: Create ~/Projects/content-atomization-poc repo (git init, Node/TS, vitest, eslint/prettier, .env.example, README) and lay down model/ skills/ taxonomy/ eval/ pipeline/staging skeleton
    status: pending
  - id: relocate-doc
    content: Relocate Master Build Doc into docs/master-build-doc.md as canonical reference; remove original from meta-demo-hub
    status: pending
  - id: eval-anchor
    content: Seed eval/example-slide-expected.json from Section 14.1
    status: pending
  - id: provision-space
    content: Provision the new Contentful space in org 0EJtkVUGWJCta9Kk8Q3ZCB; capture IDs/tokens in .env; confirm org taxonomy schemes resolve
    status: pending
  - id: content-model
    content: Author model/*.json for sourceDocument/contentAtom/customer/projectContext with the 5 corrections; create+publish via idempotent setup script
    status: pending
  - id: extract
    content: Extract importer's Slides parse into a reusable TS module; emit IR to staging/02_ir incl. speaker notes + flags
    status: pending
  - id: thin-load
    content: "Trivial Load: manifest -> CMA upsert by atomKey, draft-only, so a real deck lands as draft entries early"
    status: pending
  - id: transform
    content: "Python transform.py: IR -> draft atoms+edges+review queue; validate against eval anchor on Example-1 before scaling"
    status: pending
  - id: enrich
    content: atom-tagger (native concepts), relationship-mapper (native refs), image-describer + Section 18 asset two-layer ingestion
    status: pending
  - id: retrieval-decision
    content: Decide vector/hybrid retrieval substrate (Section 22.1) before building deck-composer
    status: pending
  - id: compose
    content: "deck-composer: query -> retrieve -> assemble honoring relationships -> cite; change-propagator one-edit demo"
    status: pending
isProject: false
---

# Content Atomization POC — New Project Setup & Build

A new repo + new Contentful space implementing the Master Build Doc as a demo-ready POC, with five Contentful-native corrections folded in from the start.

## Decisions locked in
- **New standalone repo**: `~/Projects/content-atomization-poc` (sibling to `meta-demo-hub` and `google slides importer`).
- **New Contentful space** in org `0EJtkVUGWJCta9Kk8Q3ZCB` (org-level taxonomy carries over automatically; the 6 `cs-meta-*` schemes will be available with no copy step).
- **Polyglot pipeline by stage**: Extract = TypeScript (reuse importer parse); Transform = Python (doc's stubs); Load = JSON manifest applied via CMA/MCP. Stages hand off via JSON on disk.
- `gj92mjx2vg8d` (DAM) is out of the critical path; the POC governs its own assets via the Section 18 two-layer model.

## Five corrections baked in (vs. the doc as written)
- Core relationships (`proves`/`illustrates`/`contains`) as **native reference fields**; `Object` only for long-tail verbs.
- **Drop the redundant `status` field**; use native publish state. Add only `incomplete`/`template` flag (Section 20.7) for author-unfinished gating.
- `atom-tagger` targets the **live org taxonomy** (`metadata.concepts`), not a JSON dimensions file.
- `productLine`/`audience` as **native taxonomy** (`metadata.concepts`), not `Link→Entry "taxonomyTerm"`.
- **Retrieval substrate is a required decision** (Section 22.1), not a deferred detail — `deck-composer` depends on it.

## Phase 0 — Scaffold & relocate
- Create `~/Projects/content-atomization-poc` with `git init`, Node/TS project (`tsx`, `typescript`, `vitest`, eslint/prettier per repo conventions), `.gitignore`, `.env.example`, `README.md`.
- Relocate the Master Build Doc to `docs/master-build-doc.md` as the canonical reference (copy out of `meta-demo-hub`; remove the original from the demo repo so there's one source of truth).
- Lay down the doc's folder skeleton: `model/`, `skills/`, `taxonomy/`, `eval/`, `pipeline/staging/{01_raw,02_ir,03_atoms,04_manifest}`.
- Seed `eval/example-slide-expected.json` from Section 14.1 as the regression anchor.

## Phase 1 — New space + content model
- Provision the new space (MCP `create_space` or CMA); capture space ID + tokens into `.env`.
- Author `model/*.json` for `sourceDocument`, `contentAtom`, `customer`, `projectContext` with the corrections above.
- A `scripts/setup-content-model.ts` that creates + publishes the types via CMA/MCP (idempotent).
- Confirm org taxonomy schemes resolve in the new space.

## Phase 2 — Extract (the near-term "slides into Contentful" win)
- Extract the importer's Slides-API parse into a reusable module; emit the normalized IR (Section 21.2) to `staging/02_ir/` — including speaker notes and internal/unfinished flags.
- Add a trivial Load (`pipeline/load` → manifest → CMA upsert by `atomKey`, draft-only) so a real deck lands as draft entries before Transform exists.

## Phase 3 — Transform (atoms)
- Python `pipeline/transform.py`: IR → draft atoms + edges + review queue, output matching `eval/example-slide-expected.json`.
- Validate against the eval anchor on the Example-1 slide before scaling beyond one slide.
- Non-negotiables: fused metrics, draft-only, `[NEEDS REVIEW]` over guessing, skip unfinished content.

## Phase 4 — Enrich & govern
- `atom-tagger` (native `metadata.concepts`), `relationship-mapper` (native ref fields), `image-describer` + the Section 18 asset two-layer ingestion (hash-dedup).
- Human-in-the-loop: draft → approve gate; `[NEEDS REVIEW]` queue surfaced.

## Phase 5 — Retrieval & compose (decision-gated)
- Decide the vector/hybrid substrate (Contentful-native vs external vs OpenSearch) — Section 22.1.
- `deck-composer`: query → retrieve (taxonomy + semantic) → assemble honoring relationships → cite atom keys.
- `change-propagator` one-edit lifecycle demo.

## Deferred to production (named, not built)
Recursive `collection` tier, structured notes sub-schema beyond discovery questions, dedup/conflict at scale, `provenanceClass`, diagram payloads, app/partner entities, multi-atom-family (PS offerings), generate-slides rendering round-trip, context-as-content libraries beyond 2–3 seed entries.

## MVP scope guard
One clean external section, ~8–12 slides, draft-only, dry-run manifest before any write. Everything in the deferred list stays deferred.