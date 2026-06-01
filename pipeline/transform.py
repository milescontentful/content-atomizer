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
