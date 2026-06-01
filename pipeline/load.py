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
