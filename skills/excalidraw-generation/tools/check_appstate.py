#!/usr/bin/env python3
"""Classify what changed in .excalidraw files: appState/churn vs real edits.

ExcalidrawZ (and excalidraw.com) rewrite a file on every open/save: they grow
`appState`, re-serialize the JSON, bump per-element `version`/`versionNonce`/
`updated`/`seed`, reassign fractional `index` strings, nudge coordinates by
sub-pixels, relabel group-ids, and reorder the `elements` array -- all without
any meaningful change to the drawing. This tool separates that benign churn
from genuine edits (text, colours, geometry, element add/remove, and *grouping
structure*), so you can safely `git checkout` the pure-churn files and commit
only the real ones.

Design principle: WHITELIST the churn fields. Anything not on the ignore list
counts as a real edit. The bias is deliberately safe -- mislabeling churn as
"real" only means it won't be auto-reverted; mislabeling a real edit as "churn"
would revert it and lose work. In particular `groupIds` is NOT churn: a group-id
*label* rename (same members) is benign, but a changed *partition* (a member
enters/leaves a group, or a group forms/dissolves) is a real edit -- so it is
compared structurally, not string-wise.

Deterministic: pure stdlib, no network, no randomness, no clock. Same inputs
(and same --float-eps) always yield the same verdict.

Verdicts (per file):
  UNCHANGED      identical incl. appState -- nothing to do
  APPSTATE-ONLY  elements + files byte-identical; only appState differs
  CHURN-ONLY     elements differ only in churn fields / group-label / order
  REAL-EDIT      a real field, an added/removed element, or the grouping
                 partition changed
  (files may also report ADDED / MISSING / ERROR)

Usage (run from inside the repo that holds the .excalidraw files):
  # triage every modified tracked .excalidraw against HEAD (default)
  python tools/check_appstate.py

  # specific files, working tree vs a given ref
  python tools/check_appstate.py a.excalidraw b.excalidraw --ref HEAD~3

  # compare two files on disk directly (old, new) -- no git needed
  python tools/check_appstate.py --between old.excalidraw new.excalidraw

  # machine-readable
  python tools/check_appstate.py --json

  # revert the pure-churn files (APPSTATE-ONLY + CHURN-ONLY) via git checkout
  python tools/check_appstate.py --revert-churn

  # exit 1 if any file has real edits (for pre-commit hooks / CI)
  python tools/check_appstate.py --fail-on-real
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

# --- churn taxonomy ---------------------------------------------------------

# Per-element fields that change on every save without any semantic meaning.
VOLATILE_FIELDS = frozenset({"version", "versionNonce", "updated", "seed", "index"})

# Numeric geometry fields that may drift by sub-pixels on re-serialization.
# Handled with a tolerance rather than an exact compare.
NUMERIC_FIELDS = frozenset({"x", "y", "width", "height", "angle"})

# `groupIds` is compared structurally (partition), not field-wise; skip it here.
STRUCTURAL_FIELDS = frozenset({"groupIds"})


class GitError(RuntimeError):
    pass


# --- git plumbing -----------------------------------------------------------

def _git(*args: str) -> str:
    res = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout


def modified_excalidraw() -> list[str]:
    """Tracked .excalidraw files that differ from HEAD (staged or unstaged)."""
    out = _git("diff", "--name-only", "HEAD", "--", "*.excalidraw")
    return [p for p in out.splitlines() if p.strip()]


def load_from_ref(path: str, ref: str) -> dict:
    return json.loads(_git("show", f"{ref}:{path}"))


def load_from_disk(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --- comparison core (source-agnostic) --------------------------------------

def partition(doc: dict) -> set[frozenset[str]]:
    """Grouping as a set of element-id sets, invariant to the group-id label.

    Two docs with the same partition are grouped identically even if every
    group-id string differs (a pure relabel). A differing partition means a
    member entered/left a group or a group formed/dissolved -- a real change.
    """
    groups: dict[str, set[str]] = {}
    for el in doc.get("elements", []):
        for gid in el.get("groupIds") or []:
            groups.setdefault(gid, set()).add(el.get("id"))
    return {frozenset(members) for members in groups.values()}


def _numbers_differ(a, b, eps: float) -> bool:
    try:
        return abs(float(a) - float(b)) >= eps
    except (TypeError, ValueError):
        return a != b


def _points_differ(a, b, eps: float) -> bool:
    if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b):
        return True
    for pa, pb in zip(a, b):
        if not isinstance(pa, (list, tuple)) or not isinstance(pb, (list, tuple)) or len(pa) != len(pb):
            if pa != pb:
                return True
            continue
        for ca, cb in zip(pa, pb):
            if _numbers_differ(ca, cb, eps):
                return True
    return False


def _real_field_diffs(old_el: dict, new_el: dict, eps: float) -> list[str]:
    """Fields that differ in a way that is NOT benign churn."""
    diffs: list[str] = []
    for key in set(old_el) | set(new_el):
        if key in VOLATILE_FIELDS or key in STRUCTURAL_FIELDS:
            continue
        ov, nv = old_el.get(key), new_el.get(key)
        if ov == nv:
            continue
        if key in NUMERIC_FIELDS:
            if _numbers_differ(ov, nv, eps):
                diffs.append(key)
        elif key == "points":
            if _points_differ(ov, nv, eps):
                diffs.append(key)
        else:
            diffs.append(key)  # any other differing field is a real edit
    return diffs


def classify(old: dict, new: dict, eps: float = 0.5) -> dict:
    """Return a verdict dict for one old->new .excalidraw comparison."""
    old_els = {e.get("id"): e for e in old.get("elements", [])}
    new_els = {e.get("id"): e for e in new.get("elements", [])}

    added = sorted(set(new_els) - set(old_els))
    removed = sorted(set(old_els) - set(new_els))

    field_changes: dict[str, list[str]] = {}
    for eid in set(old_els) & set(new_els):
        d = _real_field_diffs(old_els[eid], new_els[eid], eps)
        if d:
            field_changes[eid] = d

    partition_changed = partition(old) != partition(new)

    reasons: list[str] = []
    if added:
        reasons.append(f"{len(added)} element(s) added")
    if removed:
        reasons.append(f"{len(removed)} element(s) removed")
    if field_changes:
        n = sum(len(v) for v in field_changes.values())
        reasons.append(f"{n} real field change(s) across {len(field_changes)} element(s)")
    if partition_changed:
        reasons.append("grouping partition changed")

    appstate_changed = old.get("appState") != new.get("appState")
    files_changed = old.get("files") != new.get("files")
    # deep-equal on the raw elements list (order-sensitive) => not even reordered
    elements_identical = old.get("elements") == new.get("elements")

    if reasons:
        verdict = "REAL-EDIT"
    elif not appstate_changed and not files_changed and elements_identical:
        verdict = "UNCHANGED"
    elif elements_identical and not files_changed:
        verdict = "APPSTATE-ONLY"
    else:
        verdict = "CHURN-ONLY"
        churn = []
        if not elements_identical:
            churn.append("element churn (volatile/index/float/group-label/reorder)")
        if files_changed:
            churn.append("files block")
        if appstate_changed:
            churn.append("appState")
        reasons = churn

    return {
        "verdict": verdict,
        "reasons": reasons,
        "added": added,
        "removed": removed,
        "field_changes": field_changes,
        "partition_changed": partition_changed,
        "appstate_changed": appstate_changed,
    }


# --- CLI --------------------------------------------------------------------

PURE_CHURN = {"APPSTATE-ONLY", "CHURN-ONLY"}

_COLORS = {
    "REAL-EDIT": "\033[1;33m",      # yellow
    "APPSTATE-ONLY": "\033[1;32m",  # green
    "CHURN-ONLY": "\033[0;32m",     # green
    "UNCHANGED": "\033[0;90m",      # grey
}
_RESET = "\033[0m"


def _fmt_verdict(v: str, use_color: bool) -> str:
    return f"{_COLORS.get(v, '')}{v}{_RESET}" if use_color else v


def _pairs_from_args(ns):
    """Yield (label, old, new) where old/new are docs or a marker string."""
    pairs = []
    if ns.between:
        old_p, new_p = ns.between
        try:
            pairs.append((f"{old_p} -> {new_p}", load_from_disk(old_p), load_from_disk(new_p)))
        except (OSError, json.JSONDecodeError) as exc:
            pairs.append((f"{old_p} -> {new_p}", None, f"ERROR: {exc}"))
        return pairs

    paths = ns.paths or modified_excalidraw()
    for path in paths:
        try:
            old_doc = load_from_ref(path, ns.ref)
        except (GitError, json.JSONDecodeError):
            old_doc = "ADDED"  # not present in ref => newly added file
        try:
            new_doc = load_from_disk(path)
        except (OSError, json.JSONDecodeError) as exc:
            new_doc = f"ERROR: {exc}"
        pairs.append((path, old_doc, new_doc))
    return pairs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", help="specific .excalidraw files (default: all modified vs HEAD)")
    ap.add_argument("--ref", default="HEAD", help="git ref to compare the working tree against (default: HEAD)")
    ap.add_argument("--between", nargs=2, metavar=("OLD", "NEW"), help="compare two files on disk directly (no git)")
    ap.add_argument("--float-eps", type=float, default=0.5, help="sub-pixel tolerance for geometry (default: 0.5)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--revert-churn", action="store_true", help="git checkout the APPSTATE-ONLY + CHURN-ONLY files")
    ap.add_argument("--fail-on-real", action="store_true", help="exit 1 if any file has real edits")
    ns = ap.parse_args(argv)

    results = []
    for label, old_doc, new_doc in _pairs_from_args(ns):
        if old_doc == "ADDED":
            results.append({"file": label, "verdict": "ADDED", "reasons": ["not present in ref"]})
            continue
        if not isinstance(old_doc, dict) or not isinstance(new_doc, dict):
            msg = next((x for x in (new_doc, old_doc) if isinstance(x, str)), "load failed")
            results.append({"file": label, "verdict": "ERROR", "reasons": [msg]})
            continue
        res = classify(old_doc, new_doc, ns.float_eps)
        res["file"] = label
        results.append(res)

    if ns.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        use_color = sys.stdout.isatty()
        if not results:
            print("No .excalidraw changes vs", ns.ref)
        width = max((len(r["file"]) for r in results), default=0)
        for r in results:
            line = f"  {r['file']:<{width}}  {_fmt_verdict(r['verdict'], use_color)}"
            if r.get("reasons"):
                line += f"  — {'; '.join(r['reasons'])}"
            print(line)

    if ns.revert_churn:
        churn = [r["file"] for r in results if r["verdict"] in PURE_CHURN]
        if churn:
            _git("checkout", "--", *churn)
            print(f"\nReverted {len(churn)} pure-churn file(s): {', '.join(churn)}", file=sys.stderr)
        else:
            print("\nNo pure-churn files to revert.", file=sys.stderr)

    if ns.fail_on_real and any(r["verdict"] == "REAL-EDIT" for r in results):
        return 1
    if any(r["verdict"] == "ERROR" for r in results):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
