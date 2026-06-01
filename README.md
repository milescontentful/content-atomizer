# Content Atomization POC

> **Implementation reference for Contentful teams.**  
> Breaks a Google Slides deck into reusable, AI-ready content atoms and loads them into Contentful as draft entries — no LLM API key required.

---

## What this builds

```
Google Slides deck
      │
      ▼
 exportForAtomization()          ← Google Apps Script (in-presentation)
 tools/export-for-atomization.gs
      │  staging/01_raw/{deck}.json
      ▼
 npm run extract -- --deck {id}  ← TypeScript (pipeline/extract.ts)
      │  staging/02_ir/{deck}.json   (normalized IR: text runs, notes, flags)
      ▼
 python pipeline/run.py --apply  ← Python (pipeline/transform.py + load.py)
      │  staging/03_atoms/{deck}.json  (atoms + customers + edges)
      │  staging/04_manifest/{deck}.json  (dry-run preview before writing)
      ▼
 Contentful (draft entries)
   ├── sourceDocument  (1 per deck)
   ├── contentAtom     (N per deck — value_props, proofs, process_steps, …)
   └── customer        (deduplicated across the deck)
```

### Content model (space `ce81lr6pgre8`)

| Content type | Key field | Purpose |
|---|---|---|
| `sourceDocument` | `sourceDocId` | Deck parent; holds slide order |
| `contentAtom` | `atomKey` | One reusable idea (body + semanticSummary) |
| `customer` | `atomKey` | Customer reference for proof attribution |
| `projectContext` | `contextKey` | Brand voice, ICP, guardrails for AI generation |

All atoms land in **DRAFT**. A human publishes them in the Contentful UI after review.

---

## Quick start

### Prerequisites

- Node.js 18+ and Python 3.9+
- A Contentful space with the 4 content types published (see `model/`)
- A Contentful CMA token for the space

### 1. Install dependencies

```bash
npm install
pip install -r requirements.txt
```

### 2. Configure `.env`

```bash
cp .env.example .env
# Fill in:
#   CTFL_SPACE_ID=<your space id>
#   CTFL_CMA_TOKEN=<your CMA token>
#   CTFL_ENVIRONMENT_ID=master
```

### 3. Export a deck from Google Slides

Open the target deck → **Extensions → Apps Script** → create a new script file → paste `tools/export-for-atomization.gs` → run `exportForAtomization`.

Download the JSON file from the Drive dialog and save it:
```
pipeline/staging/01_raw/<deck-id>.json
```

### 4. Run the pipeline

```bash
# Extract: raw JSON → normalized IR
npm run extract -- --deck <deck-id>

# Transform + Load dry-run (no network writes)
python3 pipeline/run.py --deck-id <deck-id>

# Review staging/04_manifest/<deck-id>.json, then apply:
python3 pipeline/run.py --deck-id <deck-id> --apply
```

Scope to a slide range during development:
```bash
python3 pipeline/run.py --deck-id <deck-id> --from-slide 1 --to-slide 8 --apply
```

---

## Transform modes

| Mode | Command | What it does |
|---|---|---|
| `smart` **(default)** | `--mode smart` | Stat fusion, process-step detection, customer attribution, `contains` edges. No LLM. |
| `coarse` | `--mode coarse` | 1 slide → 1 atom. Fastest way to prove the Load pipeline works. |
| `llm` | `--mode llm` | Calls an LLM API. Wire `LLM_API_KEY` + `LLM_MODEL` in `.env`. |
| agent *(skip)* | `--skip-transform` | Loads a pre-written `staging/03_atoms/` file. Use with the agent-as-LLM pattern below. |

### Agent-as-LLM pattern (no API key needed)

The `skills/` directory contains Cursor agent skills. Invoke them in the Cursor chat to produce quality atoms without an external LLM key:

```
You (in Cursor chat):
  "Run the slides-atomizer skill on staging/02_ir/my-deck.json, slides 3–8"

Agent writes staging/03_atoms/my-deck.json

You:
  python3 pipeline/run.py --deck-id my-deck --skip-transform --apply
```

| Skill | When to use |
|---|---|
| `slides-atomizer` | Primary extraction: splits slides into named, typed atoms |
| `relationship-mapper` | Wires `proves`/`illustrates`/`contains` native reference fields |
| `atom-tagger` | Applies Contentful org taxonomy via `metadata.concepts` |
| `image-describer` | Generates semantic summaries for image atoms |
| `deck-composer` | Retrieves atoms and assembles a new deck (generation side) |
| `change-propagator` | Re-syncs when the source deck changes |

---

## Pipeline stages in detail

### Extract (`pipeline/extract.ts`)

Reads the GAS export JSON and normalizes it:
- Parses structured speaker notes (`Goal:`, `Talk Track:`, `Discovery Questions:`)
- Detects unfinished content (`tbd`, `[add in`, `xx%`, …) → skip flag
- Detects internal-only content → `authorState: incomplete`
- Emits ordered `textRuns[]` per slide

### Smart Transform (`pipeline/transform.py`)

**Stat fusion** — two patterns handled deterministically:
- *Pattern A* (stat → label): `"70%"` + `"of marketers say..."` → `"70% of marketers say..."` *(unambiguous)*
- *Pattern B* (label-block → stat-block of equal size): visual-layout slides where N labels precede N stats → flagged in review queue for human verification

**Process steps** — `"1. Discover visitors"` → `process_step` atom with `next` edge to step 2.

**Customer attribution** — `"87% higher CTR for Ace & Tate"` → `proof` atom with `attributedTo: customer-ace-tate` + a `customer` entry.

**`contains` edges** — parent value-prop atom references its child proof/step atoms via the native `contains` reference field.

### Load (`pipeline/load.py` + `pipeline/contentful_client.py`)

Two-pass CMA write (resolves forward references):
1. **Pass 1** — create all entries without relationship fields; builds `atomKey → entryId` map
2. **Pass 2** — patch relationship fields (`contains`, `attributedTo`, `proves`, …) with resolved link objects

Idempotent: re-running upserts by the content type's unique key (`atomKey` / `sourceDocId` / `contextKey`). Never publishes.

---

## Build phases

| Phase | Status | What was built |
|---|---|---|
| 0 — Scaffold | ✅ | Repo, config, model stubs, 7 skills, pipeline stubs |
| 1 — Content model | ✅ | 4 content types published in Contentful (`sourceDocument`, `contentAtom`, `customer`, `projectContext`) |
| 2 — Extract + Load | ✅ | Full E→T→L pipeline; smart transform; idempotent CMA upsert |
| 3 — LLM Transform | 🔜 | Wire `transform_slide_llm()` or use agent-as-LLM pattern |
| 4 — Enrich & govern | 🔜 | `atom-tagger`, `relationship-mapper`, image ingestion, review queue UI |
| 5 — Retrieval & compose | 🔜 | Vector/hybrid search, `deck-composer`, `change-propagator` |

---

## Repository structure

```
content-atomization-poc/
├── docs/
│   ├── master-build-doc.md   # Full methodology and data contracts
│   ├── build-plan.md         # Phase-by-phase build order
│   └── plan-content-atomization-poc.md
├── model/                    # Contentful content type definitions (JSON)
├── pipeline/
│   ├── extract.ts            # TypeScript: GAS JSON → IR
│   ├── transform.py          # Python: IR → atoms (smart/coarse/llm modes)
│   ├── load.py               # Python: atoms → CMA manifest + upsert
│   ├── contentful_client.py  # Python: CMA SDK wrapper
│   ├── run.py                # Python: CLI orchestrator
│   └── staging/
│       ├── 01_raw/           # GAS export input (gitignored)
│       ├── 02_ir/            # Normalized IR (gitignored)
│       ├── 03_atoms/         # Transform output (gitignored)
│       └── 04_manifest/      # Dry-run manifest (gitignored)
├── skills/                   # Cursor agent skills (slides-atomizer, etc.)
├── tools/
│   └── export-for-atomization.gs   # Self-contained GAS script (paste into any deck)
├── eval/
│   └── example-slide-expected.json # Regression anchor for Phase 3
├── taxonomy/                 # Contentful org taxonomy reference
├── requirements.txt          # Python deps (contentful-management)
└── package.json              # Node deps (tsx, typescript, vitest, eslint)
```

---

## Key design decisions

1. **No LLM key required for the POC.** The `smart` transform mode handles 80% of slides deterministically. The Cursor agent skills handle the rest.

2. **Draft-only by design.** Nothing is published without a human approval step in the Contentful UI.

3. **Idempotent.** Re-running the pipeline updates existing entries rather than creating duplicates.

4. **Staging files are gitignored.** The `pipeline/staging/` JSON files contain slide content and are not committed. Only the code is versioned.

5. **Two-pass CMA load.** Resolves forward references without requiring a specific atom ordering.

6. **Agent-as-LLM.** For slides that need semantic judgment (multi-idea slides, ambiguous attributions), the Cursor agent applies the `slides-atomizer` skill rules and writes the atoms file directly — no API key needed.

---

## Contributing / extending

- **New slide patterns**: add detection logic to `_fuse_stat_pairs()` in `transform.py`
- **New atom types**: extend `_SLIDE_TYPE_TO_ATOM_TYPE` and update `model/contentAtom.json`
- **New pipeline stages**: follow the JSON-on-disk handoff pattern — each stage reads from one `staging/` folder and writes to the next
- **LLM integration**: implement `transform_slide_llm()` in `transform.py`; the rest of the pipeline is already wired
