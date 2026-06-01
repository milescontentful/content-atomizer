---
name: change-propagator
description: Keep atoms current as source documents change and as the content team edits in Contentful or via AI Actions. Handles incremental re-sync (delta upserts by stable ID), update propagation (re-vectorize + re-tag on change), and safe removal (unpublish/archive over hard delete, reference-checked). Use when a source deck is updated, an atom is edited or retired, or content must be refreshed at scale.
---

# change-propagator

Maintains the knowledge graph over time. Two modes: re-sync from source, and propagate edits.

## Re-sync from source
1. Re-parse the source by sourceDocId. Diff against existing atoms by atomKey.
2. UPSERT deltas only (changed/new). Never full-rebuild.
3. NEVER clobber human edits — if an atom was human-modified after extraction, flag the
   incoming change for review instead of overwriting.

## Propagate edits (human edit in UI OR AI Action bulk change)
1. On any atom change: re-vectorize the atom AND re-validate its taxonomy tags.
2. Because atoms are referenced not copied, no re-embedding of whole documents is needed.

## Removal
1. Check reference views: what points at this atom?
2. Prefer unpublish/archive (status flip = removed from engine) over hard delete.
3. Cascade from the Source Document when retiring a whole doc.
4. "Remove from engine" != "delete forever" — keep the audit trail.

## Governance
- Brand-approved atoms are locked from AI modification (tag-based rule).
- Every human or AI change is a reversible revision.
