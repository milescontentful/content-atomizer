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
