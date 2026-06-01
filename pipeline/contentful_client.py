"""contentful_client.py — minimal CMA wrapper for the Load stage.

Idempotent upsert by atomKey, asset upload deduped by content hash, draft-only.
Wire your own CMA token / space / environment via env vars. This is an MVP stub:
no retry/backoff, no rate-limit handling, no rich-text conversion — add in Cursor.
"""
import os
import hashlib
from typing import Any

# import contentful_management  # pip install contentful-management

DEFAULT_LOCALE = os.environ.get("CTFL_LOCALE", "en-US")


class ContentfulClient:
    def __init__(self, space_id: str | None = None, environment_id: str | None = None,
                 cma_token: str | None = None, locale: str = DEFAULT_LOCALE):
        self.space_id = space_id or os.environ["CTFL_SPACE_ID"]
        self.environment_id = environment_id or os.environ.get("CTFL_ENVIRONMENT_ID", "master")
        self.cma_token = cma_token or os.environ["CTFL_CMA_TOKEN"]
        self.locale = locale
        # self._client = contentful_management.Client(self.cma_token)
        # self._env = self._client.environments(self.space_id).find(self.environment_id)
        self._env = None  # wire in Cursor

    # --- helpers -----------------------------------------------------------
    def _wrap(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Flat {fieldId: value} -> CMA {fieldId: {locale: value}}."""
        return {k: {self.locale: v} for k, v in fields.items() if v is not None}

    def _find_by_atom_key(self, content_type: str, atom_key: str):
        """Look up an entry by its stable atomKey. Returns the entry or None."""
        # entries = self._env.entries().all({
        #     "content_type": content_type,
        #     "fields.atomKey": atom_key,
        #     "limit": 1,
        # })
        # return entries[0] if len(entries) else None
        return None  # wire in Cursor

    @staticmethod
    def _hash_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # --- entries -----------------------------------------------------------
    def upsert_entry(self, content_type: str, atom_key: str,
                     fields: dict[str, Any]) -> dict[str, Any]:
        """Create or update an entry, keyed on atomKey. Leaves it in DRAFT.

        Returns {"id", "action", "atomKey"} where action is created|updated.
        """
        fields = {**fields, "atomKey": atom_key}
        existing = self._find_by_atom_key(content_type, atom_key)
        wrapped = self._wrap(fields)

        if existing is not None:
            # for field_id, value in wrapped.items():
            #     setattr(existing.fields(self.locale), field_id, value[self.locale])
            # existing.save()  # save() does NOT publish
            return {"id": getattr(existing, "id", "?"), "action": "updated", "atomKey": atom_key}

        # entry = self._env.entries().create(None, {
        #     "content_type_id": content_type,
        #     "fields": wrapped,
        # })
        # return {"id": entry.id, "action": "created", "atomKey": atom_key}
        return {"id": "<new>", "action": "created", "atomKey": atom_key}

    def link(self, entry_id: str) -> dict[str, Any]:
        """Build a CMA link object for reference fields (relatedTo, attributedTo)."""
        return {"sys": {"type": "Link", "linkType": "Entry", "id": entry_id}}

    def asset_link(self, asset_id: str) -> dict[str, Any]:
        return {"sys": {"type": "Link", "linkType": "Asset", "id": asset_id}}

    # --- assets ------------------------------------------------------------
    def upload_asset(self, file_path: str, title: str,
                     description: str = "") -> dict[str, Any]:
        """Upload a binary as a Contentful Asset, deduped by content hash.

        Returns {"id", "action", "hash"}. Leaves the asset in DRAFT.
        The wrapper image atom links to this asset via its `asset` field.
        """
        content_hash = self._hash_file(file_path)
        existing = self._find_asset_by_hash(content_hash)
        if existing is not None:
            return {"id": getattr(existing, "id", "?"), "action": "reused", "hash": content_hash}

        # upload = self._env.uploads().create(file_path)
        # asset = self._env.assets().create(None, {
        #     "fields": self._wrap({
        #         "title": title,
        #         "description": description,
        #     }) | {"file": {self.locale: {
        #         "contentType": _guess_mime(file_path),
        #         "fileName": os.path.basename(file_path),
        #         "uploadFrom": {"sys": {"type": "Link", "linkType": "Upload", "id": upload.id}},
        #     }}},
        # })
        # asset.process()              # process the binary (does NOT publish)
        # asset.metadata tag: sha256 = content_hash  (for future dedup lookup)
        return {"id": "<new-asset>", "action": "uploaded", "hash": content_hash}

    def _find_asset_by_hash(self, content_hash: str):
        # assets = self._env.assets().all({"metadata.tags.sys.id[in]": f"sha256-{content_hash}"})
        # return assets[0] if len(assets) else None
        return None  # wire in Cursor


def _guess_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".svg": "image/svg+xml", ".pdf": "application/pdf",
    }.get(ext, "application/octet-stream")


if __name__ == "__main__":
    # Smoke test (no network): exercises hashing + link/wrap helpers only.
    client = ContentfulClient(space_id="demo", cma_token="demo")
    print(client.link("entry-123"))
    print(client.asset_link("asset-123"))
    print(client._wrap({"title": "Hello", "skip": None}))
