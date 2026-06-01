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


# Fields that hold Entry links — values that match a manifest key get converted
# to CMA link objects once we know the real Contentful entry ID.
_LINK_FIELDS = {
    "sourceDocument", "attributedTo", "proves", "illustrates", "contains", "appliesTo", "atoms"
}


def _resolve_links(fields: dict, key_to_id: dict) -> dict:
    """Replace plain key strings in link fields with CMA link objects."""
    resolved = {}
    for field, value in fields.items():
        if field not in _LINK_FIELDS:
            resolved[field] = value
            continue
        if isinstance(value, str) and value in key_to_id:
            resolved[field] = {"sys": {"type": "Link", "linkType": "Entry", "id": key_to_id[value]}}
        elif isinstance(value, list):
            resolved[field] = [
                {"sys": {"type": "Link", "linkType": "Entry", "id": key_to_id[item]}}
                if isinstance(item, str) and item in key_to_id else item
                for item in value
            ]
        else:
            resolved[field] = value
    return resolved


def apply_manifest_cma(manifest_path: str, client: "ContentfulClient") -> list:
    """Apply the manifest to Contentful via CMA. Idempotent; never publishes.

    Two-pass strategy to handle forward references (e.g. a parent atom's
    'contains' field references children that don't exist yet):
      Pass 1 — upsert every entry without link/reference fields.
               Builds key→entryId map as entries are created.
      Pass 2 — update every entry that has relationship fields, now that
               all target entry IDs are known.

    Returns a list of operation results: [{op, key, id, action}].
    """
    manifest = json.loads(Path(manifest_path).read_text())
    results = []
    key_to_id: dict = {}

    upsert_ops = [op for op in manifest["operations"] if op["op"] == "upsert"]
    asset_ops  = [op for op in manifest["operations"] if op["op"] == "uploadAsset"]

    # ── Asset uploads (no forward-ref issue) ──────────────────────────────────
    for op in asset_ops:
        result = client.upload_asset(file_path=op["source"], title=op["key"])
        results.append({"op": "uploadAsset", "key": op["key"], **result})

    # ── Pass 1: create / update entries without relationship fields ────────────
    for op in upsert_ops:
        fields_no_links = {k: v for k, v in op["fields"].items() if k not in _LINK_FIELDS}
        result = client.upsert_entry(
            content_type=op["contentType"],
            key=op["key"],
            fields=fields_no_links,
        )
        key_to_id[op["key"]] = result["id"]
        results.append({"op": "upsert", "key": op["key"], **result})

    # ── Pass 2: patch relationship fields now all entry IDs are known ──────────
    for op in upsert_ops:
        link_fields = {k: v for k, v in op["fields"].items() if k in _LINK_FIELDS and v}
        if not link_fields:
            continue
        resolved = _resolve_links(link_fields, key_to_id)
        # Only update if every link field resolved fully (no plain-string leftovers)
        all_resolved = all(
            not isinstance(v, str)
            for v in (resolved.values() if not isinstance(resolved, list) else resolved)
        )
        client.upsert_entry(
            content_type=op["contentType"],
            key=op["key"],
            fields={**{k: v for k, v in op["fields"].items() if k not in _LINK_FIELDS},
                    **resolved},
        )

    return results
