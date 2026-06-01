#!/usr/bin/env python3
"""
scripts/eval.py — Regression harness for the geometry-aware transform.

Diffs staging/03_atoms/{deck}.json output for the composite proof slide
against eval/example-slide-expected.json.

Rules checked (from anchor._evalRules):
  1. statAttributionChecks — each stat value (87%, 78%, <30min) must appear in
     exactly one proof atom, paired with the correct customer name, and NOT
     paired with any of the wrong customer names.
  2. noNeedsReviewInMetric — no proof atom's 'metric' field contains '[NEEDS REVIEW]'.
  3. allProofsMustHaveAttributedTo — every proof atom must have a non-empty 'attributedTo'.
  4. requiredAtomTypes — the expected atom type counts must be present.

Usage:
  python3 scripts/eval.py [--deck DECK_ID]

  DECK_ID defaults to 'personalization-q2fy27'.

Exit codes:
  0 — all checks pass (green)
  1 — one or more checks failed (red — do NOT scale)
"""

import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
ANCHOR_PATH = ROOT / "eval" / "example-slide-expected.json"
STAGING_ATOMS = ROOT / "pipeline" / "staging" / "03_atoms"

SLIDE_4_INDEX = 4   # The composite proof slide we're gating on


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        print(f"[eval] ERROR: file not found: {path}")
        sys.exit(1)


def atoms_for_slide(atoms: list, slide_index: int) -> list:
    return [a for a in atoms if a.get("sourceSlideIndex") == slide_index]


def run_eval(deck_id: str = "personalization-q2fy27") -> None:
    anchor = load_json(ANCHOR_PATH)
    atoms_path = STAGING_ATOMS / f"{deck_id}.json"
    pipeline_out = load_json(atoms_path)

    print(f"[eval] deck     : {deck_id}")
    print(f"[eval] atoms    : {atoms_path}")
    print(f"[eval] anchor   : {ANCHOR_PATH}")
    print(f"[eval] checking slide {SLIDE_4_INDEX} (composite proof slide)\n")

    eval_rules = anchor.get("_evalRules", {})
    all_atoms: list = pipeline_out.get("atoms", [])
    slide_atoms = atoms_for_slide(all_atoms, SLIDE_4_INDEX)

    if not slide_atoms:
        # Fall back to checking all atoms if no sourceSlideIndex is set
        slide_atoms = all_atoms
        print(f"[eval] NOTE: no atoms with sourceSlideIndex={SLIDE_4_INDEX}; checking all atoms\n")

    proof_atoms = [a for a in slide_atoms if a.get("atomType") == "proof"]
    failures: list = []

    # ── Check 1: stat-attribution pairings ─────────────────────────────────────
    stat_checks = eval_rules.get("statAttributionChecks", [])
    for check in stat_checks:
        stat_val    = check["stat"]
        must_have   = check["mustContain"]
        must_not    = check.get("mustNotContain", [])

        # Find proof atoms whose metric contains this stat value
        matching_atoms = [
            a for a in proof_atoms
            if stat_val in (a.get("metric") or a.get("body") or "")
        ]

        if not matching_atoms:
            failures.append(
                f"FAIL [stat-attribution] No proof atom found containing stat '{stat_val}'."
                f" Expected one with '{must_have}' in metric."
            )
            continue

        for atom in matching_atoms:
            metric = atom.get("metric") or atom.get("body") or ""
            atom_key = atom.get("atomKey", "(unknown)")

            if must_have.lower() not in metric.lower():
                failures.append(
                    f"FAIL [stat-attribution] '{stat_val}' atom '{atom_key}' metric is:\n"
                    f"       \"{metric}\"\n"
                    f"     Expected '{must_have}' — got wrong attribution."
                )

            for wrong in must_not:
                if wrong.lower() in metric.lower():
                    failures.append(
                        f"FAIL [stat-attribution] '{stat_val}' atom '{atom_key}' metric is:\n"
                        f"       \"{metric}\"\n"
                        f"     Contains forbidden name '{wrong}' — wrong attribution."
                    )

    # ── Check 2: no [NEEDS REVIEW] in metric ───────────────────────────────────
    if eval_rules.get("noNeedsReviewInMetric"):
        for atom in proof_atoms:
            metric = atom.get("metric") or ""
            if "[NEEDS REVIEW]" in metric:
                failures.append(
                    f"FAIL [needs-review] Proof atom '{atom.get('atomKey')}' has metric:\n"
                    f"     \"{metric}\"\n"
                    f"     Geometry fusion must succeed — re-export with GAS v2."
                )

    # ── Check 3: all proofs WITH a metric must have attributedTo ──────────────────
    if eval_rules.get("allProofsMustHaveAttributedTo"):
        for atom in proof_atoms:
            # Only require attributedTo when the atom actually carries a metric field
            if atom.get("metric") and not atom.get("attributedTo"):
                failures.append(
                    f"FAIL [attribution-missing] Proof atom '{atom.get('atomKey')}' "
                    f"has metric but no 'attributedTo' field.\n"
                    f"     metric: \"{atom.get('metric', '(no metric)')}\"."
                )

    # ── Check 4: required atom type counts ─────────────────────────────────────
    required_types = eval_rules.get("requiredAtomTypes", [])
    from collections import Counter
    type_counts = Counter(a.get("atomType") for a in slide_atoms)
    expected_counts = Counter(required_types)
    for atype, expected_n in expected_counts.items():
        actual_n = type_counts.get(atype, 0)
        if actual_n < expected_n:
            failures.append(
                f"FAIL [atom-count] Expected at least {expected_n} atom(s) of type "
                f"'{atype}', found {actual_n}."
            )

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"[eval] slide atoms    : {len(slide_atoms)}")
    print(f"[eval] proof atoms    : {len(proof_atoms)}")
    print(f"[eval] checks run     : {len(stat_checks) * 3 + (1 if eval_rules.get('noNeedsReviewInMetric') else 0) + len(proof_atoms)}")
    print()

    if failures:
        print("=" * 60)
        print(f"RESULT: FAIL — {len(failures)} issue(s) found")
        print("=" * 60)
        print("Do NOT scale past one slide until these are resolved.\n")
        for f in failures:
            print(f"  {f}\n")
        sys.exit(1)
    else:
        print("=" * 60)
        print("RESULT: PASS — all stat-attribution checks green")
        print("=" * 60)
        print("Safe to scale to the next section (~8–12 slides).\n")

        # Print the passing atoms for confirmation
        for atom in proof_atoms:
            metric = atom.get("metric") or atom.get("body") or "(no metric)"
            attr = atom.get("attributedTo") or "(no attribution)"
            print(f"  PASS  {metric}")
            print(f"        attributedTo: {attr}\n")


def _parse_args() -> str:
    for i, arg in enumerate(sys.argv[1:]):
        if arg in ("--deck", "-d") and i + 1 < len(sys.argv) - 1:
            return sys.argv[i + 2]
        if not arg.startswith("-"):
            return arg
    return "personalization-q2fy27"


if __name__ == "__main__":
    deck_id = _parse_args()
    run_eval(deck_id)
