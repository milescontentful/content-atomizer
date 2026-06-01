# Master Build Doc: Context-Preserving Content Atomization for Meta

## Executive summary

Meta wants to turn its product marketing materials into reusable, AI-ready building blocks: break decks and docs into "atoms" (a value prop, a stat, a quote, an image), store them in a governed system, and let an AI engine assemble net-new slides on demand from approved content. The hard part isn't ingestion — it's **keeping the context** when you shatter a document apart, so each atom can still be found, trusted, related to its source, and reassembled coherently. The core idea: the rich metadata captured at atomization time is the product, and Contentful is the governed, queryable knowledge layer that holds it.

This blueprint has been pressure-tested against two real, structurally opposite decks (a marketing field deck and a 200-slide "deck-of-decks") and the core model held both times — every gap surfaced was additive, not a rewrite. It defines a lean, demo-ready POC content model, a chained set of Skills, and a runnable Slides → Contentful ETL pipeline. It also resolves the build/buy boundary: **Contentful owns everything up to and including the governed atom layer plus the context that governs it; Meta owns the AI engine, generation, and orchestration on top.** The capstone idea is context-as-content — storing tone, brand voice, positioning, and guardrails as governed Contentful entries so prompt engineering becomes content modeling: versioned, permissioned, collaborative, and auto-propagating.

**The 30-second pitch:** structured atoms beat dumping PDFs into a RAG pipeline because the structure lets the engine reason, not just search; one field edit propagates everywhere with no re-embedding tax; and governance (roles, permissions, draft→approved, audit history) is native to Contentful, not something we build.

### Document map

- **The thinking (Sections 1–7):** first principles, the three levels of context, why structured atoms beat raw RAG, the Slides-first methodology, the metadata schema, the update/removal/re-sync lifecycle, and the knowledge-as-code pattern.  
- **The proof (Section 8):** three worked examples plus a full-deck gap analysis against a real deck.  
- **The plan (Sections 9–10):** the lean POC content model, the atom-depth rule, the demo script, and the major open questions.  
- **The build (Sections 11–15):** full Skill specs for Cursor, repo layout and build order, the anchor architecture diagram, concrete data contracts (the JSON Cursor builds against), and the deterministic parser stub.  
- **The details (Sections 16–19):** glossary, the Cursor PLAN-mode kickoff prompt, asset ingestion, and the content-model audit checklist for your existing space.  
- **The validation & roadmap (Sections 20–23):** the second-deck stress test, the runnable ETL ingestion pipeline, what's deferred to a later phase, and the context-as-content capstone.

---

**What this document is.** A single, self-contained build reference for the Meta content-atomization POC. It consolidates everything validated so far: the methodology, three worked examples against a real deck, a full-deck gap analysis, a demo-ready POC blueprint, the open questions, and complete `SKILL.md` specs you can paste straight into Cursor. It is intentionally long and structured so it can be cut apart into separate files later.

**How to use it.** Sections 1–6 are the thinking (paste into Glean / Google Docs as the working doc). Section 7 onward are the buildable artifacts (each skill is fenced so you can copy it into its own folder). Section 9 is the file/folder layout for the repo.

---

## Table of contents

1. Purpose & first principles  
2. The three levels of context  
3. Why structured atoms beat a raw RAG dump  
4. The atomization methodology (Google Slides first)  
5. The metadata schema (delivery / retrieval / discovery / provenance)  
6. Lifecycle: updates, removal, re-sync at scale  
7. Context preservation: knowledge-as-code pattern  
8. Worked examples against the real deck (3) \+ full-deck gap analysis  
9. POC blueprint (lean model, atom-depth rule, demo script)  
10. Major open questions (decision list)  
11. The skills — full `SKILL.md` specs for Cursor  
12. Repo layout & build order  
13. Anchor architecture diagram  
14. Concrete data contracts (hand these to Cursor first)  
15. `scripts/parse_slides.py` (deterministic parser stub)  
16. Glossary  
17. Cursor PLAN MODE kickoff prompt  
18. Asset ingestion (images, screenshots, diagrams)  
19. Content-model audit checklist (run against the live space first)  
20. Second stress test — the all-up Modular Field Deck (deck-of-decks)  
21. The ETL ingestion pipeline (Extract → Transform → Load)  
22. What's not yet covered (the road beyond ingestion)  
23. Contentful as the context & data store (context-as-content)

---

# 1\. Purpose & first principles

Meta wants to take product marketing materials (Google Slides and Google Docs), break them into reusable **atoms**, and feed them to an AI engine so sales reps can query a chatbot and have it generate net-new slides from approved content. This is the "componentized single source of truth that any agent can prompt against" pattern: capture copy, imagery, proof points, and insights once, and let the engine assemble them on demand.

The hard part is **not** ingestion. The hard part is making sure that when you shatter a document into atoms you don't lose the meaning that lived in the *arrangement* of those atoms — and that every atom carries enough metadata to be found, trusted, related to its source, and reassembled correctly.

**Central principle:**

**The metadata you capture at atomization time is the product.** It powers delivery (how the engine assembles output), retrieval (how the engine finds the right atom), and discovery (how a human or agent browses what exists). Atomizing without rich structured metadata produces "smarter document search." Atomizing *with* it produces a knowledge graph an engine can reason over.

The three "keep the context" approaches you weren't sure about are **not** alternatives — they are layers of one system, tied together by metadata: the structured knowledge graph (Contentful), the progressive-disclosure context pattern, and the atom-level metadata schema. This document treats them as one stack.

---

# 2\. The three levels of context

Every metadata decision should map back to one of these levels.

### Level 1 — Document context (the whole)

The intent, audience, campaign, and narrative arc of the source. Lost first when you shatter a deck. Preserve via a **Source Document parent entry** that every atom references and that holds original ordering, campaign, product line, approval status, owner, and review cadence.

### Level 2 — Atom context (the piece)

What an atom *is* and *means* on its own. An atom must be self-describing — readable without its surrounding document. Carries atom-type, the claim it makes, the proof it offers, and a self-contained semantic summary.

### Level 3 — Relationship context (how atoms connect)

The most valuable and most fragile layer: a proof point supports a value prop; a stat backs a claim; an image illustrates a benefit; a CTA follows a beat. These are what let the engine assemble a *coherent* slide rather than a pile of correct-but-unrelated fragments. Model as explicit references, never as prose.

**Rule of thumb:** if meaning lives only in the *visual arrangement* of a slide (this caption under this chart; this quote beside this logo), promote it into an explicit field or reference before atomizing — otherwise it is gone.

---

# 3\. Why structured atoms beat a raw RAG dump

The positioning that drives every modeling choice:

- **Reasoning vs. search.** If knowledge stays locked in slides/PDFs, even well-tagged, the engine does smarter document search, not reasoning. When persona, vertical, journey stage, proof type, and ownership are *fields*, the engine can filter and assemble: "for Healthcare, CISO, Proposal stage, Product X → this value prop \+ its linked proof points \+ the latest approved visual."  
- **Single-field updates propagate everywhere.** Change one field and every future generated answer that hits that atom is instantly correct. Decks/PDFs become linked artifacts, not the source of truth.  
- **No re-embedding tax.** Traditional RAG: change an attachment → delete file → remove embedding → re-upload → re-index (token cost, stale/dup risk, engineer babysitting). A structured layer lets you change the atom in place; semantics re-vectorize off the governed record.  
- **Governance is native.** Atoms can be "brand approved" and locked from AI edits; internal-only atoms partitioned from external. The engine retrieves only approved, published, permissioned content.

This is the story to lead with for Meta: **Contentful \= the governed, queryable knowledge graph; the AI engine \= unified retrieval \+ generation on top of it.**

---

# 4\. The atomization methodology (Google Slides first)

Slides are the right start: already semi-atomized, visual structure maps to discrete blocks, and the Slides API exposes structure (shapes, text runs, images, speaker notes) you can parse deterministically. Docs are phase 2 because meaning flows continuously.

### Step 0 — Establish the atom taxonomy (what counts as an atom)

Decide canonical atom types before parsing. Starter set:

| Atom type | Example | Role in generation |
| :---- | :---- | :---- |
| value\_proposition | "Publish in minutes without developers" | Headline / narrative spine |
| proof\_point | "Cut update time from \~2 weeks to \~5 minutes" | Supports a value prop |
| stat | "40% reduction in content creation costs" | Backs a claim, hero number |
| quote | A named testimonial | Social proof |
| case\_study | Challenge / solution / results | Reference story |
| image | Hero image, diagram, screenshot | Slide visual |
| cta | "Book a demo" | Closing beat |
| insight | A market trend or thesis | Framing / opener |

Atom type is itself high-value metadata: it drives retrieval ("find a proof point") and delivery (the engine knows a proof point goes *under* a value prop).

### Step 1 — Create the Source Document parent (Level 1\)

One entry per deck: title, campaign, product line, audience/persona, approval status, owner, source URL, dates, review cadence, **original slide order**. Every atom links to it.

### Step 2 — Parse the deck into slide-level units

Walk slide by slide via the Slides API. Capture slide index (ordering), layout/section, **speaker notes** (often the richest context — the *why*), and the shapes/text/images present. Treat notes as a first-class context source.

### Step 3 — Extract atoms from each slide (Level 2\)

Split by structural \+ semantic boundaries. For each atom: raw content, atom type, a **self-contained semantic summary**, and claim/proof where applicable. For images: alt-text/description, what it depicts, the entry it illustrates, link to source asset.

### Step 4 — Capture relationships (Level 3\)

Record as explicit references: proof→supports→value prop; stat→backs→claim; image→illustrates→value prop/case study; cta→follows→beat; atom→belongs to→source document (+ position).

### Step 5 — Apply taxonomy & metadata

Tag against the controlled taxonomy (persona, vertical, journey stage, product, region, approval). Stable term IDs are non-negotiable at Meta's 30K+ term scale.

### Step 6 — Draft \+ human-in-the-loop

Land atoms in **draft**. A human approves before retrievable. Approval state gates retrieval. (Never imply AI publishes unreviewed.)

### Step 7 — Vectorize for semantic retrieval

On approval, embed off the governed atom (content \+ semantic summary) → hybrid search (keyword \+ taxonomy \+ semantic) with no separate third-party vector DB for in-platform content.

---

# 5\. The metadata schema (organized by the four jobs)

Every field should justify itself against one of four jobs. Many serve several — that's the signal of a high-value field.

**Discovery (browse what exists):** atom type, product line, campaign, persona, vertical, region; approval status; internal/external flag; source link, owner, last-reviewed, cadence; title \+ semantic summary.

**Retrieval (engine finds the right atom):** taxonomy terms (persona, stage, workflow, product, vertical); embedding \+ the summary that seeds it; claim/topic keywords, proof type; status filters; recency/freshness.

**Delivery (engine assembles coherent output):** atom type (role in a slide); relationship references; original document \+ ordering; brand/voice constraints \+ do-not-modify locks; format hints (headline / bullet / callout / full-bleed image).

**Provenance (trust \+ auditability, cross-cutting):** source document ID, slide index, extraction timestamp, method/version, confidence. Lets generated slides cite exactly which atoms were used and link back.

**Design test:** for every field ask "does this serve delivery, retrieval, discovery, or provenance?" If none, cut it. Too much irrelevant metadata degrades model output — capture what earns its place.

---

# 6\. Lifecycle: updates, removal, and re-sync at scale

These documents change over time, and the content team must be able to maintain them both **hands-on in Contentful** and **at scale via AI Actions**.

### Two interaction modes, both first-class

- **Hands-on in Contentful:** native UI, in-context editing/preview, workflows — content team edits a single atom or whole document directly.  
- **AI Actions at scale:** governed, templated, context-aware bulk changes (e.g. retone every value prop, refresh a stat everywhere) — not dumb find-and-replace.

### Update propagation

Because atoms are **referenced, not copied**, one edit corrects every future generated deck — no RAG-style re-embedding tax. Two safety rules on any change: **re-vectorize** the atom and **re-validate its tags**.

### Removal without breaking the graph

- Check reference views before deleting (what points at this atom?).  
- Prefer **unpublish/archive over hard delete** so the graph doesn't break.  
- Cascade from the Source Document when a whole doc is retired.  
- "Remove from engine" (status flip → not retrievable) is different from "delete forever."

### Versioning, audit, governance

Every human or AI change is a reversible revision in the governed environment. **Brand-approved** atoms are locked from AI modification via tag-based rules.

### Source re-sync

Stable external IDs (`sourceDocId`, `atomKey`), **incremental upserts (deltas, not full rebuilds)**, and **never clobber human edits** on re-sync.

---

# 7\. Context preservation: the knowledge-as-code pattern

To keep document and relationship context usable without flooding the engine:

- **Always-loaded index:** the Source Document parent \+ a routing summary of what atoms exist and how they cluster — enough to *route* a query.  
- **Per-atom detail on demand:** full content, relationships, proof load only when an atom is selected.

This mirrors how skills load (lightweight metadata first, full instructions on selection) and keeps context windows clean (large irrelevant context hurts reliability).

Concretely:

1. **Compile around domain concepts, not raw structure.** "Value prop for Product X" may span atoms and decks — compile the cluster.  
2. **Source Document \= the document-context carrier / index node** (narrative order \+ campaign intent).  
3. **Relationships \= graph edges** the engine traverses to assemble coherent output.

---

# 8\. Worked examples \+ full-deck gap analysis

Validated against the real deck: **\[TEMPLATE\] Contentful Personalization | Modular Field Deck | Q2FY27**.

## 8.1 Example 1 — the composite value slide

*"Deliver relevant experiences that convert, without leaving Contentful."* Bundles 1 section value prop \+ 4 sub-value-props \+ 3 customer proof stats \+ 1 UI screenshot \+ narration in notes → **1 Source Document parent \+ 9 atoms \+ explicit relationships.**

Atoms: section VP (1); four sub-VPs (2–5: convert more visitors; first-party data; built into flow; AI grounded in your content); three stats (6 Kraft Heinz 78% conversion; 7 Ace & Tate 87% CTR; 8 Ruggable \<30min); one image (9 Experiments dashboard).

Relationships:

```
atom1 --contains--> atom2,3,4,5
atom6 --proves--> atom2 ; atom7 --proves--> atom2 ; atom8 --proves--> atom4
atom9 --illustrates--> atom2, atom4
all --belongs_to--> SourceDocument(slide N)
stats6,7,8 --attributed_to--> Customer(KraftHeinz/Ace&Tate/Ruggable)
```

**Key validation:** stats become reusable only because the number+label are fused into one atom AND each carries a `proves →` edge and an `attributed_to →` edge. "87%" alone is dead; "87% higher CTR for Ace & Tate, proving the conversion value prop" is reusable.

## 8.2 Example 2 — the 5-step optimization loop (sequential/process)

Held up, but added a **new ordered \+ cyclic relationship** (`next →`) that loops step 5 back to step 1 — deck-composer must honor sequence when regenerating.  Surfaced the **"floating feature chips" crack** — labels (Audience Suggestions, Variant generator) with no visual binding to the steps they power; that mapping lives only in layout → needs `[NEEDS REVIEW]`, not a guess.

## 8.3 Example 3 — the Ace & Tate case study (dense, structured)

Two new findings: **atoms can nest** — a `case_study` is a mini-document that `contains` challenge/solution/quote/outcome atoms and `has_metric` operational stats;  and **proof metrics are heterogeneous** — operational stats (11 markets, 30+ campaigns, 5 locales), not conversion/CTR, so retrieval should let the engine ask for a *type* of proof. The big "Notes" backup block argues for progressive disclosure at ingestion (store as `backupDetail`, atomize on demand).

## 8.4 Full-deck coverage & gaps

A pass across \~30 slide archetypes (title, problem clusters, value composites, process, matrices, architecture diagrams, swimlanes, use-case library, capability matrices, differentiators, data-viz, roadmap, case-study library, internal Contentful-on-Contentful sub-deck).

**The core three-level model never broke** — every addition was additive. What changed was the shape around the edges. The seven model changes the full pass surfaced:

1. **Add a `collection`/`section` level above `sourceDocument`.** The deck is really four bundled libraries (core, use-case, case-study, internal) — "\[TEMPLATE\] Modular Field Deck" means assembled from modules, not read linearly. **Biggest change.**  
2. **Move `internalExternal` to section \+ atom, stricter-wins** — internal sections carry real financials (+$5.5m pipeline, \+12% MQLs); per-atom-only gating risks leakage.  
3. **Add `provenanceClass`** (customer\_outcome vs internal\_experiment) so Contentful's own numbers (+195% CTR, \+276% traffic) are never shown as customer proof.  
4. **Give diagram atoms a structured `payload` (JSON nodes/edges)** or auto-flag `[NEEDS REVIEW]` — a one-line summary flattens architecture meaning. Weakest automation spot.  
5. **Extend dedup to notes/boilerplate** (the "Let's take a closer look…" note repeats on \~7 slides) and add a **`conflictsWith` flag**.  
6. **Add `app`/`partner`/`integration` entity types** (Shopify, Algolia, Cloudinary, Talon.One…) so "case studies using Shopify" works.  
7. **Collapse \~30 atom types into a core set \+ `subtype`** to keep the taxonomy maintainable.

**Conflicts surfaced at scale** (need human resolution, not silent first-wins): Personio 45% vs 46%; Kraft Heinz CSAT 28% vs 30%; Pets Deli "51%" vs "not disclosed."

---

# 9\. POC blueprint

The guiding decision: **model the minimum that proves the thesis.** Defer governance-at-scale, dedup, and edge-case fidelity explicitly — don't drop them.

## 9.1 Lean POC content model (answers the "too busy" worry)

### `sourceDocument` (6 fields)

| Field | Type | Why in POC |
| :---- | :---- | :---- |
| title | Symbol | Identify source |
| productLine | taxonomy ref | First filter |
| audience | taxonomy ref | Second filter |
| sourceUrl | Symbol | Provenance |
| internalExternal | enum | The one governance field worth proving early |
| atoms | Array\<Ref → contentAtom\> | The graph |

### `contentAtom` (8 fields)

| Field | Type | Why in POC |
| :---- | :---- | :---- |
| atomType | enum | Drives retrieval \+ role in assembly |
| body | Text/RichText | The content |
| semanticSummary | Text (LLM) | Powers semantic retrieval; self-contained |
| metric | Symbol ("87% higher CTR for Ace & Tate") | Stat+label fused — the must-have pattern |
| relatedTo | Array\<Ref \+ relationType\> | One generic relationship field instead of many |
| sourceDocument | Ref | Provenance \+ reassembly |
| attributedTo | Ref → customer | Proof carries its owner |
| status | native draft/published | Gates retrieval |

### `customer` (3 fields)

`name`, `industry`, `region`.

### Deferred to production (safe to defer)

`subtype`; `brandApproved` lock, `lastReviewed`, cadence; `provenanceClass`; `collection`/`section` level; structured diagram `payload`; `conflictsWith` \+ dedup keys; `app`/`partner` entities; per-verb relationship fields.

**Stakeholder framing:** "Here's the lean model that proves it. Here's the production model it grows into — every added field earns its place by serving delivery, retrieval, discovery, or provenance." Staged, not incomplete.

## 9.2 Atom depth / granularity rule

**One atom \= one independently reusable idea.** If a fragment can't stand alone in a *different* deck, fold it into its parent.

- Value-prop headline \+ its one supporting sentence \= **one atom**.  
- **Stat \+ label \= one atom** (non-negotiable).  
- Process step \= one atom; the loop is held by parent \+ ordered relationships.  
- **Exception (kept in POC): nesting** — a case study `contains` its sub-atoms. Only allowed nesting.  
- **Too deep:** a bullet's sub-clauses are not separate atoms. Over-atomizing destroys context faster than under-atomizing; when unsure keep the larger unit and let `semanticSummary` carry meaning.  
- Make depth a **parameter** in `slides-atomizer`; ship one setting for the POC.

## 9.3 POC demo script

1. Pick one clean section (core value narrative \+ 1–2 case studies). **Skip** diagrams and the internal sub-deck for v1.  
2. Build the three content types above.  
3. Run `slides-atomizer` on \~5–8 slides → draft atoms.  
4. Human approves (shows the gate live).  
5. Vectorize approved atoms.  
6. Demo: **rep query → retrieve (taxonomy \+ semantic) → assemble a slide honoring relationships → cite source atoms.**  
7. Show **one edit**: change a stat in Contentful (or via an AI Action) → regenerate → new deck picks it up with no re-embedding (the lifecycle payoff in one move).

---

# 10\. Major open questions (decision list)

**Architecture / model**

1. **Collection vs flat:** model the collection/section level now or after the POC? (Rec: flat for POC, collection for production.)  
2. **Diagram fidelity:** skip / image+description / structured JSON payload? (Rec: skip for POC; decide for production. Biggest automation risk.)  
3. **Granularity standard:** is "one independently reusable idea" the right default, and where do we deviate?

**Data integrity at scale** 4\. **Dedup / single source of truth:** one canonical stat atom referenced many times, or one per occurrence? Dedup key? 5\. **Conflict resolution:** who arbitrates (45% vs 46%), and does the pipeline hard-block or flag?

**Governance / trust** 6\. **Internal-results leakage:** gating sectional, atom-level, or both — who sets it? 7\. **Provenance classes:** distinguish customer outcomes from Contentful's own experiment results? 8\. **AI Actions vs human edit boundaries:** what can AI Actions change unattended vs require approval? Where's the lock line for brand-approved atoms?

**Ownership / boundary** 9\. **Taxonomy authority:** who owns the 30K+ term taxonomy and keeps stable IDs? 10\. **Engine boundary (build vs buy):** what's Contentful (knowledge graph \+ retrieval) vs the AI engine (generation/orchestration)? The core architectural contract. 11\. **POC success criteria:** what does "this works" mean to Meta — retrieval precision, generation quality, edit-propagation speed, or governance? Define before building.

**Put first to a stakeholder:** \#10 (build/buy boundary), \#6 (leakage governance), \#11 (success definition).

---

# 11\. The skills — full `SKILL.md` specs for Cursor

Build these as discrete, single-responsibility skills that chain. Each block below is a complete file. Conventions used across all of them:

- One `SKILL.md` per skill, YAML frontmatter with a keyword-rich `description`.  
- Progressive disclosure: keep `SKILL.md` lean; push detail to `references/`.  
- Deterministic parsing (API) separated from LLM steps (summarize, classify, infer).  
- Honest gaps: mark `[NEEDS REVIEW]` rather than guess; route to the human queue.

## 11.1 `slides-atomizer/SKILL.md`

```
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
```

`slides-atomizer/references/atom-taxonomy.md`

```
# Atom taxonomy (core types + subtype)
Use a small CORE type set; refine with `subtype`. Do not create 30 rigid types.

CORE TYPES:
- value_proposition   (subtypes: section, sub, differentiator, benefit, value_lever)
- proof               (subtypes: stat, proof_point, experiment_result)
- quote
- case_study          (a mini-document; may CONTAIN other atoms)
- image               (subtypes: screenshot, architecture_diagram, data_viz)
- feature             (subtypes: capability, integration, audience_segment)
- process_step
- cta
- insight             (subtypes: pain_point, title, tagline, guidance)

PROVENANCE CLASS (on proof atoms): customer_outcome | internal_experiment
```

`slides-atomizer/references/granularity-rule.md`

```
# Granularity rule
DEFAULT (`idea`): one atom = one independently reusable idea.
- headline + its single supporting sentence = ONE atom
- stat + its label = ONE atom (non-negotiable)
- process step = ONE atom (sequence handled by relationships, not merging)
- case study = ONE atom that CONTAINS challenge/solution/quote/outcome atoms (only allowed nesting)

`fine`: split sub-value-props from their section header into separate atoms.
`coarse`: keep an entire slide's value cluster as one atom.

TOO DEEP: a bullet's sub-clauses are NOT separate atoms.
When unsure, keep the larger unit and let semanticSummary carry meaning.
```

`slides-atomizer/references/field-dictionary.md`

```
# Field dictionary (POC lean model)
## sourceDocument
title, productLine, audience, sourceUrl, sourceDocId, internalExternal, slideOrder, atoms[]
## contentAtom
atomType, subtype?, body, semanticSummary, metric?, relatedTo[], sourceDocument,
sourceSlideIndex, atomKey, attributedTo?, status
## customer
name, industry, region
(Production adds: brandApproved, lastReviewed, provenanceClass, conflictsWith, embedding,
collection/section ref, structured diagram payload.)
```

## 11.2 `atom-tagger/SKILL.md`

```
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
```

## 11.3 `relationship-mapper/SKILL.md`

```
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
```

## 11.4 `image-describer/SKILL.md`

```
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
```

## 11.5 `deck-composer/SKILL.md` (delivery side)

```
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
```

## 11.6 `change-propagator/SKILL.md` (lifecycle / re-sync)

```
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
```

## 11.7 `docs-atomizer/SKILL.md` (phase 2 stub)

```
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
```

---

# 12\. Repo layout & build order

## Suggested folder layout

```
content-atomization-poc/
  model/
    sourceDocument.json        # content type definition (lean POC: 6 fields)
    contentAtom.json           # content type definition (lean POC: 8 fields)
    customer.json              # 3 fields
  skills/
    slides-atomizer/
      SKILL.md
      references/
        atom-taxonomy.md
        granularity-rule.md
        field-dictionary.md
      scripts/
        parse_slides.py        # deterministic Slides API parse
    atom-tagger/SKILL.md
    relationship-mapper/SKILL.md
    image-describer/SKILL.md
    deck-composer/SKILL.md
    change-propagator/SKILL.md
    docs-atomizer/SKILL.md      # phase 2
  taxonomy/
    scheme.json                 # controlled terms + stable IDs
  eval/
    example-slide-expected.json # the Example-1 atoms, as a regression target
```

## Build order (prove small, then scale)

1. **Content model first** — `sourceDocument` \+ `contentAtom` \+ `customer` (lean POC fields). Everything reads/writes against this.  
2. **`slides-atomizer`** end-to-end on the **one** Example-1 slide. Diff output against `eval/example-slide-expected.json`.  
3. **`relationship-mapper`** \+ **`atom-tagger`** on those atoms.  
4. **`image-describer`** on the screenshot atom.  
5. **Vectorize** approved atoms.  
6. **`deck-composer`** — run the demo query loop with citations.  
7. **`change-propagator`** — show the one-edit lifecycle payoff.  
8. Only then scale to a full section, then add the deferred production fields (collection level, provenanceClass, diagram payloads, dedup/conflict handling, app/partner entities).

## One-line verdict for the demo

The three-level context model and the metadata-driven schema held across the entire deck without a single top-level break — so the thesis is sound. The POC's job is to **prove it small and clean** with the lean model, name the staged path to the production model, and surface the eleven decisions that turn a POC into a system.

---

# 13\. Anchor architecture diagram

Paste this Mermaid block at the top of the Google Doc (or render it as an image). It collapses the whole doc into one picture: ingest → atomize → govern → store → retrieve → generate, with the maintenance loop wrapping back.

```
flowchart TB
    subgraph INGEST["1. Ingest & Atomize (slides-atomizer)"]
        GS[Google Slides deck] -->|deterministic parse: slides, text, images, NOTES| SU[Slide units]
        SU -->|LLM extract: type + semanticSummary + fused metric| ATM[Draft atoms]
    end

    subgraph ENRICH["2. Enrich (chained skills)"]
        ATM --> REL[relationship-mapper: proves / illustrates / contains / next]
        ATM --> TAG[atom-tagger: persona / vertical / stage / product / region]
        ATM --> IMG[image-describer: describe + diagram payload]
    end

    subgraph GOVERN["3. Govern (human-in-the-loop)"]
        REL --> RV{Review queue\n[NEEDS REVIEW]}
        TAG --> RV
        IMG --> RV
        RV -->|approve| PUB[(Published + approved atoms)]
    end

    PUB -->|embed on publish| VEC[(Semantic index + knowledge graph)]

    subgraph DELIVER["4. Retrieve & Generate (deck-composer)"]
        Q[Rep chatbot query] -->|taxonomy filter + semantic search| VEC
        VEC --> TRAV[Traverse relationships:\nspine VP -> proofs -> visual -> ordered steps]
        TRAV --> OUT[Generated slide + citations to atomKeys]
    end

    subgraph MAINTAIN["5. Maintain (change-propagator)"]
        EDIT[Edit in Contentful UI\nOR AI Action bulk change] --> PUB
        GS -.source edited.-> RESYNC[Delta upsert by atomKey\nnever clobber human edits]
        RESYNC --> RV
        PUB -.unpublish / archive\n!= delete.-> REMOVE[Removed from engine\naudit trail kept]
    end

    OUT -.feedback: thin retrieval / conflicts surfaced.-> RV
```

Reading guide for a stakeholder: boxes 1–3 are the build pipeline, box 4 is the demo moment (the rep query → generated slide), and box 5 is the "this is a living system, not a migration" story.

---

# 14\. Concrete data contracts (hand these to Cursor first)

These are the literal targets. Building against concrete JSON beats building against prose — the model can diff its output against these.

## 14.1 `eval/example-slide-expected.json` (the regression anchor)

The Example-1 composite value slide, fully expanded. This is the "did the atomizer get it right?" oracle.

```json
{
  "sourceDocument": {
    "atomKey": "src-personalization-modular-field-deck-q2fy27",
    "title": "Contentful Personalization — Modular Field Deck Q2FY27",
    "productLine": "contentful-personalization",
    "audience": ["marketing-leader", "digital-experience-buyer"],
    "sourceUrl": "https://docs.google.com/presentation/d/1lDdGqlqRABuSBfv5eW79aXlT3oIKiFeF5DPdLJzRDmw",
    "sourceDocId": "gslides-1lDdGqlqRABuSBfv5eW79aXlT3oIKiFeF5DPdLJzRDmw",
    "internalExternal": "internal",
    "slideOrder": ["atom-vp-section", "atom-vp-convert", "atom-vp-firstparty", "atom-vp-flow", "atom-vp-ai", "atom-stat-kraftheinz", "atom-stat-acetate", "atom-stat-ruggable", "atom-img-experiments"]
  },
  "atoms": [
    {
      "atomKey": "atom-vp-section",
      "atomType": "value_proposition",
      "subtype": "section",
      "body": "Deliver relevant experiences that convert, without leaving Contentful",
      "semanticSummary": "The overarching promise: deliver relevant, converting experiences without leaving the CMS.",
      "relatedTo": [
        {"target": "atom-vp-convert", "relationType": "contains"},
        {"target": "atom-vp-firstparty", "relationType": "contains"},
        {"target": "atom-vp-flow", "relationType": "contains"},
        {"target": "atom-vp-ai", "relationType": "contains"}
      ],
      "sourceDocument": "src-personalization-modular-field-deck-q2fy27",
      "sourceSlideIndex": "N",
      "status": "draft"
    },
    {
      "atomKey": "atom-vp-convert",
      "atomType": "value_proposition",
      "subtype": "sub",
      "body": "Convert more visitors into customers — build audience segments and content variants that drive higher CTR and conversions",
      "semanticSummary": "Personalization lifts CTR and conversion via audience segments and content variants.",
      "relatedTo": [],
      "sourceDocument": "src-personalization-modular-field-deck-q2fy27",
      "sourceSlideIndex": "N",
      "status": "draft"
    },
    {
      "atomKey": "atom-vp-firstparty",
      "atomType": "value_proposition",
      "subtype": "sub",
      "body": "Your first-party data, finally working for you — define segments with any customer data by connecting CRM, CDP, or warehouse signals directly to content decisions",
      "semanticSummary": "Activates first-party data (CRM/CDP/DWH) directly into content decisions.",
      "relatedTo": [],
      "sourceDocument": "src-personalization-modular-field-deck-q2fy27",
      "sourceSlideIndex": "N",
      "status": "draft"
    },
    {
      "atomKey": "atom-vp-flow",
      "atomType": "value_proposition",
      "subtype": "sub",
      "body": "Built into your flow of work — personalize in the same Contentful workspace. No new tools, no dev tickets, no stitching",
      "semanticSummary": "Personalization is native to Contentful with no new tools or developer dependency.",
      "relatedTo": [],
      "sourceDocument": "src-personalization-modular-field-deck-q2fy27",
      "sourceSlideIndex": "N",
      "status": "draft"
    },
    {
      "atomKey": "atom-vp-ai",
      "atomType": "value_proposition",
      "subtype": "sub",
      "body": "Let AI surface what you would never find — AI is grounded in your actual content model and customer data, so suggestions are contextually accurate from day one",
      "semanticSummary": "AI suggestions are grounded in the customer's own content model and data, accurate from day one.",
      "relatedTo": [],
      "sourceDocument": "src-personalization-modular-field-deck-q2fy27",
      "sourceSlideIndex": "N",
      "status": "draft"
    },
    {
      "atomKey": "atom-stat-kraftheinz",
      "atomType": "proof",
      "subtype": "stat",
      "body": "78% increase in conversion rate by Kraft Heinz",
      "metric": "78% increase in conversion rate (Kraft Heinz)",
      "semanticSummary": "Kraft Heinz saw a 78% increase in conversion rate with Contentful Personalization.",
      "provenanceClass": "customer_outcome",
      "attributedTo": "customer-kraft-heinz",
      "relatedTo": [{"target": "atom-vp-convert", "relationType": "proves"}],
      "sourceDocument": "src-personalization-modular-field-deck-q2fy27",
      "sourceSlideIndex": "N",
      "status": "draft"
    },
    {
      "atomKey": "atom-stat-acetate",
      "atomType": "proof",
      "subtype": "stat",
      "body": "87% higher CTR for Ace & Tate",
      "metric": "87% higher CTR (Ace & Tate)",
      "semanticSummary": "Ace & Tate saw 87% higher click-through rate with Contentful Personalization.",
      "provenanceClass": "customer_outcome",
      "attributedTo": "customer-ace-and-tate",
      "relatedTo": [{"target": "atom-vp-convert", "relationType": "proves"}],
      "sourceDocument": "src-personalization-modular-field-deck-q2fy27",
      "sourceSlideIndex": "N",
      "status": "draft"
    },
    {
      "atomKey": "atom-stat-ruggable",
      "atomType": "proof",
      "subtype": "stat",
      "body": "Under 30 minutes for Ruggable to personalize experiences",
      "metric": "<30min time-to-value (Ruggable)",
      "semanticSummary": "Ruggable was personalizing experiences in under 30 minutes (fast time-to-value).",
      "provenanceClass": "customer_outcome",
      "attributedTo": "customer-ruggable",
      "relatedTo": [{"target": "atom-vp-flow", "relationType": "proves"}],
      "sourceDocument": "src-personalization-modular-field-deck-q2fy27",
      "sourceSlideIndex": "N",
      "status": "draft"
    },
    {
      "atomKey": "atom-img-experiments",
      "atomType": "image",
      "subtype": "screenshot",
      "asset": "asset-experiments-dashboard",
      "body": "Experiments dashboard screenshot",
      "semanticSummary": "Screenshot of the Contentful Experiments dashboard listing experiments with status, audience, and performance metrics.",
      "relatedTo": [
        {"target": "atom-vp-convert", "relationType": "illustrates"},
        {"target": "atom-vp-flow", "relationType": "illustrates"}
      ],
      "sourceDocument": "src-personalization-modular-field-deck-q2fy27",
      "sourceSlideIndex": "N",
      "status": "draft"
    }
  ],
  "customers": [
    {"atomKey": "customer-kraft-heinz", "name": "Kraft Heinz", "industry": "CPG / Food & Beverage", "region": "North America"},
    {"atomKey": "customer-ace-and-tate", "name": "Ace & Tate", "industry": "Retail / Eyewear", "region": "EMEA"},
    {"atomKey": "customer-ruggable", "name": "Ruggable", "industry": "Retail / Home Goods", "region": "North America"}
  ],
  "reviewQueue": [
    {"atomKey": "src-personalization-modular-field-deck-q2fy27", "field": "sourceSlideIndex", "reason": "Confirm actual slide index in deck", "value": "[NEEDS REVIEW]"}
  ]
}
```

## 14.2 Content-type definitions (`model/*.json`)

Lean POC shape, written as portable JSON the Contentful content-model setup can be derived from. Field IDs match the dictionary in Section 11\.

```json
// model/sourceDocument.json
{
  "name": "Source Document",
  "id": "sourceDocument",
  "fields": [
    {"id": "title", "type": "Symbol", "required": true},
    {"id": "productLine", "type": "Link", "linkType": "Entry", "validations": ["taxonomyTerm"]},
    {"id": "audience", "type": "Array", "items": {"type": "Link", "linkType": "Entry"}},
    {"id": "sourceUrl", "type": "Symbol"},
    {"id": "sourceDocId", "type": "Symbol", "required": true, "unique": true},
    {"id": "internalExternal", "type": "Symbol", "validations": [{"in": ["internal", "external"]}], "default": "internal"},
    {"id": "slideOrder", "type": "Object"},
    {"id": "atoms", "type": "Array", "items": {"type": "Link", "linkType": "Entry", "validations": [{"linkContentType": ["contentAtom"]}]}}
  ]
}
```

```json
// model/contentAtom.json
{
  "name": "Content Atom",
  "id": "contentAtom",
  "fields": [
    {"id": "atomKey", "type": "Symbol", "required": true, "unique": true},
    {"id": "atomType", "type": "Symbol", "required": true, "validations": [{"in": ["value_proposition", "proof", "quote", "case_study", "image", "feature", "process_step", "cta", "insight"]}]},
    {"id": "subtype", "type": "Symbol"},
    {"id": "body", "type": "Text", "required": true},
    {"id": "semanticSummary", "type": "Text", "required": true},
    {"id": "metric", "type": "Symbol"},
    {"id": "asset", "type": "Link", "linkType": "Asset"},
    {"id": "relatedTo", "type": "Object"},
    {"id": "attributedTo", "type": "Link", "linkType": "Entry", "validations": [{"linkContentType": ["customer"]}]},
    {"id": "sourceDocument", "type": "Link", "linkType": "Entry", "validations": [{"linkContentType": ["sourceDocument"]}]},
    {"id": "sourceSlideIndex", "type": "Integer"},
    {"id": "status", "type": "Symbol", "validations": [{"in": ["draft", "published"]}], "default": "draft"}
  ]
}
```

```json
// model/customer.json
{
  "name": "Customer",
  "id": "customer",
  "fields": [
    {"id": "atomKey", "type": "Symbol", "required": true, "unique": true},
    {"id": "name", "type": "Symbol", "required": true},
    {"id": "industry", "type": "Symbol"},
    {"id": "region", "type": "Symbol"}
  ]
}
```

Note on `relatedTo`: modeled as `Object` (JSON array of `{target, relationType}`) for the POC so you can iterate on the relationship vocabulary without schema migrations. For production, consider promoting it to typed reference fields once the vocabulary stabilizes.

## 14.3 `taxonomy/scheme.json` (starter controlled terms)

A seed so `atom-tagger` has stable IDs to validate against. Replace with Meta's real 30K-term taxonomy later — the structure (stable `id` \+ human `label` \+ `dimension`) is what matters.

```json
{
  "dimensions": {
    "persona": [
      {"id": "marketing-leader", "label": "Marketing Leader"},
      {"id": "digital-experience-buyer", "label": "Digital Experience Buyer"},
      {"id": "developer", "label": "Developer"},
      {"id": "content-editor", "label": "Content Editor"}
    ],
    "vertical": [
      {"id": "retail", "label": "Retail"},
      {"id": "cpg", "label": "CPG / Food & Beverage"},
      {"id": "financial-services", "label": "Financial Services"},
      {"id": "technology", "label": "Technology"}
    ],
    "journeyStage": [
      {"id": "awareness", "label": "Awareness"},
      {"id": "consideration", "label": "Consideration"},
      {"id": "proposal", "label": "Proposal"},
      {"id": "expansion", "label": "Expansion"}
    ],
    "product": [
      {"id": "contentful-personalization", "label": "Contentful Personalization"},
      {"id": "contentful-studio", "label": "Contentful Studio"},
      {"id": "contentful-ai", "label": "Contentful AI"}
    ],
    "region": [
      {"id": "north-america", "label": "North America"},
      {"id": "emea", "label": "EMEA"},
      {"id": "apac", "label": "APAC"}
    ]
  }
}
```

---

# 15\. `scripts/parse_slides.py` (deterministic parser stub)

The deterministic half of `slides-atomizer`. Walks the deck and emits the raw structure the LLM step consumes — slides in order, text runs, image refs, and speaker notes. No model variance here.

```py
"""parse_slides.py — deterministic Google Slides parse for slides-atomizer.

Emits a JSON structure of slides (in order) with text runs, image refs, and
speaker notes. This is the deterministic input to the LLM atom-extraction step.
Auth/credentials are environment-specific; wire your own service account.
"""
import json
from typing import Any

# from googleapiclient.discovery import build  # wire in Cursor

def _text_from_shape(shape: dict[str, Any]) -> str:
    runs = []
    for el in shape.get("text", {}).get("textElements", []):
        run = el.get("textRun")
        if run and run.get("content"):
            runs.append(run["content"])
    return "".join(runs).strip()

def _speaker_notes(slide: dict[str, Any]) -> str:
    notes_page = slide.get("slideProperties", {}).get("notesPage", {})
    parts = []
    for el in notes_page.get("pageElements", []):
        shape = el.get("shape")
        if shape and shape.get("text"):
            parts.append(_text_from_shape(shape))
    return "\n".join(p for p in parts if p).strip()

def parse_deck(presentation: dict[str, Any]) -> dict[str, Any]:
    """presentation = slides.presentations().get(presentationId=...).execute()"""
    out = {
        "presentationId": presentation.get("presentationId"),
        "title": presentation.get("title"),
        "slides": [],
    }
    for idx, slide in enumerate(presentation.get("slides", [])):
        text_runs, image_refs = [], []
        for el in slide.get("pageElements", []):
            shape = el.get("shape")
            if shape and shape.get("text"):
                t = _text_from_shape(shape)
                if t:
                    text_runs.append(t)
            image = el.get("image")
            if image:
                image_refs.append({
                    "objectId": el.get("objectId"),
                    "contentUrl": image.get("contentUrl"),
                    "altText": el.get("description") or el.get("title") or "",
                })
        out["slides"].append({
            "slideIndex": idx,
            "objectId": slide.get("objectId"),
            "layout": slide.get("slideProperties", {}).get("layoutObjectId"),
            "textRuns": text_runs,
            "imageRefs": image_refs,
            "speakerNotes": _speaker_notes(slide),  # first-class context
        })
    return out

def detect_internal_external(deck: dict[str, Any]) -> str:
    """Stricter-wins: any internal/template cue -> internal."""
    haystack = json.dumps(deck).lower()
    cues = ["internal only", "do not use", "[template]", "confidential"]
    return "internal" if any(c in haystack for c in cues) else "external"

if __name__ == "__main__":
    # presentation = build("slides", "v1", credentials=creds) \
    #     .presentations().get(presentationId=DECK_ID).execute()
    # parsed = parse_deck(presentation)
    # parsed["internalExternal"] = detect_internal_external(parsed)
    # print(json.dumps(parsed, indent=2))
    pass
```

---

# 16\. Glossary (so a fresh model has zero ambiguity)

- **Atom** — the smallest independently reusable unit of content (a value prop, a stat, a quote, an image). Self-describing via `semanticSummary`.  
- **Source Document** — the parent entry representing one original deck/doc; holds Level-1 context and original ordering.  
- **Collection / Section** (deferred) — a grouping above Source Document; the deck is really four bundled libraries.  
- **Relationship / edge** — an explicit typed link between atoms (`proves`, `illustrates`, `contains`, `next`, `attributed_to`, …). Level-3 context.  
- **Fused metric** — a number captured together with its label ("87% higher CTR for Ace & Tate"); never a bare number.  
- **Provenance class** — `customer_outcome` vs `internal_experiment`; prevents Contentful's own numbers being shown as customer proof.  
- **`[NEEDS REVIEW]`** — the honest-gap sentinel; written when the pipeline can't determine a value, routed to the human queue instead of guessed.  
- **Re-vectorize** — regenerate an atom's embedding after a change so retrieval stays accurate.  
- **Delta upsert** — re-sync that writes only changed/new atoms (by `atomKey`), never a full rebuild, never clobbering human edits.

---

# 17\. Cursor PLAN MODE kickoff prompt

Paste this at the top of PLAN MODE to orient the agent before it reads the rest of the doc.

```
You are building a POC for context-preserving content atomization (project: Meta AI
Knowledge Base). The full methodology, data contracts, and skill specs are in this
document. Your job in PLAN MODE:

1. Read the whole document. Treat Section 14 (data contracts) as the source of truth for
   shapes, and eval/example-slide-expected.json as the regression target.
2. Propose a build plan that follows Section 12's build order: content model first, then
   slides-atomizer (deterministic parse via scripts/parse_slides.py + LLM extraction),
   then relationship-mapper + atom-tagger, then image-describer, then vectorize, then
   deck-composer, then change-propagator. Phase-2 docs-atomizer last.
3. Build the LEAN POC model only (Section 9.1): 2 content types + 1 entity, ~8 fields max.
   Everything in the "Deferred to production" list stays deferred — note it, don't build it.
4. Honor the non-negotiables: stats fused with labels; atoms land in draft (human-in-the-
   loop before retrievable); never guess — write "[NEEDS REVIEW]" and queue it; deterministic
   parsing must not depend on model variance; deck-composer never surfaces internal_experiment
   proof externally and never fabricates content not in retrieved atoms.
5. Validate slides-atomizer against eval/example-slide-expected.json before scaling beyond
   one slide.
6. Surface, do not silently resolve, the open questions in Section 10 — especially the
   build/buy engine boundary (#10), internal-results leakage governance (#6), and POC
   success criteria (#11).

Output a step-by-step plan with file paths, the order of operations, and where you need a
human decision before proceeding.
```

# 18\. Asset ingestion (images, screenshots, diagrams)

Your instinct is correct: wrap each asset and tag it with metadata. The key realization is that Contentful already separates the two things you care about, and our model already has the wrapper — so this is mostly wiring, not new architecture.

## 18.1 The two-layer model

- **Layer 1 — the Contentful Asset (the binary).** A native Asset record holding the actual file (PNG/JPG/SVG/PDF) plus Contentful's built-in `title`, `description`, and `file` fields. This is just the bytes \+ minimal alt-text. It is intentionally thin.  
- **Layer 2 — the wrapper entry (the meaning).** A content entry that *links* to the Asset and carries all the rich metadata, taxonomy, relationships, and provenance. **In our model this wrapper is the `image` contentAtom** — it already has `semanticSummary`, `relatedTo`, `attributedTo`, `sourceDocument`, `sourceSlideIndex`, and taxonomy. So we do not need a new content type for the POC; we just give the image atom a real link to the Asset instead of a string placeholder.

Rule: never let the engine retrieve a bare Asset. It always retrieves the wrapper atom (which carries the description \+ relationships) and resolves the Asset link only at delivery time. A naked binary has no context; the wrapper is what makes it findable and reusable.

## 18.2 One field change to the lean model

The Example-1 JSON uses `"body": "asset://experiments-dashboard.png"` as a placeholder. For real ingestion, add an explicit Asset link to `contentAtom` so the binary and its meaning stay connected:

```json
// add to model/contentAtom.json fields[]
{"id": "asset", "type": "Link", "linkType": "Asset"}
```

The image atom then looks like:

```json
{
  "atomKey": "atom-img-experiments",
  "atomType": "image",
  "subtype": "screenshot",
  "asset": "asset-experiments-dashboard",
  "body": "Experiments dashboard screenshot",
  "semanticSummary": "Screenshot of the Contentful Experiments dashboard listing experiments with status, audience, and performance metrics.",
  "relatedTo": [
    {"target": "atom-vp-convert", "relationType": "illustrates"},
    {"target": "atom-vp-flow", "relationType": "illustrates"}
  ],
  "sourceDocument": "src-personalization-modular-field-deck-q2fy27",
  "sourceSlideIndex": "N",
  "status": "draft"
}
```

`body` stays as a human-readable label; `asset` carries the actual binary link; `semanticSummary` (written by `image-describer`) is what powers retrieval.

## 18.3 Selective ingestion — what to pull vs skip

You said you don't need all of them — correct. Most slide images are chrome, not content. Apply the same "is this independently meaningful?" test used for atom depth:

- **Ingest:** product screenshots, data-viz/charts, architecture diagrams, and any image a generated slide would legitimately reuse as a visual.  
- **Skip:** backgrounds, decorative shapes, slide-master furniture, bullet icons, and (usually) logos — logos belong on the `customer` / `app` / `partner` entity, not as standalone image atoms.  
- **Borderline → `[NEEDS REVIEW]`:** if the parser can't tell whether an image is content or decoration, flag it rather than ingest noise. Over-ingesting assets degrades retrieval the same way too much metadata does.

`parse_slides.py` already collects `imageRefs` (with `contentUrl` \+ `altText`); the ingestion step filters that list against the criteria above before creating any Assets.

## 18.4 Ingestion flow

1. **Filter** the slide's `imageRefs` to the keep-list (18.3).  
2. **Dedup by content hash.** The same screenshot/diagram recurs across slides. Hash the binary; if an Asset with that hash already exists, **reuse it** and just add another wrapper-atom reference. This is the asset-level version of the stat-dedup question — one canonical Asset, many referencing atoms.  
3. **Upload the binary** as a Contentful Asset; set `title` \+ a stable external ID (e.g. `asset-{hash}` or `asset-{sourceDocId}-{objectId}`) for re-sync.  
4. **Create/Link the image contentAtom** (the wrapper) pointing at the Asset, in **draft**.  
5. **Run `image-describer`** to fill `semanticSummary` (and, for diagrams, attempt the structured payload or flag `[NEEDS REVIEW]`).  
6. **Run `relationship-mapper`** to wire `illustrates` edges to the value props/case studies the image supports.  
7. **Tag** via `atom-tagger`, then **human approves**, then **vectorize** the wrapper's text (description \+ summary). The binary itself is not embedded — its *description* is what becomes searchable.

## 18.5 Provenance, lifecycle, and governance (assets follow the same rules)

- **Provenance:** the wrapper atom already carries `sourceDocument` \+ `sourceSlideIndex`, so every asset traces back to the exact slide it came from.  
- **Replace-in-place:** when a screenshot is refreshed, replace the Asset binary; every wrapper atom (and every future generated deck) referencing it updates automatically — no re-linking. Re-run `image-describer` if the visual meaning changed.  
- **Removal:** check reference views first (which atoms link this Asset?), then prefer unpublish/archive over hard delete so referencing atoms don't break. "Remove from engine" (unpublish the wrapper) is still distinct from "delete the binary forever."  
- **Rights/licensing:** if Meta needs usage rights, expiry, or source-credit on imagery, that metadata lives on the wrapper (or a dedicated `mediaAsset` wrapper in production), never on the bare Asset — so governance and retrieval filters can honor it.

## 18.6 When to graduate to a dedicated `mediaAsset` wrapper (production, deferred)

For the POC, the `image` contentAtom is the wrapper and that's enough. Promote to a separate `mediaAsset` content type later only when an asset needs to be **shared and governed independently of any single atom** — e.g. one hero image reused across many decks with its own licensing, rights expiry, approved-variant set, or alt-text-per-locale. At that point image atoms reference `mediaAsset`, and `mediaAsset` references the Contentful Asset — a clean three-tier split (binary → media wrapper → content atom). Keep it deferred until a real reuse/licensing requirement forces it; the two-layer model covers the demo.

---

# 19\. Content-model audit checklist (run this against the live space first)

You already have content models in this space, so the first PLAN-mode task is a **reconciliation**, not a clean build. The governing rule: **additive changes only — never rename or repurpose an existing field in place; flag any conflict as `[NEEDS REVIEW]` and let a human decide.** The Section 14 definitions are the *target*; the live space is the *ground truth* you must not break.

## 19.1 How to run the audit

1. **Pull the live content model.** Export the current content types (e.g. `contentful space export --content-model-only`, or read via the CMA). This is the baseline.  
2. **Diff against Section 14** (`sourceDocument`, `contentAtom`, `customer`) field by field using the matrix below.  
3. **Classify every field** into one of: MATCH (exists, compatible), ADD (missing, create it), CONFLICT (exists but type/validation/ID differs → `[NEEDS REVIEW]`), or REUSE (an existing field already serves this purpose under a different ID → map, don't duplicate).  
4. **Apply only ADDs automatically.** Hold all CONFLICTs and REUSEs for human sign-off before writing.

## 19.2 Decision rules (so the agent doesn't guess)

- **Naming collision, same purpose** → REUSE the existing field; record the ID mapping in `taxonomy/scheme.json` or a `model/field-map.json`. Do not create a duplicate.  
- **Naming collision, different purpose** → CONFLICT. Do not touch the existing field. Propose a namespaced ID (e.g. `atomKey` → `caKey`) and flag `[NEEDS REVIEW]`.  
- **Type mismatch** (e.g. live `relatedTo` is `Array<Link>` but Section 14 says `Object`) → CONFLICT. Prefer the live type if it already works; note the deviation rather than migrating data.  
- **Missing required field** → ADD, but default `required: false` on first pass so existing entries don't fail validation; tighten to `required: true` only after backfill.  
- **`unique` constraints** (`atomKey`, `sourceDocId`) → only add if no existing entries would violate them; otherwise ADD without `unique` and flag for a dedupe pass.  
- **New content type entirely missing** (likely `contentAtom`) → ADD whole, since there's nothing to conflict with.

## 19.3 Field-by-field audit matrix

Run this exact table against the live space. "Status" is filled in during the audit.

### `sourceDocument`

| Field (target) | Type | Required | Notes for audit | Status |
| :---- | :---- | :---- | :---- | :---- |
| title | Symbol | yes | Almost certainly exists in some form — REUSE if so |  |
| productLine | Link→taxonomy | no | Check if a product/category field already exists |  |
| audience | Array | no | May map to an existing persona/segment field |  |
| sourceUrl | Symbol | no | ADD if absent |  |
| sourceDocId | Symbol (unique) | yes | Critical for re-sync — verify uniqueness before adding `unique` |  |
| internalExternal | Symbol enum | yes | Governance gate — ADD if absent; default `internal` |  |
| slideOrder | Object | no | ADD; JSON array of atom refs |  |
| atoms | Array\<Link→contentAtom\> | no | Depends on `contentAtom` existing first |  |

### `contentAtom` (most likely net-new)

| Field (target) | Type | Required | Notes for audit | Status |
| :---- | :---- | :---- | :---- | :---- |
| atomKey | Symbol (unique) | yes | Stable ID for delta upserts |  |
| atomType | Symbol enum | yes | Enum must match Section 14 list |  |
| subtype | Symbol | no | Free-form for POC |  |
| body | Text | yes | The content |  |
| semanticSummary | Text | yes | Seeds the vector |  |
| metric | Symbol | no | Fused stat+label |  |
| asset | Link→Asset | no | The asset-wrapper link (Section 18\) |  |
| relatedTo | Object | no | `{target, relationType}[]` — confirm Object vs typed refs |  |
| attributedTo | Link→customer | no | Proof ownership |  |
| sourceDocument | Link→sourceDocument | no | Back-reference |  |
| sourceSlideIndex | Integer | no | Provenance |  |
| status | Symbol enum | no | draft/published gate |  |

### `customer`

| Field (target) | Type | Required | Notes for audit | Status |
| :---- | :---- | :---- | :---- | :---- |
| atomKey | Symbol (unique) | yes | Or REUSE an existing slug/ID field |  |
| name | Symbol | yes | Likely exists — REUSE |  |
| industry | Symbol | no | May map to an existing vertical field |  |
| region | Symbol | no | ADD if absent |  |

## 19.4 Audit output the agent should produce

- `model/field-map.json` — every REUSE mapping (target ID → live ID).  
- A CONFLICT report — each `[NEEDS REVIEW]` with the live definition, the target definition, and a proposed resolution.  
- A migration plan — ordered list of ADDs (safe to auto-apply) vs. held items (need sign-off).  
- Confirmation that **no existing field was renamed, retyped, or deleted** in the process.

One-line instruction for PLAN mode: *"Reconcile Section 14 against the live space. Auto-apply ADDs as optional fields; for every MATCH/REUSE record the mapping; for every CONFLICT stop and flag `[NEEDS REVIEW]`. Never rename, retype, or delete an existing field."*

---

# 20\. Second stress test — the all-up Modular Field Deck (deck-of-decks)

Run against a deliberately harder document: **\[TEMPLATE\] Modular Field Deck — Q2FY27**, 200+ slides. Where the personalization deck was one deck pretending to be a library, this one is genuinely a library of libraries: a Strategic Narrative section, six self-contained first-call decks (Platform, AI, Personalization, Studio, Ecosystem, Vercel), a large Professional Services offerings catalog, and a Learning Services section — each with its own version date and its own internal structure. This is the closest thing yet to what Meta's real corpus will look like, so it's the best gap finder we've run.

## 20.1 Verdict up front

The core three-level context model held again — no slide required a new top-level concept, and the atom / Source Document / relationship spine absorbed everything. But this deck broke the **shape** in three structurally important ways the personalization deck never did: the collection level needs to be **recursive (3–4 levels deep)**, speaker notes turned out to have their **own internal schema** that must itself be atomized, and a whole **non-marketing content domain (priced service offerings)** showed up that doesn't fit the "marketing atom" frame. None are rewrites, but \#1 and \#2 should be decided before Cursor because they change the data model.

## 20.2 Structural finding 1 — the collection level must be recursive

The deck nests at least four levels: the whole field deck → a section (e.g. "Contentful Platform First Call Deck," "Professional Services") → a slide-group within it (e.g. one PS offering's overview \+ scope \+ timeline) → the individual slide → atoms. The "\[TEMPLATE\]" name, the table of contents, the per-section "Latest update" dates, and the explicit assembly instructions ("keep decks under 10 slides," "for net-new prospects highlight Platform \+ Personalization") all confirm it is built to be assembled, not read.

Implication: the deferred `collection`/`section` level from Section 8.4 is not enough as a single tier. Model it as a **self-referencing `collection` entity** (a collection can contain collections) so the hierarchy can be arbitrary depth. Each collection carries its own `internalExternal`, `version`/`lastUpdated`, and audience. This is the single biggest model change the second deck forces.

## 20.3 Structural finding 2 — speaker notes have their own schema

In this deck the notes are not free prose. They are consistently structured into named blocks: **Goal**, **Talk Track**, **Key Points**, **Key Takeaway**, and **Discovery Questions**. That means a single slide's notes are not one context blob — they are several distinct atoms with different roles, audiences, and reuse profiles:

- **Discovery questions** are highly reusable, persona-tagged, and belong to a query/qualification library of their own — arguably the highest-reuse atom in the whole deck.  
- **Talk track** is verbatim presenter script (internal).  
- **Key takeaway** is the one-line conclusion (often a better `semanticSummary` source than the slide body).  
- **Key points** are delivery guidance (internal).

Implication: `slides-atomizer` needs a **notes sub-parser** that detects these labeled blocks and emits each as its own atom with the right `atomType`, rather than dumping notes into one field. This is additive but it materially improves both retrieval (discovery questions become findable) and delivery (talk track can be attached to a generated slide).

## 20.4 Structural finding 3 — gating splits *within* a single slide

Because the slide body is customer-facing but the notes (talk track, key points) are internal-only, one slide now contains **both external and internal atoms**. The atom-level `internalExternal` flag handles this correctly — but only if notes are atomized separately (per 20.3). This actually validates the stricter-wins design: the slide's external body stays retrievable for external decks while its internal coaching never leaks. It also surfaces a parser requirement: the deck signals internal content three different ways — yellow slide backgrounds ("REMOVE YELLOW SLIDES BEFORE SHARING"), explicit text ("Internal Only Slide – Do Not Use"), and NDA banners ("CONFIDENTIAL — SHARED UNDER NDA"). The yellow-background signal is **invisible to a text parser** — a genuine automation crack that must fall back to explicit text cues or human review.

## 20.5 New atom types this deck revealed

Beyond everything from Sections 4 and 8, add (as subtypes of the core set, per the maintainability rule):

- `discovery_question` (reusable, persona-tagged qualification question)  
- `talk_track` (verbatim presenter script — internal)  
- `key_takeaway` and `key_point` (presenter guidance — internal)  
- `offering` / `service_sku` (a named, sellable PS package)  
- `pricing` (amount \+ currency \+ conditions, e.g. "$2,500 for net-new customers," "€63,000 / 12 months," "starts at €5k for one L space")  
- `deliverable` (e.g. "Miro board," "Scope of Work PDF," "session recordings")  
- `engagement_timeline` (week-by-week / session-by-session plan)  
- `comparison` (the Before Contentful / After Contentful transformation grid)  
- `disclaimer` / `legal` (forward-looking-statements, NDA, roadmap disclaimer)  
- `template_slot` (fill-in-the-blank placeholder, e.g. "\[Company Name\] – What We've Heard," "\<What is the business objective…\>")

## 20.6 New relationship types

- `answers` — discovery\_question → the pain\_point / value\_prop it qualifies  
- `guides` — talk\_track / key\_point → the slide it coaches  
- `priced_at` — offering → pricing  
- `delivers` — offering → deliverable  
- `scheduled_as` — offering → engagement\_timeline  
- `transforms` / `before_after` — pairs a "before" state atom with its "after" state atom in comparison grids

## 20.7 New governance states (beyond draft/published)

The deck is full of unfinished and conditional content that must **never** be retrieved for generation:

- Editorial TODOs inside otherwise-real slides: "Need numbers," "\[add in something about testing\]," "\[ADD IN competitive strains\]," "Nascar Logos and ROI or check NASCAR Slides by Industry."  
- Pure template slides with slots and angle-bracket prompts (the customer-facing CBI/"What We've Heard" template).

Implication: add a content state beyond draft/published — a `template` / `incomplete` status (or a `needsContent` flag) that is excluded from retrieval the same way draft is. This is distinct from `[NEEDS REVIEW]` (which flags a field the pipeline couldn't determine); this flags an atom the **author** hasn't finished. Both must gate retrieval.

## 20.8 New content domain — Professional Services as priced SKUs

The PS catalog (Quickstart Basic/Premium/Enterprise, Partner Assurance, Studio/Personalization Quickstart Lite, Audit, Space Architecture, Content Migration, Retainer/Subscription Services, Sitecore Migration) is not marketing content — it's **product/offering data** with pricing, durations, deliverables, and structured timelines. It fits the same atom/relationship machinery, but it argues the model should support **multiple atom families** (a `marketing` family and an `offering` family) sharing the graph, rather than assuming every atom is a marketing message. For the POC this is out of scope, but it's worth naming because Meta's corpus will almost certainly contain non-marketing content (legal, product, enablement) that needs the same treatment.

## 20.9 The deck validates the deck-composer thesis outright

The "How to use this Modular Field Deck" slides literally encode the deck-composer's job: keep assembled decks under 10 slides; for net-new prospects lead with Platform \+ the combined Personalization \+ Studio value; for cross-sell/up-sell lead with the specific product sections the account cares about. These are human-authored **composition rules** we can capture directly as deck-composer logic and as `collection`\-level metadata (audience, journey stage, "lead-with" priority). The source document is telling us how it wants to be reassembled — that's strong confirmation the whole approach is aimed correctly.

## 20.10 Conflicts and freshness at scale

At 200+ slides the dedup/conflict/freshness problems get much louder:

- **Version drift across modules:** integration-partner counts appear as "110+ apps," "140+ apps and data connectors," and "350+ partners" in different sections; "live websites" appears as "\~50,000" while elsewhere the story is "4200 customer stories" and "550K+ active users." These are the same facts at different vintages.  
- **Per-module dates inside one file:** sections are stamped October 2025, November 2025, April 2026, May 2026\. A single retrieval over this file would mix stale and fresh facts. This is the strongest argument yet for **collection-level `lastUpdated` \+ recency-weighted retrieval**, so the engine prefers the freshest module's version of a recurring stat.  
- **Recurring hero stats** (Kraft Heinz 78%, 180B API calls/month, \~30% of the Fortune 500, 99.99% uptime) appear many times across modules — confirming canonical-atom dedup with many references is the right call, now at 10x the scale of the first deck.

## 20.11 Net model changes from the second deck

1. Make `collection` **self-referencing (recursive)** — biggest change.  
2. Add a **notes sub-parser** so Goal / Talk Track / Key Points / Key Takeaway / Discovery Questions each become their own atom.  
3. Add a **`template`/`incomplete` content state** that gates retrieval (distinct from `[NEEDS REVIEW]`).  
4. Add the new subtypes (20.5) and relationship verbs (20.6) to the taxonomy and `relationship-mapper`.  
5. Support **collection-level `internalExternal`, `version`, `lastUpdated`, audience, and "lead-with" priority**; add **recency-weighted retrieval**.  
6. Treat the yellow-background gating signal as an automation gap — parse explicit text cues, else route to human review.  
7. (Production, not POC) Allow **multiple atom families** so non-marketing domains (offerings/pricing, legal, enablement) share the graph.

## 20.12 POC impact — what changes and what doesn't

Keep the POC exactly as scoped in Section 9 — one clean external section, lean model, prove the loop. **Do not** pull the PS catalog, the recursive hierarchy, or the notes sub-schema into v1; they'd reintroduce the "too busy" problem. But make two cheap, forward-compatible choices now so you don't paint into a corner: (a) give the `sourceDocument`/`collection` a nullable `parent` reference from day one (so recursion is possible later without migration), and (b) when the atomizer reads notes, at minimum split out **discovery questions** as their own atoms — they're the highest-reuse thing in the entire corpus and cost almost nothing to capture. Everything else from this section is documented and deferred.

## 20.13 Bottom line

Two very different decks, same result: the three-level context model never broke. What the harder deck changed is the scaffolding around it — recursion in the collection tier, structure inside the speaker notes, a new "unfinished content" gate, and a non-marketing domain on the horizon. You're going into Cursor with the gaps named instead of discovered mid-build, which was the entire point of the stress test.

---

# 21\. The ETL ingestion pipeline (Extract → Transform → Load)

This section makes the ingestion concrete and demo-able. Everything before this defined the *what* (atoms, metadata, skills); this defines the *how it runs*. It is built around the Slides API path (reusing your existing importer) and is scoped so you can show a live ingestion without processing all 200+ slides of the wilf deck.

The mapping to the classic ETL stages, and to the rest of this doc:

- **Extract** \= `parse_slides.py` (Section 15\) \+ a structured speaker-notes parser \+ unfinished-content/collection detectors. Pure deterministic. Output: a clean Intermediate Representation (IR).  
- **Transform** \= the LLM half of `slides-atomizer` \+ `relationship-mapper` \+ `atom-tagger` \+ `image-describer` (Section 11). Output: draft atoms \+ edges \+ review queue, in the exact shape of `eval/example-slide-expected.json` (Section 14.1).  
- **Load** \= write to Contentful via CMA or MCP, idempotent upsert by `atomKey`, everything lands in draft (Sections 6, 14.2).

## 21.1 Design principle: stage-to-disk, never one big run

The single most important MVP decision: **write the output of each stage to disk as JSON, and make each stage read the previous stage's file.** This is what makes the pipeline demo-able and debuggable.

```
pipeline/
  staging/
    01_raw/        # Extract: raw Slides API JSON (one file per deck)
    02_ir/         # Extract: normalized IR (slides + parsed notes + flags)
    03_atoms/      # Transform: draft atoms + edges + review queue
    04_manifest/   # Load: the exact create/upsert batch (dry-run output)
  extract.py
  transform.py
  load.py
  run.py           # orchestrator + scoping
  contentful_client.py
```

Why this matters for the MVP:

- **Inspectable** — you can open `02_ir/` and `03_atoms/` mid-demo and show "here's the slide, here's what we pulled out, here's the atom." That *is* the cool part you want to show.  
- **Cheap re-runs** — re-run Transform without re-hitting the Slides API; re-run Load without re-running the LLM. The expensive stage (LLM Transform) runs once.  
- **Safe Load** — `04_manifest/` is a dry-run artifact. You review exactly what will hit Contentful before anything is written.

## 21.2 Extract — Slides API → Intermediate Representation

Reuses `parse_slides.py` for the raw walk, then adds three wilf-deck-specific parsers the stress test (Section 20\) told us we need: the structured speaker-notes schema, unfinished-content detection, and collection/section detection.

```py
# pipeline/extract.py
"""Extract: Google Slides -> normalized Intermediate Representation (IR).
Deterministic only. No LLM. Reuses scripts/parse_slides.py."""
import json, re, os
from pathlib import Path
# from scripts.parse_slides import parse_deck, detect_internal_external

STAGING = Path(__file__).parent / "staging"

# wilf deck speaker-notes schema (Section 20 finding)
NOTE_SECTIONS = ["Goal", "Talk Track", "Key Points", "Key Takeaway", "Discovery Questions"]
UNFINISHED_CUES = ["need numbers", "[add in", "tbd", "todo", "xx%", "lorem ipsum", "<insert", "placeholder"]
INTERNAL_CUES = ["internal only", "do not use", "[template]", "confidential"]

def parse_structured_notes(notes: str) -> dict:
    """Split a slide's speaker notes into the wilf schema. Each becomes its own atom downstream."""
    if not notes:
        return {}
    out, current = {}, None
    for line in notes.splitlines():
        header = next((s for s in NOTE_SECTIONS if line.strip().lower().startswith(s.lower())), None)
        if header:
            current = header
            out[current] = line.split(":", 1)[1].strip() if ":" in line else ""
        elif current:
            out[current] = (out[current] + "\n" + line).strip()
    return out

def detect_unfinished(text: str) -> bool:
    """Unfinished slides must NEVER be retrieved. Distinct from [NEEDS REVIEW]."""
    low = text.lower()
    return any(cue in low for cue in UNFINISHED_CUES)

def build_ir(parsed_deck: dict) -> dict:
    """parsed_deck = output of parse_slides.parse_deck()."""
    slides_ir = []
    for s in parsed_deck["slides"]:
        joined = " ".join(s["textRuns"])
        slides_ir.append({
            "slideIndex": s["slideIndex"],
            "objectId": s["objectId"],
            "textRuns": s["textRuns"],
            "imageRefs": s["imageRefs"],
            "notes": parse_structured_notes(s["speakerNotes"]),
            "rawNotes": s["speakerNotes"],
            "flags": {
                "unfinished": detect_unfinished(joined + " " + s["speakerNotes"]),
                "internal": any(c in (joined + s["speakerNotes"]).lower() for c in INTERNAL_CUES),
            },
        })
    return {
        "sourceDocId": f"gslides-{parsed_deck['presentationId']}",
        "title": parsed_deck["title"],
        "sourceUrl": f"https://docs.google.com/presentation/d/{parsed_deck['presentationId']}",
        "slides": slides_ir,
    }

def run_extract(presentation_json_path: str, deck_id: str) -> str:
    raw = json.loads(Path(presentation_json_path).read_text())
    ir = build_ir(raw)  # raw must already be parse_deck() output
    out_path = STAGING / "02_ir" / f"{deck_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(ir, indent=2))
    return str(out_path)
```

MVP cut line: collection/section nesting (the recursive deck-of-decks structure) is detected but flattened for v1 — store a `sectionHint` string per slide and defer the real recursive `collection` entity to production (Section 20.12).

## 21.3 Transform — IR → draft atoms

The LLM stage. Deterministic parsing is done; this is where atoms, summaries, fused metrics, and edges get created. Keep the LLM boundaries tight and route everything uncertain to the review queue.

```py
# pipeline/transform.py
"""Transform: IR -> draft atoms + edges + review queue.
Output matches eval/example-slide-expected.json (Section 14.1)."""
import json
from pathlib import Path
# from your_llm_client import complete  # wire your model in Cursor

STAGING = Path(__file__).parent / "staging"

ATOM_PROMPT = """You atomize ONE slide into reusable content atoms.
Rules (non-negotiable):
- One atom = one independently reusable idea (granularity rule).
- A stat is captured WITH its label fused: "87% higher CTR for Ace & Tate", never "87%".
- Speaker-note sections (Goal/Talk Track/Key Points/Key Takeaway/Discovery Questions)
  become SEPARATE atoms. Discovery Questions are high-value, persona-tagged.
- If attribution, persona, or a stat's meaning is unclear -> value "[NEEDS REVIEW]".
- Every atom: atomKey, atomType, subtype?, body, semanticSummary (self-contained), status="draft".
Return JSON: {atoms:[...], edges:[{source,target,relationType}], reviewQueue:[...]}.
Atom types: value_proposition, proof, quote, case_study, image, feature, process_step, cta, insight."""

def transform_slide(slide: dict, source_doc_id: str) -> dict:
    if slide["flags"]["unfinished"]:
        return {"atoms": [], "edges": [], "reviewQueue": [
            {"slideIndex": slide["slideIndex"], "reason": "unfinished content - skipped", "value": "[UNFINISHED]"}]}
    payload = {"slide": slide, "sourceDocument": source_doc_id}
    # raw = complete(system=ATOM_PROMPT, user=json.dumps(payload))
    # return json.loads(raw)
    return {"atoms": [], "edges": [], "reviewQueue": []}  # stub

def run_transform(ir_path: str, deck_id: str, slide_range=None) -> str:
    ir = json.loads(Path(ir_path).read_text())
    slides = ir["slides"]
    if slide_range:
        lo, hi = slide_range
        slides = [s for s in slides if lo <= s["slideIndex"] <= hi]
    atoms, edges, review = [], [], []
    for s in slides:
        r = transform_slide(s, ir["sourceDocId"])
        atoms += r["atoms"]; edges += r["edges"]; review += r["reviewQueue"]
    out = {
        "sourceDocument": {
            "atomKey": ir["sourceDocId"], "title": ir["title"],
            "sourceUrl": ir["sourceUrl"], "sourceDocId": ir["sourceDocId"],
            "internalExternal": "internal" if any(s["flags"]["internal"] for s in slides) else "external",
            "slideOrder": [a["atomKey"] for a in atoms],
        },
        "atoms": atoms, "edges": edges, "reviewQueue": review,
    }
    out_path = STAGING / "03_atoms" / f"{deck_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    return str(out_path)
```

The `atom-tagger` and `image-describer` steps can run as additional passes over `03_atoms/` (read, enrich, write back) — or be folded into the prompt for the MVP. Keep them separate if you want to show the chained-skills story; fold them in if you want fewer moving parts on stage.

## 21.4 Load — atoms → Contentful (CMA or MCP), dry-run first

Load is pluggable on purpose: Transform produces a **load manifest**, and the manifest can be consumed two ways — a scripted CMA client, or the Contentful MCP server driven by the agent in Cursor. Since you're using MCP, the manifest is the clean handoff: the agent reads `04_manifest/` and calls MCP create/upsert tools.

```py
# pipeline/load.py
"""Load: atoms -> Contentful. Dry-run produces a manifest; real load upserts by atomKey.
Idempotent. Everything lands in DRAFT."""
import json
from pathlib import Path

STAGING = Path(__file__).parent / "staging"

def build_manifest(atoms_path: str, deck_id: str) -> str:
    """Produce the exact create/upsert batch WITHOUT writing to Contentful."""
    data = json.loads(Path(atoms_path).read_text())
    ops = []
    # customers / entities first (referenced by atoms)
    for c in data.get("customers", []):
        ops.append({"op": "upsert", "contentType": "customer", "key": c["atomKey"], "fields": c})
    # source document
    ops.append({"op": "upsert", "contentType": "sourceDocument",
                "key": data["sourceDocument"]["sourceDocId"], "fields": data["sourceDocument"]})
    # atoms (images -> upload Asset first, then link)
    for a in data["atoms"]:
        if a["atomType"] == "image" and a.get("asset"):
            ops.append({"op": "uploadAsset", "key": a["asset"], "source": a.get("body")})
        ops.append({"op": "upsert", "contentType": "contentAtom", "key": a["atomKey"],
                    "fields": a, "status": "draft"})
    manifest = {"deck": deck_id, "operationCount": len(ops), "operations": ops}
    out_path = STAGING / "04_manifest" / f"{deck_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2))
    return str(out_path)

def apply_manifest_cma(manifest_path: str, client):
    """Real load via CMA. Idempotent: upsert by atomKey. Never publishes."""
    manifest = json.loads(Path(manifest_path).read_text())
    for op in manifest["operations"]:
        if op["op"] == "uploadAsset":
            client.upload_asset(key=op["key"], source=op["source"])  # implement in contentful_client.py
        else:
            client.upsert_entry(content_type=op["contentType"], key=op["key"],
                                fields=op["fields"])  # creates draft if absent, updates if present
    # NOTE: no publish step. Human-in-the-loop approval publishes later.
```

MCP path (what you'll likely demo): skip `apply_manifest_cma` and instead tell the agent in Cursor: "read `staging/04_manifest/{deck}.json` and execute each operation via the Contentful MCP, creating entries in draft." The manifest is model-agnostic, so the same dry-run output feeds either path.

## 21.5 Orchestrator \+ demo scoping

```py
# pipeline/run.py
"""Orchestrate E -> T -> L with scoping so you don't run all 200 slides."""
import argparse
from extract import run_extract
from transform import run_transform
from load import build_manifest

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--deck-id", required=True)
    p.add_argument("--raw", required=True, help="path to parse_deck() JSON output")
    p.add_argument("--from-slide", type=int, default=0)
    p.add_argument("--to-slide", type=int, default=8)   # default: first ~8 slides
    p.add_argument("--dry-run", action="store_true", default=True)
    args = p.parse_args()

    ir_path = run_extract(args.raw, args.deck_id)
    print(f"[E] IR -> {ir_path}")
    atoms_path = run_transform(ir_path, args.deck_id, slide_range=(args.from_slide, args.to_slide))
    print(f"[T] atoms -> {atoms_path}")
    manifest_path = build_manifest(atoms_path, args.deck_id)
    print(f"[L] manifest (dry-run) -> {manifest_path}")
    print("Review the manifest, then run the MCP/CMA load to write drafts to Contentful.")

if __name__ == "__main__":
    main()
```

For the wilf deck, scope to one coherent first-call deck section (e.g. the Personalization first-call deck, \~8-12 slides) rather than the whole 200\. That gives you the full pipeline — including structured notes, discovery-question atoms, and at least one image — without the runtime or cost of the entire deck-of-decks.

## 21.6 How to demo the ingestion (the runnable narrative)

1. **Show the source** — open the wilf deck to the scoped section.  
2. **Run Extract** — `python pipeline/run.py --deck-id wilf --raw raw.json --from-slide 30 --to-slide 40`. Open `02_ir/wilf.json`: "here's the slide text, the parsed Goal/Talk Track/Discovery Questions, and the unfinished/internal flags."  
3. **Show Transform output** — open `03_atoms/wilf.json`: "the slide became these atoms, each with a self-contained summary, stats fused with labels, discovery questions split out as their own atoms, and edges between them."  
4. **Show the dry-run manifest** — `04_manifest/wilf.json`: "this is exactly what will hit Contentful — nothing written yet."  
5. **Load via MCP** — point the agent at the manifest; watch draft entries appear in Contentful.  
6. **Show the gate** — entries are in draft, not retrievable until approved. Approve one.  
7. **Close the loop** — run `deck-composer` against the approved atoms with a rep query, and show a generated slide that cites the atom keys.

That sequence is the entire thesis, live: a real slide → atoms with preserved context → governed entries → a generated answer.

## 21.7 MVP cut lines (skip these for the demo, document them)

- **Skip** architecture-diagram structured payloads — flag diagram slides `[NEEDS REVIEW]` and move on.  
- **Skip** recursive collection nesting — flatten with a `sectionHint`; add the real `collection` entity in production.  
- **Skip** dedup across slides — accept duplicate stat atoms in v1; dedup by content hash later.  
- **Skip** conflict detection (45% vs 46%) — record both, resolve in production.  
- **Skip** publish/promote — Load always writes draft; human approval is a separate manual step in the demo.  
- **Keep** (non-negotiable even in MVP): stage-to-disk, fused metrics, draft-only load, `[NEEDS REVIEW]` over guessing, unfinished-content skipping, and the dry-run manifest before any write.

## 21.8 One-line framing

Extract is deterministic and reuses what you already built; Transform is the only LLM stage and produces the Section 14 shape; Load is a reviewable manifest that either CMA or MCP can apply as drafts. The staging-to-disk pattern is what turns an abstract pipeline into a thing you can actually show, stage by stage.

---

### 21.9 `pipeline/contentful_client.py` (CMA wrapper stub)

The thin Contentful Management API wrapper the Load stage calls when running the **scripted CMA path** (`apply_manifest_cma` in 21.4). If you go MCP-first in Cursor, you can ignore this file — the agent executes the same manifest operations through the Contentful MCP tools. It's here so the Load stage compiles end-to-end without the MCP, and so the demo can fall back to a pure-Python run if the MCP isn't wired yet.

Design rules baked in:

- **Idempotent by `atomKey`.** Every entry carries a stable `atomKey`; upsert looks it up first and updates in place rather than creating duplicates. Safe to re-run the whole pipeline.  
- **Draft by default.** Nothing is published. Entries are created/updated and left unpublished so the human-in-the-loop gate stays intact. A separate, explicit `publish` is out of MVP scope.  
- **Assets deduped by content hash.** The same screenshot recurs across slides; upload looks up an existing asset by a `sha256` tag before uploading a new binary.  
- **Locale-wrapped fields.** The CMA expects `{fieldId: {locale: value}}`; the wrapper handles that so the manifest can stay flat.

```py
"""contentful_client.py — minimal CMA wrapper for the Load stage.

Idempotent upsert by atomKey, asset upload deduped by content hash, draft-only.
Wire your own CMA token / space / environment via env vars. This is an MVP stub:
no retry/backoff, no rate-limit handling, no rich-text conversion — add in Cursor.
"""
import os
import hashlib
from typing import Any

# import contentful_management  # pip install contentful-management

DEFAULT_LOCALE = os.environ.get("CTFL_LOCALE", "en-US")


class ContentfulClient:
    def __init__(self, space_id: str | None = None, environment_id: str | None = None,
                 cma_token: str | None = None, locale: str = DEFAULT_LOCALE):
        self.space_id = space_id or os.environ["CTFL_SPACE_ID"]
        self.environment_id = environment_id or os.environ.get("CTFL_ENVIRONMENT_ID", "master")
        self.cma_token = cma_token or os.environ["CTFL_CMA_TOKEN"]
        self.locale = locale
        # self._client = contentful_management.Client(self.cma_token)
        # self._env = self._client.environments(self.space_id).find(self.environment_id)
        self._env = None  # wire in Cursor

    # --- helpers -----------------------------------------------------------
    def _wrap(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Flat {fieldId: value} -> CMA {fieldId: {locale: value}}."""
        return {k: {self.locale: v} for k, v in fields.items() if v is not None}

    def _find_by_atom_key(self, content_type: str, atom_key: str):
        """Look up an entry by its stable atomKey. Returns the entry or None."""
        # entries = self._env.entries().all({
        #     "content_type": content_type,
        #     "fields.atomKey": atom_key,
        #     "limit": 1,
        # })
        # return entries[0] if len(entries) else None
        return None  # wire in Cursor

    @staticmethod
    def _hash_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # --- entries -----------------------------------------------------------
    def upsert_entry(self, content_type: str, atom_key: str,
                     fields: dict[str, Any]) -> dict[str, Any]:
        """Create or update an entry, keyed on atomKey. Leaves it in DRAFT.

        Returns {"id", "action", "atomKey"} where action is created|updated.
        """
        fields = {**fields, "atomKey": atom_key}
        existing = self._find_by_atom_key(content_type, atom_key)
        wrapped = self._wrap(fields)

        if existing is not None:
            # for field_id, value in wrapped.items():
            #     setattr(existing.fields(self.locale), field_id, value[self.locale])
            # existing.save()  # save() does NOT publish
            return {"id": getattr(existing, "id", "?"), "action": "updated", "atomKey": atom_key}

        # entry = self._env.entries().create(None, {
        #     "content_type_id": content_type,
        #     "fields": wrapped,
        # })
        # return {"id": entry.id, "action": "created", "atomKey": atom_key}
        return {"id": "<new>", "action": "created", "atomKey": atom_key}

    def link(self, entry_id: str) -> dict[str, Any]:
        """Build a CMA link object for reference fields (relatedTo, attributedTo)."""
        return {"sys": {"type": "Link", "linkType": "Entry", "id": entry_id}}

    def asset_link(self, asset_id: str) -> dict[str, Any]:
        return {"sys": {"type": "Link", "linkType": "Asset", "id": asset_id}}

    # --- assets ------------------------------------------------------------
    def upload_asset(self, file_path: str, title: str,
                     description: str = "") -> dict[str, Any]:
        """Upload a binary as a Contentful Asset, deduped by content hash.

        Returns {"id", "action", "hash"}. Leaves the asset in DRAFT.
        The wrapper image atom links to this asset via its `asset` field.
        """
        content_hash = self._hash_file(file_path)
        existing = self._find_asset_by_hash(content_hash)
        if existing is not None:
            return {"id": getattr(existing, "id", "?"), "action": "reused", "hash": content_hash}

        # upload = self._env.uploads().create(file_path)
        # asset = self._env.assets().create(None, {
        #     "fields": self._wrap({
        #         "title": title,
        #         "description": description,
        #     }) | {"file": {self.locale: {
        #         "contentType": _guess_mime(file_path),
        #         "fileName": os.path.basename(file_path),
        #         "uploadFrom": {"sys": {"type": "Link", "linkType": "Upload", "id": upload.id}},
        #     }}},
        # })
        # asset.process()              # process the binary (does NOT publish)
        # asset.metadata tag: sha256 = content_hash  (for future dedup lookup)
        return {"id": "<new-asset>", "action": "uploaded", "hash": content_hash}

    def _find_asset_by_hash(self, content_hash: str):
        # assets = self._env.assets().all({"metadata.tags.sys.id[in]": f"sha256-{content_hash}"})
        # return assets[0] if len(assets) else None
        return None  # wire in Cursor


def _guess_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".svg": "image/svg+xml", ".pdf": "application/pdf",
    }.get(ext, "application/octet-stream")


if __name__ == "__main__":
    # Smoke test (no network): exercises hashing + link/wrap helpers only.
    client = ContentfulClient(space_id="demo", cma_token="demo")
    print(client.link("entry-123"))
    print(client.asset_link("asset-123"))
    print(client._wrap({"title": "Hello", "skip": None}))
```

How the manifest applier (21.4) uses it — the order matters because references must resolve:

1. **Assets first** — `upload_asset` for each image binary; capture the returned asset id, keyed by the atom's `asset` placeholder.  
2. **Customers / entities next** — `upsert_entry("customer", …)`; capture ids so stats can link to them.  
3. **Atoms** — `upsert_entry("contentAtom", …)`, resolving `attributedTo` to the customer id and leaving `relatedTo` placeholders for the next pass.  
4. **Relationship pass** — once all atoms exist and have ids, update each atom's `relatedTo` with real `link()` objects (you can't link to an entry that doesn't exist yet).  
5. **Source Document last** — `upsert_entry("sourceDocument", …)` with its `atoms` array of links and `slideOrder` resolved to real ids.

This two-pass ordering (create, then wire relationships) is the one thing worth getting right even in the MVP — it's the same reason the manifest separates `entries` from `edges`. Everything stays in draft throughout, so the human-in-the-loop gate is never bypassed.

---

# 22\. What's not yet covered (the road beyond ingestion)

The doc takes you from content-model design through ETL ingestion. Everything below is **deliberately deferred** — named here so the boundaries are honest and the next phase is obvious. Ordered by how much each blocks the demo payoff.

## 22.1 Retrieval & embedding layer (the biggest open gap)

The whole system's value is retrieval, but the doc only says "vectorize for semantic retrieval." Contentful is not natively a vector store, so this is a real architecture decision, not an implementation detail. `deck-composer` *assumes* a semantic index \+ knowledge graph exists that nothing in the pipeline currently builds.

Options to decide between:

- **Contentful-native semantic / AI features** — least moving parts, keeps everything in one governed system; verify it covers hybrid (keyword \+ taxonomy filter \+ vector) at the needed scale.  
- **External vector DB** (Pinecone/Weaviate/pgvector) — most control, adds the re-embedding/sync burden the methodology warned about; the `change-propagator` re-vectorize hook is where it plugs in.  
- **Solr / OpenSearch** (your instinct) — strong for the keyword \+ taxonomy-facet half, with a vector plugin for the semantic half; good for a *testable* search demo over the two example decks specifically.

MVP recommendation: pick the lowest-friction path that supports **taxonomy filter \+ semantic similarity together**, and treat the index as a derived artifact rebuilt from the governed atoms (never the source of truth).

## 22.2 The generate-slides loop (closing the original Meta ask)

Meta's ask was "the engine generates slides." We built the retrieval half — `deck-composer` outputs an assembled slide spec \+ citations — but the **rendering** half is unspecified: atoms → an actual deliverable. Decide the output target:

- **JSON slide outline** (easiest; pairs with the existing `.slides` workflow) — good enough to prove the loop.  
- **Back to Google Slides** via the importer run in reverse (most impressive; reuses tooling you already have).  
- **PPTX** (portable; no live dependency).

This is the literal closing of the loop and the most demo-able "wow" once retrieval works. MVP: JSON outline first, then wire the Google Slides round-trip if time allows.

## 22.3 Human review workflow (operationalizing the non-negotiable)

"Human approves before retrievable" and the `[NEEDS REVIEW]` queue appear throughout but have no surface. Make it concrete:

- Use **Contentful native workflows / tasks** to move atoms draft → in-review → approved, with the `[NEEDS REVIEW]` items as assigned tasks.  
- A lightweight **Content Preview** app (your idea) doubles as the reviewer's surface and a debug view — render an atom \+ its relationships \+ provenance so a human can approve or kick back in one screen. This is what makes the governance story real in front of a stakeholder, not just asserted.

## 22.4 Output-side evaluation (answers open question \#11)

There's a regression anchor for the *atomizer* (`eval/example-slide-expected.json`) but nothing for the *delivery* side. Add a golden set:

- `eval/golden-queries.json` — a handful of rep queries → the atoms a correct answer should retrieve (and the ones it must NOT, e.g. internal\_experiment proof on an external query).  
- Metrics: retrieval precision/recall on the golden set, plus a manual "is the assembled slide coherent?" pass. This turns "does it work?" from opinion into a number, which is exactly what open question \#11 needs before scaling.

## 22.5 Cross-cutting smaller gaps

- **Access control** — internal/external is modeled at the data layer, but not *who can query the chatbot* or role-based retrieval. Matters for Meta; defer the mechanism, note the requirement.  
- **Transform cost/token budget** — Transform is the LLM stage; over 200+ slides it needs batching, rate-limit handling, and a rough cost estimate. Fine to ignore for an 8–12 slide MVP slice; don't ignore at full-deck scale.  
- **Pipeline observability** — staging-to-disk gives inspectability, but add a per-run log (pipeline version \+ timestamp \+ slide range \+ counts) so you can tell which run produced which atoms. The atom-level `method/version` provenance is the hook.  
- **Taxonomy bootstrapping** — the 30K-term scheme is referenced but its loading path isn't. For the MVP the `taxonomy/scheme.json` seed is enough; production needs an import \+ stable-ID strategy (ties to open question \#9).

## 22.6 Suggested sequence after ingestion

1. **Content Preview app** — review surface \+ debug view (unblocks human-in-the-loop and makes ingestion *visible*).  
2. **Retrieval index** (Solr / vector) over the two example decks — proves search works on real atoms.  
3. **deck-composer end-to-end** — query → retrieve → assemble → cite.  
4. **Generate-slides rendering** — close the loop back to a real deck.  
5. **Golden-query eval** — put a number on "it works."

This is the phase that turns a populated content model into the actual demo Meta asked for.

---

# 23\. Contentful as the context & data store (context-as-content)

This is the capstone. Everything so far treats Contentful as the store for the **output** — the atoms. The bigger idea: Contentful also stores the **context that governs how atoms are produced, tagged, and assembled**. Tone, brand voice, project brief, ideal-customer profile, competitive positioning, glossary, messaging pillars, compliance guardrails — all as first-class, governed, versioned entries, not as a prompt buried in a script or a doc in someone's drive.

This is the Section 7 "knowledge-as-code" pattern finally realized as actual content. The payoff in one line: **prompt engineering becomes content modeling** — versioned, permissioned, collaborative, and auto-propagating.

## 23.1 Why this changes the system

- **Context becomes governed, versioned, permissioned — exactly like atoms.** Brand voice, tone, do's-and-don'ts, ICP, positioning all live as entries with the same draft→approved gate and reversible revision history. No more context that lives in one person's head or a stale doc.  
- **Single-source-of-truth, single-update-propagates.** Change the tone guide once, and every future atomization run, every AI Action, and every generation respects it. The same re-use story as atoms, now for the rules that govern them.  
- **The importer AND the MCP both read context from Contentful at runtime.** Whether you ingest via the Slides importer or operate via the MCP in Cursor, you have a rich, current, approved context set sitting right next to the content — so processing happens faster and more consistently at scale.  
- **Governance for free (your point).** Contentful's roles and permissions mean different teams own different context: brand team edits `brand_voice`, product marketing owns `competitive_positioning`, legal owns `compliance_guardrail` — everyone else read-only. Environments let you test new context in sandbox before it goes live. None of this is something you build; it's native.

## 23.2 The context content type

A single `projectContext` type covers the POC. Format is markdown or JSON so it's both human-editable and machine-consumable.

```json
// model/projectContext.json
{
  "name": "Project Context",
  "id": "projectContext",
  "fields": [
    {"id": "contextKey", "type": "Symbol", "required": true, "unique": true},
    {"id": "contextType", "type": "Symbol", "required": true, "validations": [{"in": ["brand_voice", "tone_guide", "project_brief", "icp", "competitive_positioning", "compliance_guardrail", "glossary", "messaging_pillar", "style_rules"]}]},
    {"id": "format", "type": "Symbol", "validations": [{"in": ["markdown", "json"]}], "default": "markdown"},
    {"id": "body", "type": "Text", "required": true},
    {"id": "scope", "type": "Symbol", "validations": [{"in": ["space", "collection", "project", "source_document"]}], "default": "space"},
    {"id": "appliesTo", "type": "Array", "items": {"type": "Link", "linkType": "Entry"}},
    {"id": "precedence", "type": "Integer", "default": 0},
    {"id": "status", "type": "Symbol", "validations": [{"in": ["draft", "published"]}], "default": "draft"}
  ]
}
```

- **`scope` \+ `appliesTo`** implement progressive disclosure as data: `space`\-scoped context is always loaded (the "index"); `collection`/`project`/`source_document`\-scoped context loads only when relevant to what's being processed. This is Section 7's always-loaded-index \+ on-demand-detail pattern, now driven by content, not code.  
- **`precedence`** resolves conflicts deterministically: a project-level tone override beats the space-wide default (higher precedence wins). No silent guessing.  
- **`status`** gates context the same way it gates atoms — only approved context conditions a production run; draft context can be tested in a sandbox environment first.

## 23.3 How it threads into the pipeline

Only the **Transform** stage changes — and only at the front. Before extracting atoms from a deck, the pipeline loads the applicable context (space-wide always, plus anything scoped to the deck's collection/project), assembles it by precedence, and conditions the LLM step on it. So `semanticSummary` tone, `atomType` classification hints, and even taxonomy tagging are all grounded in the project's actual, approved context.

```py
# transform.py — front of the LLM stage
def load_context(client, collection_key=None, project_key=None):
    """Fetch applicable projectContext entries, ordered by precedence (low->high)."""
    scopes = ["space"]
    if collection_key: scopes.append(("collection", collection_key))
    if project_key: scopes.append(("project", project_key))
    entries = client.fetch_published("projectContext", scopes=scopes)  # status=published only
    entries.sort(key=lambda e: e["precedence"])  # higher precedence applied last = wins
    return entries

def build_system_prompt(base_prompt, context_entries):
    blocks = []
    for c in context_entries:
        blocks.append(f"## {c['contextType']} ({c['scope']})\n{c['body']}")
    return base_prompt + "\n\n# Project context (governs tone, semantics, tagging)\n" + "\n\n".join(blocks)
```

The importer and the MCP both call the same `load_context` surface, so context is consistent no matter how content enters. Nothing in Extract or Load changes.

## 23.4 The resolved build/buy boundary

This section also settles open question \#10 (the engine boundary). With context-as-content, the line is clean:

- **Contentful owns everything up to and including the governed, queryable layer** — atoms, relationships, taxonomy, AND the context that governs them. This is the single store for both the content and the rules for using it.  
- **Meta owns the AI engine, generation, and orchestration** on top — retrieval at query time, slide generation, and the chatbot.

The Content Preview and the Solr/search index become *illustrative proof points* of what the handoff surface can do — "here's what the atoms and context look like when queried" — not production commitments. Meta builds the post-ingestion engine; Contentful proves the layer it sits on.

## 23.5 POC framing

For the demo, seed two or three `projectContext` entries — a `brand_voice`, a `tone_guide`, and one `project_brief` for the wilf or personalization deck — and show the same slide atomized **with and without** context loaded. The difference in `semanticSummary` tone and tagging is the whole point, visible in one side-by-side. Then change the tone entry once and re-run to show propagation. Defer multi-type context libraries, per-locale context, and fine-grained precedence chains to production — the single type with `scope` \+ `precedence` is enough to prove it.

---

## Sources

- [\[TEMPLATE\] Contentful Personalization | Modular Field Deck | Q2FY27](https://docs.google.com/presentation/d/1lDdGqlqRABuSBfv5eW79aXlT3oIKiFeF5DPdLJzRDmw)  
- [\[TEMPLATE\] Modular Field Deck — Q2FY27 (all-up: Strategic Narrative, Platform, AI, Personalization, Studio, Ecosystem, Vercel, Professional Services, Learning Services)](https://docs.google.com/presentation/d/19T0y_dW9_yd1e-PJ_NfUT0naZEroJ5CALJTRIT2cdY8)

