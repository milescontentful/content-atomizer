"""Extract: Google Slides API JSON -> normalized IR.

IMPORTANT: This file is an ALTERNATIVE extract path for use with the direct
Google Slides API (via parse_slides.py / service account auth). It is NOT
used by the main pipeline.

The PRIMARY extract path is pipeline/extract.ts, which processes the
output of tools/export-for-atomization.gs (Google Apps Script export).
To run the main pipeline:
    npm run extract -- --deck <deckId>
    python pipeline/run.py --deck-id <deckId>

This Python path is kept for completeness; use it when you want to bypass
the GAS export and hit the Slides API directly with a service account.

IR shape (matches pipeline/extract.ts output):
  sourceDocId, title, sourceUrl, slides[] where each slide has:
  slideIndex, objectId, textRuns[], shapes[], imageRefs[], imageCount,
  notes{}, rawNotes, flags{unfinished, internal}
"""
import json
from pathlib import Path

STAGING = Path(__file__).parent / "staging"

NOTE_SECTIONS = ["Goal", "Talk Track", "Key Points", "Key Takeaway", "Discovery Questions"]
UNFINISHED_CUES = ["need numbers", "[add in", "tbd", "todo", "xx%", "lorem ipsum", "<insert", "placeholder"]
INTERNAL_CUES = ["internal only", "do not use", "[template]", "confidential"]


def parse_structured_notes(notes: str) -> dict:
    if not notes:
        return {}
    out: dict = {}
    current = None
    for line in notes.splitlines():
        header = next((s for s in NOTE_SECTIONS if line.strip().lower().startswith(s.lower())), None)
        if header:
            current = header
            out[current] = line.split(":", 1)[1].strip() if ":" in line else ""
        elif current:
            out[current] = (out[current] + "\n" + line).strip()
    return out


def detect_unfinished(text: str) -> bool:
    low = text.lower()
    return any(cue in low for cue in UNFINISHED_CUES)


def build_ir(parsed_deck: dict) -> dict:
    """parsed_deck = output of scripts/parse_slides.parse_deck().

    The parse_slides.py output does not include per-shape geometry; shapes[] and
    imageRefs[] are passed through from the raw output as-is. When using the GAS
    export path (extract.ts), shapes[] includes bounding-box geometry, which
    enables geometry-aware stat fusion in the transform stage.
    """
    slides_ir = []
    for s in parsed_deck["slides"]:
        text_runs = s.get("textRuns", [])
        joined = " ".join(text_runs)
        speaker_notes = s.get("speakerNotes", "")

        # shapes[] and imageRefs[] from parse_slides.py don't carry geometry,
        # but we preserve whatever is present for forward-compat.
        shapes = s.get("shapes", [])
        image_refs = s.get("imageRefs", [])
        image_count = len(image_refs) if image_refs else s.get("imageCount", 0)

        slides_ir.append({
            "slideIndex": s["slideIndex"],
            "objectId": s["objectId"],
            "textRuns": text_runs,
            "shapes": shapes,
            "imageRefs": image_refs,
            "imageCount": image_count,
            "notes": parse_structured_notes(speaker_notes),
            "rawNotes": speaker_notes,
            "flags": {
                "unfinished": detect_unfinished(joined + " " + speaker_notes),
                "internal": any(c in (joined + speaker_notes).lower() for c in INTERNAL_CUES),
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
    ir = build_ir(raw)
    out_path = STAGING / "02_ir" / f"{deck_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(ir, indent=2))
    return str(out_path)
