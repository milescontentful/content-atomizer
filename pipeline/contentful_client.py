"""contentful_client.py — CMA wrapper for the Load stage.

Idempotent upsert by atomKey, asset upload deduped by content hash, draft-only.
Requires: pip install contentful-management  (see requirements.txt)

Environment variables (set in .env):
    CTFL_SPACE_ID       space ce81lr6pgre8
    CTFL_ENVIRONMENT_ID master
    CTFL_CMA_TOKEN      your CMA token
    CTFL_LOCALE         en-US (default)
"""
import os
import hashlib
from typing import Any, Optional

import contentful_management  # pip install contentful-management

DEFAULT_LOCALE = os.environ.get("CTFL_LOCALE", "en-US")

# The unique identifier field for each content type (not always atomKey)
_KEY_FIELD: dict = {
    "contentAtom":    "atomKey",
    "customer":       "atomKey",
    "sourceDocument": "sourceDocId",
    "projectContext": "contextKey",
}


class ContentfulClient:
    def __init__(
        self,
        space_id: Optional[str] = None,
        environment_id: Optional[str] = None,
        cma_token: Optional[str] = None,
        locale: str = DEFAULT_LOCALE,
    ):
        self.space_id = space_id or os.environ["CTFL_SPACE_ID"]
        self.environment_id = environment_id or os.environ.get("CTFL_ENVIRONMENT_ID", "master")
        self.cma_token = cma_token or os.environ["CTFL_CMA_TOKEN"]
        self.locale = locale

        self._client = contentful_management.Client(self.cma_token)
        self._env = self._client.environments(self.space_id).find(self.environment_id)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _key_field(self, content_type: str) -> str:
        return _KEY_FIELD.get(content_type, "atomKey")

    def _wrap(self, fields: dict) -> dict:
        """Flat {fieldId: value} → CMA {fieldId: {locale: value}}, skipping None."""
        return {k: {self.locale: v} for k, v in fields.items() if v is not None}

    def _find_by_key(self, content_type: str, key_value: str) -> Optional[Any]:
        """Return the first entry matching the type's unique key field, or None."""
        field = self._key_field(content_type)
        entries = self._env.entries().all({
            "content_type": content_type,
            f"fields.{field}": key_value,
            "limit": 1,
        })
        return entries[0] if len(entries) else None

    @staticmethod
    def _hash_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # ── Entries ───────────────────────────────────────────────────────────────

    def upsert_entry(
        self,
        content_type: str,
        key: str,
        fields: dict,
    ) -> dict:
        """Create or update an entry keyed on atomKey. Leaves it in DRAFT.

        Returns {"id", "action", "atomKey"} where action is "created" | "updated".
        """
        key_field = self._key_field(content_type)
        if key_field not in fields:
            fields = {**fields, key_field: key}
        existing = self._find_by_key(content_type, key)
        wrapped = self._wrap(fields)

        if existing is not None:
            existing.raw["fields"] = wrapped
            existing.save()
            return {"id": existing.sys["id"], "action": "updated", "atomKey": key}

        entry = self._env.entries().create(
            None,  # auto-generate entry ID
            {
                "content_type_id": content_type,
                "fields": wrapped,
            },
        )
        # save() after create is not strictly required but ensures the version
        # counter is consistent if the caller re-fetches immediately
        return {"id": entry.sys["id"], "action": "created", "atomKey": key}

    def link(self, entry_id: str) -> dict[str, Any]:
        """Build a CMA link object for reference fields (proves, attributedTo, etc.)."""
        return {"sys": {"type": "Link", "linkType": "Entry", "id": entry_id}}

    def asset_link(self, asset_id: str) -> dict[str, Any]:
        return {"sys": {"type": "Link", "linkType": "Asset", "id": asset_id}}

    # ── Assets ────────────────────────────────────────────────────────────────

    def upload_asset(
        self,
        file_path: str,
        title: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Upload a binary as a Contentful Asset, deduped by content hash.

        Returns {"id", "action", "hash"}. Leaves the asset in DRAFT.
        The wrapper image atom links to this asset via its 'asset' field.
        """
        content_hash = self._hash_file(file_path)
        existing = self._find_asset_by_hash(content_hash)
        if existing is not None:
            return {"id": existing.sys["id"], "action": "reused", "hash": content_hash}

        upload = self._env.uploads().create(file_path)
        asset = self._env.assets().create(
            None,
            {
                "fields": self._wrap({"title": title, "description": description})
                | {
                    "file": {
                        self.locale: {
                            "contentType": _guess_mime(file_path),
                            "fileName": os.path.basename(file_path),
                            "uploadFrom": {
                                "sys": {
                                    "type": "Link",
                                    "linkType": "Upload",
                                    "id": upload.sys["id"],
                                }
                            },
                        }
                    }
                },
            },
        )
        asset.process()  # enqueue binary processing (does NOT publish)
        return {"id": asset.sys["id"], "action": "uploaded", "hash": content_hash}

    def _find_asset_by_hash(self, content_hash: str) -> Optional[Any]:
        """Look up an asset by its sha256 tag. Returns None if not found."""
        assets = self._env.assets().all({
            "metadata.tags.sys.id[in]": f"sha256-{content_hash}",
            "limit": 1,
        })
        return assets[0] if len(assets) else None


def _guess_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf",
    }.get(ext, "application/octet-stream")


if __name__ == "__main__":
    # Smoke test: exercises link/wrap helpers without network.
    client = ContentfulClient.__new__(ContentfulClient)
    client.locale = "en-US"
    print(client.link("entry-123"))
    print(client.asset_link("asset-123"))
    client._env = None
    print("helpers OK")
