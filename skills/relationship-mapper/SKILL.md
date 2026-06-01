---
name: relationship-mapper
description: Infer and record explicit relationships between content atoms (proves, illustrates, contains, next, attributed_to, powers, references, targets, variant_of, positioned_at). Use when mapping how atoms connect, preserving relationship/Level-3 context, building the knowledge-graph edges, or wiring proof points to value props. Runs after slides-atomizer on atoms from the same source.
---

# relationship-mapper

Captures Level-3 context as explicit reference edges, not prose.

## Relationship vocabulary
contains | proves | illustrates | attributed_to | belongs_to | next (ordered, may be cyclic)
| powers | references | has_metric | positioned_at | integrates_with | variant_of
| targets | phase_sequence | depends_on

## Workflow
1. For atoms from one source document, infer edges:
   - proof/stat --proves--> the value_prop it backs
   - image --illustrates--> the value_prop/case_study it depicts
   - section value_prop --contains--> its sub value_props
   - process_step --next--> the following step (loop back if cyclic)
   - stat --attributed_to--> customer
   - case_study --contains--> challenge/solution/quote/outcome; --has_metric--> stats
2. Where binding lives only in visual layout (e.g. floating feature chips), DO NOT guess —
   create the edge as "[NEEDS REVIEW]".
3. Write edges to relatedTo[] with {target, relationType}.

## Guardrails
- Edges are references, never copied text. No fabricated attributions.

## POC note
Core verbs (proves / illustrates / contains) should be NATIVE Contentful reference fields;
keep relatedTo Object for the long-tail vocabulary only.
