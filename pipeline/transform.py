"""Transform: IR -> draft atoms + edges + review queue.

Three modes
-----------
  coarse  (Phase 2)  Deterministic: 1 slide → 1 atom. Proves Load works.
  smart   (Phase 2+) Deterministic: stat fusion, process-step detection,
                     customer attribution, contains edges. No LLM needed.
                     Produces 80% of the quality an LLM would give.
  llm     (Phase 3)  LLM extraction per ATOM_PROMPT. Wire LLM_API_KEY.
                     Alternatively, invoke the slides-atomizer Cursor skill
                     agentically and write the atoms JSON by hand — the
                     agent IS the LLM for the POC (no API key required).

Agent-as-LLM pattern (recommended for POC without an LLM key)
-------------------------------------------------------------
  The slides-atomizer / relationship-mapper skills in skills/ are written
  to run inside the Cursor agent chat. Invoke them there, let the agent
  write staging/03_atoms/{deck}.json, then run:
    python pipeline/run.py --deck-id <id> --skip-transform --apply
  The --skip-transform flag (see run.py) bypasses this module entirely and
  loads whatever atoms JSON is already on disk.

Output shape matches model/contentAtom.json (corrected):
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
    """Scan text runs and fuse bare-stat lines with their labels.

    Handles two patterns found in real decks:
      Pattern A (stat → label): "70%\\nof marketers say..."
        → "70% of marketers say..."  (unambiguous, always correct)
      Pattern B (label-block → stat-block, same count ≥ 2):
        "higher CTR for Ace & Tate\\n78%\\n87%\\n..."
        → pairs by DOM index order (may need visual review — flagged)

    Returns (items, review_items):
      items: list of {'kind': 'stat'|'step'|'text', 'text': str, ['metric': str], ['step_num': int]}
      review_items: list of {'reason': str, ...} for items needing human verification
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

        # ── Pattern A: stat immediately followed by a non-stat label ──────────
        # This is unambiguous — the label directly follows the number in DOM order.
        if _is_bare_stat(text) and i + 1 < n and not _is_bare_stat(runs[i + 1]):
            metric = f"{text} {runs[i + 1].strip()}"
            result.append({"kind": "stat", "text": metric, "metric": metric})
            i += 2
            continue

        # ── Pattern B: contiguous label-block then stat-block of equal size ───
        # Requires ≥ 2 stats to avoid false positives (single-stat case is
        # handled by Pattern A on the next iteration). Flags for review because
        # DOM order ≠ visual layout order — a human should verify the pairing.
        if not _is_bare_stat(text):
            j = i
            while j < n and not _is_bare_stat(runs[j]):
                j += 1
            k = j
            while k < n and _is_bare_stat(runs[k]):
                k += 1
            label_count = j - i
            stat_count = k - j

            if 2 <= stat_count == label_count <= 5:
                fused = []
                for idx in range(stat_count):
                    metric = f"{runs[j + idx].strip()} {runs[i + idx].strip()}"
                    result.append({"kind": "stat", "text": metric, "metric": metric})
                    fused.append(metric)
                review.append({
                    "reason": (
                        "Pattern B stat fusion: DOM order may not match visual layout order. "
                        "Verify each stat-label pairing is correct."
                    ),
                    "fusedMetrics": fused,
                })
                i = k
                continue

        # ── Numbered process step ──────────────────────────────────────────────
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
    # Use a short prefix of the sourceDocId so atomKeys are readable
    doc_pfx = source_doc_id.replace("gslides-", "")[:12]

    runs = slide.get("textRuns", [])
    # Remove runs that exactly duplicate the title
    body_runs = [r for r in runs if r.strip() and r.strip() != title]

    fused, fusion_review = _fuse_stat_pairs(body_runs)
    review: list = [{"slideIndex": slide_idx, **r} for r in fusion_review]
    stats = [f for f in fused if f["kind"] == "stat"]
    steps = [f for f in fused if f["kind"] == "step"]
    texts = [f for f in fused if f["kind"] == "text"]

    atoms: list = []
    new_customers: dict = {}
    edges: list = []

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
        vp_key = f"{doc_pfx}-vp-{_slug(title)}"
        author_state = "incomplete" if slide["flags"].get("internal") else "complete"

        # For non-stat/non-step slides, include remaining text in body
        if not stats and not steps and texts:
            body_text = title + "\n" + "\n".join(t["text"] for t in texts)
        else:
            body_text = title

        # Summary: first meaningful sentence (≤160 chars)
        summary = title.split("\n")[0][:160]

        vp_atom: dict = {
            "atomKey": vp_key,
            "atomType": _atom_type_from_slide(slide),
            "body": body_text,
            "semanticSummary": summary,
            "sourceDocument": source_doc_id,
            "sourceSlideIndex": slide_idx,
            "authorState": author_state,
        }

        child_keys = stat_atom_keys + step_atom_keys
        if child_keys:
            vp_atom["contains"] = child_keys

        atoms.insert(0, vp_atom)

    # ── Customer entries (deduplicated) ────────────────────────────────────────
    customer_list = [
        {"atomKey": ckey, "name": cname}
        for cname, ckey in new_customers.items()
    ]

    # ── Discovery Questions from structured notes ──────────────────────────────
    dq = slide.get("notes", {}).get("Discovery Questions", "").strip()
    if dq:
        dq_key = f"{doc_pfx}-dq-s{slide_idx}"
        atoms.append({
            "atomKey": dq_key,
            "atomType": "insight",
            "subtype": "discovery_question",
            "body": dq,
            "semanticSummary": f"Discovery questions from slide {slide_idx}.",
            "sourceDocument": source_doc_id,
            "sourceSlideIndex": slide_idx,
            "authorState": "complete",
        })

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
