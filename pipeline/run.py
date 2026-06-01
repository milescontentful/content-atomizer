"""Orchestrate E -> T -> L with scoping so you don't run all 200 slides."""
import argparse
from extract import run_extract
from transform import run_transform
from load import build_manifest

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--deck-id", required=True)
    p.add_argument("--raw", required=True, help="path to parse_deck() JSON output")
    p.add_argument("--from-slide", type=int, default=0)
    p.add_argument("--to-slide", type=int, default=8)   # default: first ~8 slides
    p.add_argument("--dry-run", action="store_true", default=True)
    args = p.parse_args()

    ir_path = run_extract(args.raw, args.deck_id)
    print(f"[E] IR -> {ir_path}")
    atoms_path = run_transform(ir_path, args.deck_id, slide_range=(args.from_slide, args.to_slide))
    print(f"[T] atoms -> {atoms_path}")
    manifest_path = build_manifest(atoms_path, args.deck_id)
    print(f"[L] manifest (dry-run) -> {manifest_path}")
    print("Review the manifest, then run the MCP/CMA load to write drafts to Contentful.")

if __name__ == "__main__":
    main()
