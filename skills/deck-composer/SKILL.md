---
name: deck-composer
description: Given a sales rep query, retrieve approved content atoms (taxonomy filter + semantic search), assemble a coherent slide or deck honoring relationships and ordering, and cite the source atoms used. Use when generating slides from the knowledge graph, answering a rep chatbot query with assembled content, or producing a net-new deck from approved atoms. This is the generation/delivery step.
---

# deck-composer

Retrieves and assembles approved atoms into a coherent slide with citations.

## Inputs
- `query` (required): the rep's natural-language ask.
- `filters` (optional): persona, vertical, journeyStage, product, region.

## Workflow
1. Resolve filters from the query (taxonomy) + run semantic search over embeddings.
2. RETRIEVE ONLY: status=published AND approved AND permissioned. Respect internalExternal —
   never surface internal_experiment proof in an external deck.
3. Select a spine (value_prop), then TRAVERSE relationships to pull supporting proof/stats
   (proves), the right visual (illustrates), and ordered steps (next) for process slides.
4. Prefer the freshest atom (lastReviewed) when duplicates exist; if conflictsWith is set,
   surface the flagged conflict rather than silently picking one.
5. Assemble honoring atom roles (value_prop=headline, proof=supporting, image=visual) and
   original ordering where relevant.
6. Cite every atom used (atomKey + source document) so output is auditable.

## Guardrails
- Never fabricate content not present in retrieved atoms.
- Never present Contentful internal numbers as customer outcomes.
- If retrieval is thin, say so — do not pad with invented proof.
