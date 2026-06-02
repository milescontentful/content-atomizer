"""Transform: IR -> draft atoms + edges + review queue.

Three modes
-----------
  smart   (default)  Geometry-aware: uses shapes[].top/left from the IR to
                     correctly associate stat numbers with their labels within
                     the same visual card. Falls back to Pattern-A only when
                     geometry is absent. Ambiguous pairings → [NEEDS REVIEW].
  coarse             1 slide → 1 atom. Fastest way to prove the Load pipeline.
  llm                LLM extraction per ATOM_PROMPT. Wire LLM_API_KEY.

Agent-as-LLM pattern (recommended for POC without an LLM key)
-------------------------------------------------------------
  The slides-atomizer skill in skills/ runs inside the Cursor agent chat.
  Invoke it there, let the agent write staging/03_atoms/{deck}.json, then:
    python pipeline/run.py --deck-id <id> --skip-transform --apply
  --skip-transform bypasses this module and loads whatever atoms are on disk.
  This is the source-of-truth path for multi-idea slides requiring judgment.

Stat fusion non-negotiable (Section 9.1)
-----------------------------------------
  A number without its label is NEVER its own atom.
  "87%" alone is dead; "87% higher CTR for Ace & Tate" is reusable.

  Two fusion strategies in order of preference:

  1. Geometry-aware card detection (when shapes[] present — GAS v2 export):
     Shapes are grouped into vertical "card columns" by left position
     (|left_A - left_B| < COL_THRESHOLD). Within each column, a lone stat
     line is fused with the label line(s) in the same column. This correctly
     handles slides where labels and stats are in separate shape boxes
     (e.g. label at top, big number below, or 3-column stat-card layout).
     Ambiguous columns (multiple stats) → [NEEDS REVIEW].

  2. Pattern A — textRuns fallback (when shapes[] absent — old GAS export):
     A bare stat run immediately followed by a non-stat run in textRuns[].
     DOM order makes the pairing unambiguous for this specific pattern.

  Pattern B (index-based: N labels then N stats, paired by position) has
  been REMOVED. It was the root cause of the proof-slide misattributions
  (Ruggable=87%, Ace&Tate=78%, KraftHeinz=<30min — all three wrong).

Output shape matches model/contentAtom.json:
  - no 'status' field (native publish state gates retrieval)
  - 'authorState' enum: complete | incomplete | template
  - native relationship fields (proves / illustrates / contains)
  - 'metric' for stat atoms (stat + label FUSED, never bare number)
"""
import json
import re
from pathlib import Path
from typing import Literal, Optional, Tuple

STAGING = Path(__file__).parent / "staging"

# Geometry thresholds for card-column grouping (points, Google Slides coordinate space).
# Within a stat card, a number and its label are typically aligned within ~15pt.
# Adjacent columns in a 3-column layout have gaps of 50–200pt.
# 20pt is tight enough to separate neighbouring columns (observed min gap: 23pt)
# while still grouping stat + label within the same card (max within-card offset: ~11pt).
COL_THRESHOLD = 20

# ─── LLM prompt (Phase 3) ────────────────────────────────────────────────────

ATOM_PROMPT = """You atomize ONE slide into reusable content atoms.
Rules (non-negotiable):
- One atom = one independently reusable idea (granularity rule).
- A stat is captured WITH its label fused: "87% higher CTR for Ace & Tate", never "87%".
- Speaker-note sections (Goal/Talk Track/Key Points/Key Takeaway/Discovery Questions)
  become SEPARATE atoms. Discovery Questions are high-value, persona-tagged.
- If attribution, persona, or a stat's meaning is unclear → value "[NEEDS REVIEW]".
- Every atom: atomKey, atomType, subtype?, body, semanticSummary (self-contained),
  authorState="complete".
Return JSON: {atoms:[...], edges:[{source,target,relationType}], reviewQueue:[...]}.
Atom types: value_proposition, proof, quote, case_study, image, feature, process_step,
            cta, insight"""

# ─── Slide type → atom type (coarse + smart modes) ───────────────────────────

_SLIDE_TYPE_TO_ATOM_TYPE: dict = {
    "statistics":    "proof",
    "case-study":    "case_study",
    "quote":         "quote",
    "image-full":    "image",
    "title-slide":   "value_proposition",
    "section-break": "value_proposition",
    "body":          "value_proposition",
}


def _atom_type_from_slide(slide: dict) -> str:
    return _SLIDE_TYPE_TO_ATOM_TYPE.get(slide.get("slideType", "body"), "value_proposition")


# ─── Smart mode: stat detection and fusion ────────────────────────────────────

# A "bare stat": a standalone number/percentage with no surrounding context.
# Examples: "70%", "87%", "3x", "<30min", "43%"
_BARE_STAT = re.compile(r'^[<>≥≤]?\s*\d+\.?\d*\s*[%xkKmMbBs+]?\s*(?:min|hr|hrs|days?)?\s*$', re.IGNORECASE)

# Numbered process step: "1. Discover visitors"
_NUMBERED_STEP = re.compile(r'^(\d+)\.\s+(.+)$')

# Customer attribution in a fused metric: "for Ace & Tate", "by Kraft Heinz"
# No IGNORECASE — company names must start with a capital letter so we don't
# match function words like "their", "our", "the", etc.
_CUSTOMER_ATTR = re.compile(
    r'\b(?:for|by)\s+([A-Z][A-Za-z&\s\.\-]+?)(?:\s+to\s+|\s+in\s+|\s*$)'
)


def _is_bare_stat(text: str) -> bool:
    return bool(_BARE_STAT.match(text.strip()))


def _fuse_stat_pairs(runs: list) -> Tuple[list, list]:
    """Scan textRuns and fuse bare-stat lines with their labels (Pattern A only).

    Pattern A (stat immediately followed by label in textRuns):
      "70%\\nof marketers say..." → "70% of marketers say..."
      Unambiguous because DOM order makes the adjacency clear.

    Pattern B (index-based: N labels then N stats) has been REMOVED.
    It produced wrong attributions on the proof slide because DOM reading
    order differs from visual left-to-right layout order.

    Use _fuse_stat_cards_geometry() when shapes[] geometry is available —
    it correctly groups stats with labels by visual card column.

    Returns (items, review_items):
      items: list of {'kind': 'stat'|'step'|'text', 'text': str, ...}
      review_items: list of {'reason': str, ...}
    """
    result = []
    review: list = []
    i = 0
    n = len(runs)

    while i < n:
        text = runs[i].strip()
        if not text:
            i += 1
            continue

        # Pattern A: stat immediately followed by a non-stat label (unambiguous)
        if _is_bare_stat(text) and i + 1 < n and not _is_bare_stat(runs[i + 1]):
            metric = f"{text} {runs[i + 1].strip()}"
            result.append({"kind": "stat", "text": metric, "metric": metric})
            i += 2
            continue

        # Bare stat with no immediately following label → flag, never guess
        if _is_bare_stat(text):
            marker = f"{text} [NEEDS REVIEW]"
            result.append({"kind": "stat", "text": marker, "metric": marker})
            review.append({
                "reason": (
                    f"Bare stat '{text}' has no immediately following label in textRuns. "
                    "Re-export with GAS v2 for geometry-aware fusion, or review manually."
                ),
                "stat": text,
            })
            i += 1
            continue

        # Numbered process step
        m = _NUMBERED_STEP.match(text)
        if m:
            step_num = int(m.group(1))
            step_label = m.group(2)
            desc = ""
            if i + 1 < n and not _is_bare_stat(runs[i + 1]) and not _NUMBERED_STEP.match(runs[i + 1]):
                desc = runs[i + 1].strip()
                i += 1
            full = f"{step_label}\n{desc}".strip() if desc else step_label
            result.append({"kind": "step", "text": full, "step_num": step_num})
            i += 1
            continue

        result.append({"kind": "text", "text": text})
        i += 1

    return result, review


def _group_shapes_by_column(shapes: list) -> list:
    """Group shapes into visual card columns by left position.

    Two shapes are in the same column when |left_A - left_B| < COL_THRESHOLD.
    Each column is sorted top-to-bottom. Columns are returned left-to-right.
    """
    if not shapes:
        return []

    sorted_shapes = sorted(shapes, key=lambda s: s.get("left", 0))
    columns: list = []

    for shape in sorted_shapes:
        shape_left = shape.get("left", 0)
        placed = False
        for col in columns:
            rep_left = col[0].get("left", 0)
            if abs(shape_left - rep_left) < COL_THRESHOLD:
                col.append(shape)
                placed = True
                break
        if not placed:
            columns.append([shape])

    for col in columns:
        col.sort(key=lambda s: s.get("top", 0))

    return columns


def _fuse_stat_cards_geometry(shapes: list) -> Tuple[list, list]:
    """Geometry-aware stat + label fusion using shapes[] bounding boxes.

    Groups shapes into visual card columns (by left position) then associates
    each bare stat with the label line(s) in the same column. This is the
    correct approach for stat-card slides where the label and number are in
    separate visual boxes.

    Ambiguous columns (multiple stats with no clear one-to-one label) →
    [NEEDS REVIEW], never guessed.

    Returns (items, review_items) in the same format as _fuse_stat_pairs().
    """
    result = []
    review: list = []

    columns = _group_shapes_by_column(shapes)

    for col in columns:
        col_lines: list = []
        for shape in col:
            for line in shape.get("lines", []):
                text = (line.get("text") or "").strip()
                if text:
                    col_lines.append(text)

        if not col_lines:
            continue

        stat_lines = [t for t in col_lines if _is_bare_stat(t)]
        label_lines = [t for t in col_lines if not _is_bare_stat(t)]

        if not stat_lines:
            # No stats in this column — check for process steps, then emit as text
            for text in col_lines:
                m = _NUMBERED_STEP.match(text)
                if m:
                    step_num = int(m.group(1))
                    step_label = m.group(2)
                    result.append({"kind": "step", "text": step_label, "step_num": step_num})
                else:
                    result.append({"kind": "text", "text": text})
            continue

        if len(stat_lines) == 1:
            if label_lines:
                # Unambiguous: exactly one stat, one-or-more label lines in same column
                label = " ".join(label_lines)
                metric = f"{stat_lines[0]} {label}"
                result.append({"kind": "stat", "text": metric, "metric": metric})
            else:
                # Stat with no label in its column — flag
                marker = f"{stat_lines[0]} [NEEDS REVIEW]"
                result.append({"kind": "stat", "text": marker, "metric": marker})
                review.append({
                    "reason": f"Bare stat '{stat_lines[0]}' has no label in its visual column.",
                    "stat": stat_lines[0],
                })
        else:
            # Multiple stats in same column → geometry ambiguous, flag all
            for stat in stat_lines:
                marker = f"{stat} [NEEDS REVIEW]"
                result.append({"kind": "stat", "text": marker, "metric": marker})
            review.append({
                "reason": (
                    "Multiple stats in the same visual column — cannot determine "
                    "which label belongs to which stat. Verify manually."
                ),
                "stats": stat_lines,
                "labels": label_lines,
            })

    return result, review


def _extract_attribution(metric: str) -> Optional[str]:
    """Return the company name from 'for X' or 'by X' in a fused metric, or None."""
    m = _CUSTOMER_ATTR.search(metric)
    if not m:
        return None
    name = m.group(1).strip().rstrip(".")
    # Filter noise: short function words are not company names
    if len(name) < 3 or name.lower() in {"you", "your", "our", "the", "its"}:
        return None
    return name


def _slug(text: str, max_words: int = 5) -> str:
    """Stable slug for atom keys (lowercase alphanumeric + hyphens)."""
    clean = re.sub(r"[^a-z0-9\s]", "", text.lower())
    words = clean.split()[:max_words]
    return "-".join(w for w in words if w)


# ─── Concept tagger (atom-tagger, Phase D) ────────────────────────────────────

# Keyword → concept-ID mapping for the personalization deck.
# Concepts are stored in the atom's relatedTo.concepts[] array (Object field).
# productLine and audience are stored as concept IDs per the locked decision.
_CONCEPT_RULES: list = [
    # Product line
    (re.compile(r'\bpersonali[sz]ation\b', re.I),   "product:contentful-personalization"),
    (re.compile(r'\bexperiment',            re.I),   "product:contentful-personalization"),
    (re.compile(r'\bA/B test',              re.I),   "product:contentful-personalization"),
    (re.compile(r'\bai[\b\-]',              re.I),   "feature:ai"),
    (re.compile(r'\bai native\b',           re.I),   "feature:ai"),
    (re.compile(r'\bcdp\b',                 re.I),   "integration:cdp"),
    (re.compile(r'\bcrm\b',                 re.I),   "integration:crm"),
    (re.compile(r'\bcomposab',              re.I),   "architecture:composable"),
    (re.compile(r'\bmach\b',                re.I),   "architecture:composable"),
    # Audience / persona
    (re.compile(r'\bmarketer',              re.I),   "persona:marketer"),
    (re.compile(r'\bmarketing team',        re.I),   "persona:marketer"),
    (re.compile(r'\bdeveloper',             re.I),   "persona:developer"),
    (re.compile(r'\bdigital team',          re.I),   "persona:digital-team"),
    # Vertical / use-case
    (re.compile(r'\bretail\b',              re.I),   "vertical:retail"),
    (re.compile(r'\bCPG\b',                re.I),   "vertical:cpg"),
    (re.compile(r'\bfood.?bever',           re.I),   "vertical:cpg"),
    (re.compile(r'\be.?comm',               re.I),   "vertical:ecommerce"),
]


def _tag_concepts(text: str) -> list:
    """Return a deduplicated list of concept IDs that match the given text."""
    concepts: list = []
    seen: set = set()
    for pattern, concept_id in _CONCEPT_RULES:
        if pattern.search(text) and concept_id not in seen:
            concepts.append(concept_id)
            seen.add(concept_id)
    return concepts


# ─── Coarse transform (Phase 2) ───────────────────────────────────────────────

def transform_slide_coarse(slide: dict, source_doc_id: str) -> dict:
    """Deterministic: 1 slide → 1 contentAtom. Proves the Load pipeline works."""
    if slide["flags"]["unfinished"]:
        return {"atoms": [], "edges": [], "customers": [], "reviewQueue": [{
            "slideIndex": slide["slideIndex"],
            "reason": "unfinished content — skipped per non-negotiable rule",
            "value": "[UNFINISHED]",
        }]}

    atom_key = f"{source_doc_id}-slide-{slide['slideIndex']}"
    text_runs = slide.get("textRuns", [])
    body = "\n".join(text_runs) if text_runs else "[NEEDS REVIEW]"
    summary = slide.get("title") or (text_runs[0] if text_runs else "[NEEDS REVIEW]")

    atoms = [{
        "atomKey": atom_key,
        "atomType": _atom_type_from_slide(slide),
        "body": body,
        "semanticSummary": summary,
        "sourceDocument": source_doc_id,
        "sourceSlideIndex": slide["slideIndex"],
        "authorState": "incomplete" if slide["flags"].get("internal") else "complete",
    }]

    dq = slide.get("notes", {}).get("Discovery Questions", "").strip()
    if dq:
        atoms.append({
            "atomKey": f"{atom_key}-dq",
            "atomType": "insight",
            "subtype": "discovery_question",
            "body": dq,
            "semanticSummary": f"Discovery questions from slide {slide['slideIndex']}.",
            "sourceDocument": source_doc_id,
            "sourceSlideIndex": slide["slideIndex"],
            "authorState": "complete",
        })

    return {"atoms": atoms, "edges": [], "customers": [], "reviewQueue": []}


# ─── Smart transform (Phase 2+) ───────────────────────────────────────────────

def transform_slide_smart(
    slide: dict,
    source_doc_id: str,
    seen_customers: Optional[dict] = None,
) -> dict:
    """Smart deterministic transform. No LLM needed.

    Improvements over coarse:
      - Fuses bare stat lines with their labels ("70%" + "of marketers..." → one fused metric)
      - Splits multi-stat slides into one proof atom per stat (with metric field)
      - Detects numbered process steps and emits process_step atoms
      - Extracts customer attribution ("for Ace & Tate") and links attributedTo
      - Wires contains[] edges from parent value_prop to child proof/step atoms
      - Deduplicates customer entries across the full deck via seen_customers dict
    """
    if seen_customers is None:
        seen_customers = {}

    if slide["flags"]["unfinished"]:
        return {"atoms": [], "edges": [], "customers": [], "reviewQueue": [{
            "slideIndex": slide["slideIndex"],
            "reason": "unfinished content — skipped",
            "value": "[UNFINISHED]",
        }]}

    slide_idx = slide["slideIndex"]
    title = (slide.get("title") or "").strip()
    doc_pfx = source_doc_id.replace("gslides-", "")[:12]

    # Choose fusion strategy: geometry-aware when shapes[] present (GAS v2 export),
    # otherwise fall back to Pattern-A-only textRuns fusion.
    shapes = slide.get("shapes", [])
    if shapes:
        fused, fusion_review = _fuse_stat_cards_geometry(shapes)
    else:
        runs = slide.get("textRuns", [])
        body_runs = [r for r in runs if r.strip() and r.strip() != title]
        fused, fusion_review = _fuse_stat_pairs(body_runs)

    review: list = [{"slideIndex": slide_idx, **r} for r in fusion_review]
    stats = [f for f in fused if f["kind"] == "stat"]
    steps = [f for f in fused if f["kind"] == "step"]
    texts = [f for f in fused if f["kind"] == "text"]

    atoms: list = []
    new_customers: dict = {}
    edges: list = []

    # vp_key computed early so proof atoms can reference it via proves[]
    vp_key = f"{doc_pfx}-vp-{_slug(title)}" if title else None

    # ── Proof atoms (one per fused stat) ──────────────────────────────────────
    stat_atom_keys = []
    for s in stats:
        metric = s["metric"]
        akey = f"{doc_pfx}-stat-{_slug(metric)}"

        company = _extract_attribution(metric)
        attr_key = None
        if company:
            cslug = f"customer-{_slug(company, 3)}"
            if company not in seen_customers:
                seen_customers[company] = cslug
                new_customers[company] = cslug
            attr_key = seen_customers[company]

        full_text = f"{title} {metric}"
        concepts = _tag_concepts(full_text)

        atom: dict = {
            "atomKey": akey,
            "atomType": "proof",
            "metric": metric,
            "body": metric,
            "semanticSummary": metric,
            "sourceDocument": source_doc_id,
            "sourceSlideIndex": slide_idx,
            "authorState": "complete",
        }
        if attr_key:
            atom["attributedTo"] = attr_key
        if vp_key:
            atom["proves"] = [vp_key]
        if concepts:
            atom["relatedTo"] = {"concepts": concepts}

        atoms.append(atom)
        stat_atom_keys.append(akey)

    # ── Process step atoms ─────────────────────────────────────────────────────
    step_atom_keys = []
    prev_step_key = None
    for step in steps:
        akey = f"{doc_pfx}-step-s{slide_idx}-{step['step_num']}"
        atom = {
            "atomKey": akey,
            "atomType": "process_step",
            "body": step["text"],
            "semanticSummary": step["text"].split("\n")[0],
            "sourceDocument": source_doc_id,
            "sourceSlideIndex": slide_idx,
            "authorState": "complete",
        }
        atoms.append(atom)
        step_atom_keys.append(akey)
        if prev_step_key:
            edges.append({"source": prev_step_key, "target": akey, "relationType": "next"})
        prev_step_key = akey

    # ── Parent value_prop atom ─────────────────────────────────────────────────
    if title:
        author_state = "incomplete" if slide["flags"].get("internal") else "complete"

        # For non-stat/non-step slides, include body text in the value_prop.
        # Prefer shapes[] text (GAS v2) over flat textRuns for correct reading order.
        if not stats and not steps and texts:
            body_text = title + "\n" + "\n".join(t["text"] for t in texts)
        elif not stats and not steps and not shapes:
            runs_fb = slide.get("textRuns", [])
            body_runs_fb = [r for r in runs_fb if r.strip() and r.strip() != title]
            body_text = title + ("\n" + "\n".join(body_runs_fb) if body_runs_fb else "")
        else:
            body_text = title

        summary = title.split("\n")[0][:160]
        vp_concepts = _tag_concepts(body_text)

        parent_type = (
            "value_proposition"
            if stats or steps
            else _atom_type_from_slide(slide)
        )
        vp_atom: dict = {
            "atomKey": vp_key,
            "atomType": parent_type,
            "body": body_text,
            "semanticSummary": summary,
            "sourceDocument": source_doc_id,
            "sourceSlideIndex": slide_idx,
            "authorState": author_state,
        }

        child_keys = stat_atom_keys + step_atom_keys
        if child_keys:
            vp_atom["contains"] = child_keys
        if vp_concepts:
            vp_atom["relatedTo"] = {"concepts": vp_concepts}

        atoms.insert(0, vp_atom)

    # ── Image atoms from imageRefs[] (GAS v2 export — image-describer) ────────
    image_atom_keys = []
    for img in slide.get("imageRefs", []):
        img_key = f"{doc_pfx}-img-s{slide_idx}-{img.get('objectId', 'x')[-6:]}"
        alt = (img.get("altText") or "").strip()
        if not alt:
            alt = f"Image on slide {slide_idx} [NEEDS REVIEW]"
            img_review_state = "incomplete"
        else:
            img_review_state = "complete"

        img_atom: dict = {
            "atomKey": img_key,
            "atomType": "image",
            "body": alt,
            "semanticSummary": f"Slide {slide_idx} image: {alt[:120]}",
            "sourceDocument": source_doc_id,
            "sourceSlideIndex": slide_idx,
            "authorState": img_review_state,
        }
        if vp_key:
            img_atom["illustrates"] = [vp_key]
        img_concepts = _tag_concepts(alt)
        if img_concepts:
            img_atom["relatedTo"] = {"concepts": img_concepts}

        atoms.append(img_atom)
        image_atom_keys.append(img_key)

    # ── Customer entries (deduplicated) ────────────────────────────────────────
    customer_list = [
        {"atomKey": ckey, "name": cname}
        for cname, ckey in new_customers.items()
    ]

    # ── Discovery Questions from structured notes ──────────────────────────────
    dq = slide.get("notes", {}).get("Discovery Questions", "").strip()
    if dq:
        dq_key = f"{doc_pfx}-dq-s{slide_idx}"
        dq_concepts = _tag_concepts(dq)
        dq_atom: dict = {
            "atomKey": dq_key,
            "atomType": "insight",
            "subtype": "discovery_question",
            "body": dq,
            "semanticSummary": f"Discovery questions from slide {slide_idx}.",
            "sourceDocument": source_doc_id,
            "sourceSlideIndex": slide_idx,
            "authorState": "complete",
        }
        if dq_concepts:
            dq_atom["relatedTo"] = {"concepts": dq_concepts}
        atoms.append(dq_atom)

    return {"atoms": atoms, "edges": edges, "customers": customer_list, "reviewQueue": review}


# ─── LLM transform stub (Phase 3) ─────────────────────────────────────────────

def transform_slide_llm(slide: dict, source_doc_id: str) -> dict:
    """Wire your LLM client here for Phase 3.

    Alternatively (recommended for the POC): invoke the slides-atomizer skill
    in the Cursor agent chat. The agent reads the IR, applies the skill rules,
    and writes staging/03_atoms/{deck}.json directly. Then run:
        python pipeline/run.py --deck-id <id> --skip-transform --apply
    """
    if slide["flags"]["unfinished"]:
        return {"atoms": [], "edges": [], "customers": [], "reviewQueue": [{
            "slideIndex": slide["slideIndex"],
            "reason": "unfinished — skipped",
            "value": "[UNFINISHED]",
        }]}
    raise NotImplementedError(
        "Set LLM_API_KEY + LLM_MODEL in .env and implement complete(), OR "
        "use the agent-as-LLM pattern: run the slides-atomizer skill in Cursor chat, "
        "save the result to staging/03_atoms/{deck}.json, then --skip-transform."
    )


# ─── Orchestrator ──────────────────────────────────────────────────────────────

def run_transform(
    ir_path: str,
    deck_id: str,
    slide_range: Optional[Tuple[int, int]] = None,
    mode: Literal["coarse", "smart", "llm"] = "smart",
) -> str:
    """Transform IR → atoms JSON. Default mode is now 'smart'.

    Args:
        ir_path:     Path to staging/02_ir/{deck_id}.json
        deck_id:     Short deck identifier for output file naming
        slide_range: Optional (from_slide, to_slide) inclusive filter
        mode:        'coarse' | 'smart' (default) | 'llm'

    Returns:
        Path to staging/03_atoms/{deck_id}.json
    """
    ir = json.loads(Path(ir_path).read_text())
    slides = ir["slides"]

    if slide_range:
        lo, hi = slide_range
        slides = [s for s in slides if lo <= s["slideIndex"] <= hi]

    all_atoms: list = []
    all_edges: list = []
    all_customers: list = []
    all_review: list = []

    # seen_customers is shared across slides so the same company isn't emitted twice
    seen_customers: dict = {}

    for s in slides:
        if mode == "smart":
            result = transform_slide_smart(s, ir["sourceDocId"], seen_customers)
        elif mode == "coarse":
            result = transform_slide_coarse(s, ir["sourceDocId"])
        else:
            result = transform_slide_llm(s, ir["sourceDocId"])

        all_atoms += result["atoms"]
        all_edges += result["edges"]
        all_customers += result.get("customers", [])
        all_review += result["reviewQueue"]

    out = {
        "sourceDocument": {
            "title": ir["title"],
            "sourceUrl": ir["sourceUrl"],
            "sourceDocId": ir["sourceDocId"],
            "internalExternal": "internal" if any(s["flags"]["internal"] for s in slides) else "external",
            "slideOrder": [
                a["atomKey"] for a in all_atoms if a.get("atomType") != "customer"
            ],
        },
        "atoms": all_atoms,
        "customers": all_customers,
        "edges": all_edges,
        "reviewQueue": all_review,
    }

    out_path = STAGING / "03_atoms" / f"{deck_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    return str(out_path)
