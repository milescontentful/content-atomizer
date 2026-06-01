"""Transform: IR -> draft atoms + edges + review queue.

Two modes:
  coarse  (Phase 2) – deterministic, no LLM; 1 slide -> 1 contentAtom.
                      Discovery Questions in notes become a second atom.
                      Safe to run immediately with no API keys.
  llm     (Phase 3) – LLM extraction per ATOM_PROMPT; output must match
                      eval/example-slide-expected.json before scaling.

Output matches the schema in model/contentAtom.json (corrected shape):
  - no 'status' field (native publish state gates retrieval)
  - 'authorState' enum: complete | incomplete | template
  - native relationship fields (proves/illustrates/contains) handled by
    the relationship-mapper skill in Phase 4; left empty here
"""
import json
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
- If attribution, persona, or a stat's meaning is unclear -> value "[NEEDS REVIEW]".
- Every atom: atomKey, atomType, subtype?, body, semanticSummary (self-contained),
  authorState="complete".
Return JSON: {atoms:[...], edges:[{source,target,relationType}], reviewQueue:[...]}.
Atom types: value_proposition, proof, quote, case_study, image, feature, process_step,
            cta, insight"""

# ─── slideType -> atomType mapping (coarse mode) ─────────────────────────────

_SLIDE_TYPE_TO_ATOM_TYPE: dict[str, str] = {
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


# ─── Coarse transform (Phase 2, no LLM) ──────────────────────────────────────

def transform_slide_coarse(slide: dict, source_doc_id: str) -> dict:
    """Deterministic: 1 slide → 1 contentAtom, plus a Discovery Questions atom if present.

    Unfinished slides are logged to the review queue and skipped.
    Internal slides get authorState='incomplete' so they stay gated.
    """
    if slide["flags"]["unfinished"]:
        return {
            "atoms": [],
            "edges": [],
            "reviewQueue": [{
                "slideIndex": slide["slideIndex"],
                "reason": "unfinished content — skipped per non-negotiable rule",
                "value": "[UNFINISHED]",
            }],
        }

    atom_key = f"{source_doc_id}-slide-{slide['slideIndex']}"
    text_runs = slide.get("textRuns", [])
    body = "\n".join(text_runs) if text_runs else "[NEEDS REVIEW]"
    # Use the slide title as a proxy semantic summary (Phase 3 LLM will replace this)
    summary = slide.get("title") or (text_runs[0] if text_runs else "[NEEDS REVIEW]")
    author_state = "incomplete" if slide["flags"].get("internal") else "complete"

    atoms: list[dict] = [{
        "atomKey": atom_key,
        "atomType": _atom_type_from_slide(slide),
        "body": body,
        "semanticSummary": summary,
        "sourceDocument": source_doc_id,
        "sourceSlideIndex": slide["slideIndex"],
        "authorState": author_state,
    }]

    # Discovery Questions → dedicated insight atom (highest reuse value per build doc)
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

    return {"atoms": atoms, "edges": [], "reviewQueue": []}


# ─── LLM transform stub (Phase 3) ────────────────────────────────────────────

def transform_slide_llm(slide: dict, source_doc_id: str) -> dict:
    """Wire your LLM client here. Validate against eval/example-slide-expected.json
    on the Example-1 slide before scaling to more slides."""
    if slide["flags"]["unfinished"]:
        return {
            "atoms": [],
            "edges": [],
            "reviewQueue": [{
                "slideIndex": slide["slideIndex"],
                "reason": "unfinished content — skipped",
                "value": "[UNFINISHED]",
            }],
        }
    payload = {"slide": slide, "sourceDocument": source_doc_id}
    # raw = complete(system=ATOM_PROMPT, user=json.dumps(payload))
    # return json.loads(raw)
    raise NotImplementedError(
        "Wire your LLM client into transform_slide_llm. "
        "Set LLM_API_KEY + LLM_MODEL in .env and implement complete()."
    )


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def run_transform(
    ir_path: str,
    deck_id: str,
    slide_range: Optional[Tuple[int, int]] = None,
    mode: Literal["coarse", "llm"] = "coarse",
) -> str:
    """Transform IR → atoms JSON.

    Args:
        ir_path:     Path to staging/02_ir/{deck_id}.json
        deck_id:     Short deck identifier used for output file naming
        slide_range: Optional (from_slide, to_slide) inclusive filter; default = all slides
        mode:        "coarse" (Phase 2, no LLM) or "llm" (Phase 3)

    Returns:
        Path to staging/03_atoms/{deck_id}.json
    """
    ir = json.loads(Path(ir_path).read_text())
    slides = ir["slides"]

    if slide_range:
        lo, hi = slide_range
        slides = [s for s in slides if lo <= s["slideIndex"] <= hi]

    transform_fn = transform_slide_coarse if mode == "coarse" else transform_slide_llm

    atoms: list[dict] = []
    edges: list[dict] = []
    review: list[dict] = []

    for s in slides:
        result = transform_fn(s, ir["sourceDocId"])
        atoms += result["atoms"]
        edges += result["edges"]
        review += result["reviewQueue"]

    out = {
        "sourceDocument": {
            "title": ir["title"],
            "sourceUrl": ir["sourceUrl"],
            "sourceDocId": ir["sourceDocId"],
            "internalExternal": "internal" if any(s["flags"]["internal"] for s in slides) else "external",
            "slideOrder": [a["atomKey"] for a in atoms],
        },
        "atoms": atoms,
        "edges": edges,
        "reviewQueue": review,
    }

    out_path = STAGING / "03_atoms" / f"{deck_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    return str(out_path)
