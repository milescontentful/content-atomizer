---
name: atom-tagger
description: Apply the controlled taxonomy (persona, vertical, journey/deal stage, product, region, approval) to draft content atoms and validate term IDs. Use when tagging atoms, classifying content for retrieval, enriching atoms with metadata, or enforcing taxonomy governance. Runs after slides-atomizer / docs-atomizer and before vectorization.
---

# atom-tagger

Adds the retrieval + governance metadata layer to draft atoms.

## Inputs
- `atoms` (required): draft contentAtom records.
- `taxonomyScheme` (required): the controlled taxonomy with stable term IDs.

## Workflow
1. For each atom, infer and assign taxonomy terms: persona, vertical, journeyStage,
   product, region. Use only valid term IDs from the scheme.
2. Validate every term against the scheme. Unknown/ambiguous -> "[NEEDS REVIEW]".
3. Set internalExternal (inherit stricter of section vs atom).
4. Set provenanceClass on proof atoms (customer_outcome vs internal_experiment).
5. Do not over-tag. Each tag must serve retrieval, discovery, or governance. Drop the rest.

## Guardrails
- Never invent taxonomy terms. Never relax internalExternal toward "external".
- Tagging changes require re-validation downstream.

## POC note
Target the LIVE Contentful org taxonomy via `metadata.concepts` (the 6 cs-meta-* schemes),
not the local taxonomy/scheme.json seed. The seed is a fallback only.
