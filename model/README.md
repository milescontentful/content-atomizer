# Content model

Portable JSON definitions of the 4 lean POC content types. These are the **deployed, corrected** shapes as published in space `ce81lr6pgre8` (env `master`) on 2026-06-01.

The five Contentful-native corrections from `docs/plan-content-atomization-poc.md` are **applied** — not pending:

1. **Core relationships as native reference fields.** `contentAtom` has `proves`, `illustrates`, and `contains` as `Array<Link→contentAtom>`. `relatedTo` (Object) is kept for long-tail verbs only.
2. **`status` field dropped.** Contentful's native publish state gates retrieval. `authorState` enum (`complete | incomplete | template`, default `complete`) handles the Section 20.7 "unfinished content" gate.
3. **`productLine` / `audience` removed from `sourceDocument`.** Classification happens via `metadata.concepts` against the live org taxonomy schemes (`cs-meta-products`, `cs-audience-segment`, etc.) — applied at tagging time in Phase 4.
4. **Tagging targets the live org taxonomy**, not `taxonomy/scheme.json`. The JSON file is a fallback reference only.
5. **`unique` enabled** on `atomKey` (contentAtom, customer), `sourceDocId` (sourceDocument), and `contextKey` (projectContext). Verified safe on the fresh space.

## Files

| File | Content type | Display field |
|---|---|---|
| `customer.json` | Customer | `name` |
| `contentAtom.json` | Content Atom | `atomKey` |
| `sourceDocument.json` | Source Document | `title` |
| `projectContext.json` | Project Context | `contextKey` |

## Key design notes

- `contentAtom.proves` / `illustrates` / `contains` are typed `Array<Link→contentAtom>` — the explicit graph edges the deck-composer traverses.
- `contentAtom.authorState` distinguishes `incomplete` (slide had placeholder text — never retrieve) and `template` (reusable structure) from `complete` (default).
- `sourceDocument.slideOrder` is an Object (ordered array of atomKeys) to preserve the original narrative sequence for deck assembly.
- `projectContext` is the context-as-content capstone (Section 23): brand voice, tone, ICP, guardrails stored as versioned, permissioned entries that condition the Transform stage.
