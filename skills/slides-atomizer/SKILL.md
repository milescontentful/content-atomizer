---
name: slides-atomizer
description: Parse a Google Slides deck into a Source Document parent and draft content atoms with atom types, self-contained semantic summaries, and provenance. Use when atomizing a slide deck, breaking slides into reusable components, ingesting marketing decks into the content knowledge graph, or preparing slide content for an AI retrieval/generation engine. Not for Google Docs (use docs-atomizer) and not for tagging or relationship mapping (use atom-tagger / relationship-mapper).
---

# slides-atomizer

Turns one Google Slides deck into a `sourceDocument` parent + a set of draft `contentAtom`
records. Deterministic parsing first, LLM extraction second. Output lands in DRAFT for
human review — never publishes.

## Inputs
- `deckUrl` (required): Google Slides URL or export.
- `granularity` (optional, default `idea`): `idea` | `fine` | `coarse`. See references/granularity-rule.md.
- `sectionScope` (optional): slide index range to limit a POC run.

## Workflow
1. **Parse (deterministic).** Use the Slides API to walk slides in order. For each slide capture:
   slide index, layout/section, all text runs, image refs, and SPEAKER NOTES.
   Notes are first-class context — never skip them.
2. **Create the Source Document parent.** Populate: title, campaign, productLine, audience,
   sourceUrl, sourceDocId (stable), owner, internalExternal (parse from "[TEMPLATE]",
   "Internal Only" cues), slideOrder. See references/field-dictionary.md.
3. **Extract atoms (LLM).** Within each slide, split by structural + semantic boundaries using
   the granularity rule. For each atom produce: atomType (references/atom-taxonomy.md),
   body, semanticSummary (one self-contained sentence), and metric (stat + label FUSED into
   one string), claim/proof where present.
4. **Fuse stats with labels.** A number without its label is never its own atom. "87%" must be
   captured as "87% higher CTR for Ace & Tate".
5. **Attach provenance.** Every atom gets sourceDocument ref, sourceSlideIndex, atomKey (stable),
   extraction timestamp, method/version, confidence.
6. **Flag, don't guess.** When persona, attribution, or a stat's meaning can't be determined
   from slide text + notes, set the field to "[NEEDS REVIEW]" and add to the review queue.
7. **Emit DRAFT.** Write atoms in draft status. Do not tag or map relationships here — hand off.

## Output
- 1 `sourceDocument` (draft)
- N `contentAtom` (draft), each self-contained
- A review-queue list of `[NEEDS REVIEW]` items

## Guardrails
- Deterministic parse must never depend on model variance.
- Do not publish. Do not invent attributions. Do not drop speaker notes.
- Skip architecture-diagram slides in POC mode (flag them for manual structured capture).
