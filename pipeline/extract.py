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
