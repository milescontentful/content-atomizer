"""Orchestrate Transform → Load for a deck that has already been extracted.

Extract (TypeScript) runs first as a separate step:
    npm run extract -- --deck <deckId>

Then this script handles Transform + Load:
    python pipeline/run.py --deck-id <deckId>              # dry-run (default)
    python pipeline/run.py --deck-id <deckId> --apply      # write drafts to Contentful
    python pipeline/run.py --deck-id <deckId> --from-slide 1 --to-slide 8

Full pipeline one-liner (bash):
    npm run extract -- --deck <deckId> && python pipeline/run.py --deck-id <deckId> --apply

Environment variables required for --apply:
    CTFL_SPACE_ID, CTFL_CMA_TOKEN  (see .env / .env.example)
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Allow running directly from the pipeline/ directory or from the repo root
sys.path.insert(0, str(Path(__file__).parent))

from transform import run_transform
from load import build_manifest, apply_manifest_cma


STAGING = Path(__file__).parent / "staging"


def _load_env() -> None:
    """Best-effort .env loader — no dependency on python-dotenv."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip() not in os.environ:
            os.environ[key.strip()] = val.strip()


def main() -> None:
    _load_env()

    p = argparse.ArgumentParser(
        description="Transform + Load one deck through the atomization pipeline."
    )
    p.add_argument("--deck-id", required=True, help="Short deck identifier, e.g. personalization-q2fy27")
    p.add_argument("--from-slide", type=int, default=None, help="First slide index to include (inclusive)")
    p.add_argument("--to-slide",   type=int, default=None, help="Last slide index to include (inclusive)")
    p.add_argument("--mode", choices=["coarse", "smart", "llm"], default="smart",
                   help="'smart' = stat-fusion + step detection (default); 'coarse' = 1-slide-1-atom; 'llm' = LLM/agent")
    p.add_argument("--skip-transform", action="store_true", default=False,
                   help="Skip transform — load whatever atoms JSON is already in staging/03_atoms/. "
                        "Use this when the Cursor agent wrote the atoms file directly (agent-as-LLM pattern).")
    p.add_argument("--apply", action="store_true", default=False,
                   help="Write draft entries to Contentful. Without this flag only a dry-run manifest is produced.")
    args = p.parse_args()

    deck_id = args.deck_id
    ir_path = STAGING / "02_ir" / f"{deck_id}.json"

    if not ir_path.exists():
        print(f"[run] ERROR: IR not found at {ir_path}")
        print(f"[run]   Run:  npm run extract -- --deck {deck_id}")
        sys.exit(1)

    slide_range = None
    if args.from_slide is not None and args.to_slide is not None:
        slide_range = (args.from_slide, args.to_slide)

    # ── Transform (or skip if agent already wrote the atoms file) ────────────
    atoms_path_obj = STAGING / "03_atoms" / f"{deck_id}.json"

    if args.skip_transform:
        if not atoms_path_obj.exists():
            print(f"[T] ERROR: --skip-transform set but atoms file not found: {atoms_path_obj}")
            print("[T]   Write the atoms JSON first (e.g. via the slides-atomizer skill in Cursor)")
            sys.exit(1)
        atoms_path = str(atoms_path_obj)
        print(f"[T] --skip-transform: using existing atoms file {atoms_path}")
    else:
        print(f"[T] transforming {deck_id}  mode={args.mode}" +
              (f"  slides {slide_range[0]}-{slide_range[1]}" if slide_range else ""))
        atoms_path = run_transform(str(ir_path), deck_id, slide_range=slide_range, mode=args.mode)
        print(f"[T] → {atoms_path}")

    atoms_data = json.loads(Path(atoms_path).read_text())
    atom_count = len(atoms_data["atoms"])
    customer_count = len(atoms_data.get("customers", []))
    review_count = len(atoms_data["reviewQueue"])
    print(f"[T]   {atom_count} atoms | {customer_count} customers | {review_count} review-queue items")

    # ── Build manifest (dry-run) ──────────────────────────────────────────────
    manifest_path = build_manifest(atoms_path, deck_id)
    manifest_data = json.loads(Path(manifest_path).read_text())
    print(f"[L] manifest → {manifest_path}  ({manifest_data['operationCount']} ops)")

    if not args.apply:
        print()
        print("[L] DRY-RUN complete. Review the manifest, then re-run with --apply to write drafts.")
        print(f"    python pipeline/run.py --deck-id {deck_id} --apply")
        if review_count > 0:
            print(f"\n[!] {review_count} items need human review (see 'reviewQueue' in {atoms_path})")
        return

    # ── Apply to Contentful ───────────────────────────────────────────────────
    required = ["CTFL_SPACE_ID", "CTFL_CMA_TOKEN"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"[L] ERROR: missing env vars: {', '.join(missing)}")
        print("[L]   Add them to .env or export them in your shell.")
        sys.exit(1)

    from contentful_client import ContentfulClient
    client = ContentfulClient()
    print(f"[L] applying to space {client.space_id} / {client.environment_id} …")

    results = apply_manifest_cma(manifest_path, client)

    created  = sum(1 for r in results if r.get("action") == "created")
    updated  = sum(1 for r in results if r.get("action") == "updated")
    reused   = sum(1 for r in results if r.get("action") == "reused")
    uploaded = sum(1 for r in results if r.get("action") == "uploaded")

    print(f"[L] done — {created} created | {updated} updated | {uploaded} uploaded | {reused} asset-reused")
    print("[L] all entries are in DRAFT. Approve in the Contentful UI to publish.")

    if review_count > 0:
        print(f"\n[!] {review_count} items need human review. See 'reviewQueue' in {atoms_path}")


if __name__ == "__main__":
    main()
