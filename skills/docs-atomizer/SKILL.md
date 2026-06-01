---
name: docs-atomizer
description: Phase-2 extension that atomizes Google Docs into the same atom/metadata model used for slides. Use when atomizing a Google Doc, chunking continuous prose into reusable atoms, or ingesting Docs-based marketing material. Reuses atom-tagger, relationship-mapper, image-describer, and deck-composer unchanged — only the parser differs from slides-atomizer.
---

# docs-atomizer (PHASE 2)

Same three-level model as slides; boundaries are semantic, not structural.

## Differences from slides
1. Chunk by SEMANTIC unit (a coherent idea / section / claim+support), which may span
   several paragraphs — not by visual block.
2. Bind inline images to the idea they illustrate (relationship is implicit in flow -> make
   it explicit).
3. For metrics in tables/prose, capture surrounding context (baseline, period, comparison)
   into claim/proof — a bare number is meaningless out of context.
4. Use the heading tree as relationship scaffolding (atoms under a heading relate to its concept).

## Reuse
Output the same contentAtom/sourceDocument records, then hand off to atom-tagger,
relationship-mapper, image-describer, and deck-composer with no changes.
