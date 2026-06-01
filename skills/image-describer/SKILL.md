---
name: image-describer
description: Generate self-contained semantic descriptions / alt-text for image atoms (screenshots, architecture diagrams, data-viz) so they are retrievable. Use when an atom is an image, when slides contain product screenshots or charts, or when image content must be searchable. Runs on image-type atoms produced by slides-atomizer.
---

# image-describer

Makes image atoms retrievable. An image with no description is invisible to search.

## Workflow
1. For each image atom, produce a semanticSummary describing WHAT it depicts and WHAT it
   illustrates (the entry/value prop it supports).
2. For data_viz: state the metric, trend, and axis meaning, not just "a chart".
3. For architecture_diagram: attempt a structured payload (nodes + edges as JSON). If the
   structure is non-trivial, set payload to "[NEEDS REVIEW]" and keep the prose description.
4. Link back to the source asset.

## Guardrails
- Never assert numbers you can't read from the image. Diagrams default to [NEEDS REVIEW] for
  structured payload in POC mode.
