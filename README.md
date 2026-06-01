# Content Atomization POC

Context-preserving content atomization for Meta: break Google Slides decks into reusable, AI-ready **atoms**, store them as governed Contentful entries, and assemble net-new slides on demand from approved content.

> Full methodology, data contracts, and skill specs: [`docs/master-build-doc.md`](docs/master-build-doc.md).
> Build plan: [`docs/plan-content-atomization-poc.md`](docs/plan-content-atomization-poc.md).

## Status

Scaffolding only. This repo currently contains the structure, config, and copy-ready stubs from the build doc. **No Contentful space is provisioned yet** and the pipeline stubs are not wired. A step-by-step build plan follows.

## Pipeline shape (Extract -> Transform -> Load)

Each stage writes JSON to disk and reads the previous stage's file (`pipeline/staging/`), so every step is inspectable and cheap to re-run.

| Stage | Language | Output |
|---|---|---|
| Extract | TypeScript (reuses the Google Slides importer parse) | `staging/02_ir/` normalized IR (slides + notes + flags) |
| Transform | Python (LLM) | `staging/03_atoms/` draft atoms + edges + review queue |
| Load | manifest (CMA or MCP) | `staging/04_manifest/` dry-run batch, then draft entries |

## Lean POC content model

- `sourceDocument` — the deck parent (Level-1 context + ordering)
- `contentAtom` — one independently reusable idea (Level-2) with relationships (Level-3)
- `customer` — proof attribution
- `projectContext` — context-as-content (tone, brand voice, guardrails) that conditions Transform

## Non-negotiables (even in MVP)

- Stats fused with their label ("87% higher CTR for Ace & Tate", never "87%").
- Everything lands in **draft**; a human approves before content is retrievable.
- Never guess — write `[NEEDS REVIEW]` and queue it.
- Dry-run manifest before any write to Contentful.

## Repo layout

```
content-atomization-poc/
  docs/        master build doc + plan (canonical reference)
  model/       Contentful content-type definitions (POC lean shape)
  skills/      SKILL.md specs (slides-atomizer, atom-tagger, ...)
  taxonomy/    starter controlled-term seed (production maps to live org taxonomy)
  eval/        regression anchor (example-slide-expected.json)
  pipeline/    extract / transform / load + staging/ stage-to-disk artifacts
```
