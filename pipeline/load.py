"""Load: atoms JSON -> Contentful via CMA.

Two steps:
  1. build_manifest()     – dry-run; writes staging/04_manifest/{deck}.json
                            with every operation the real load will execute.
                            Review this before writing anything to Contentful.
  2. apply_manifest_cma() – idempotent upsert; creates/updates draft entries.
                            Never publishes. Human approval publishes in the UI.
"""
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contentful_client import ContentfulClient

STAGING = Path(__file__).parent / "staging"


def build_manifest(atoms_path: str, deck_id: str) -> str:
    """Produce the exact create/upsert batch WITHOUT writing to Contentful.

    Order: customers (referenced entities) → sourceDocument → atoms.
    Image atoms with an 'asset' field are preceded by an uploadAsset op.
    """
    data = json.loads(Path(atoms_path).read_text())
    ops: list[dict] = []

    # 1. Referenced customer entities first
    for c in data.get("customers", []):
        ops.append({
            "op": "upsert",
            "contentType": "customer",
            "key": c["atomKey"],
            "fields": c,
        })

    # 2. Source document
    ops.append({
        "op": "upsert",
        "contentType": "sourceDocument",
        "key": data["sourceDocument"]["sourceDocId"],
        "fields": data["sourceDocument"],
    })

    # 3. Atoms (image atoms preceded by an asset upload op)
    for a in data["atoms"]:
        if a.get("atomType") == "image" and a.get("asset"):
            ops.append({
                "op": "uploadAsset",
                "key": a["asset"],
                "source": a.get("body"),
            })
        ops.append({
            "op": "upsert",
            "contentType": "contentAtom",
            "key": a["atomKey"],
            "fields": a,
            "status": "draft",
        })

    manifest = {
        "deck": deck_id,
        "operationCount": len(ops),
        "operations": ops,
    }
    out_path = STAGING / "04_manifest" / f"{deck_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2))
    return str(out_path)


def apply_manifest_cma(manifest_path: str, client: "ContentfulClient") -> list[dict]:
    """Apply the manifest to Contentful via CMA. Idempotent; never publishes.

    Returns a list of operation results: [{op, key, id, action}].
    """
    manifest = json.loads(Path(manifest_path).read_text())
    results: list[dict] = []

    for op in manifest["operations"]:
        if op["op"] == "uploadAsset":
            result = client.upload_asset(
                file_path=op["source"],
                title=op["key"],
            )
            results.append({"op": "uploadAsset", "key": op["key"], **result})

        elif op["op"] == "upsert":
            result = client.upsert_entry(
                content_type=op["contentType"],
                key=op["key"],
                fields=op["fields"],
            )
            results.append({"op": "upsert", "key": op["key"], **result})

    return results
