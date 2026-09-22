#!/usr/bin/env python3
"""
excalidraw_toolkit — build valid .excalidraw files programmatically.

Why this exists: hand-writing Excalidraw JSON (or having an LLM emit it field by
field) reliably produces files that *look* right but fail to open in strict
parsers. The two failure modes that even careful authors miss:

  1. Every element needs a fractional-indexing `index` key (z-order). Omitting it
     makes ExcaliDrawZ throw "invalid order key" on tab-switch.
  2. `appState` must contain EXACTLY five keys. Extra UI-state keys trip strict
     re-reads; missing keys are silently defaulted by some clients but not others.

The fix is a single chokepoint: never construct an element dict by hand. Always
go through `base_element()` (directly or via `rect`/`ellipse`/`diamond`/`text`/
`arrow`/`line`), then `write_excalidraw()`. The required fields live in ONE place,
so no element can forget `strokeStyle`, `index`, `versionNonce`, etc.

Usage:
    from excalidraw_toolkit import rect, text, arrow, write_excalidraw
    els = [rect(0, 0, 160, 80), text(20, 30, 120, 24, "Hello")]
    write_excalidraw(Path("diagram.excalidraw"), els)

Validate a file:
    python3 excalidraw_toolkit.py diagram.excalidraw [more.excalidraw ...]
"""

import hashlib
import json
import sys
from pathlib import Path

# Base62 alphabet ordered the way fractional-indexing expects (digits, A-Z, a-z).
BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

# Fixed timestamp — non-visual field kept constant for byte-stable output.
# NEVER use time.time() here: that would break determinism.
UPDATED_MS = 1_700_000_000_000

FONT = {"hand": 1, "normal": 5, "code": 3}

# ---------------------------------------------------------------------------
# Deterministic hashing
# ---------------------------------------------------------------------------

def _stable_int(*parts):
    h = hashlib.sha1("/".join(str(p) for p in parts).encode()).hexdigest()
    return int(h, 16) % (2**31 - 1) + 1   # Excalidraw seed/nonce in [1, 2^31)


def stable_seed(diagram_id, element_id):
    return _stable_int(diagram_id, element_id, "seed")


def stable_nonce(diagram_id, element_id):
    return _stable_int(diagram_id, element_id, "nonce")


# ---------------------------------------------------------------------------
# Keys & z-order
# ---------------------------------------------------------------------------

def gen_key(i):
    """Fractional-indexing z-order key for element i (1-based), ordered. Supports
    a1..az (1..61) then b01.. (62+); lexicographic order matches array order."""
    if i < 1:
        raise ValueError("gen_key is 1-based")
    if i <= 61:
        return "a" + BASE62[i]
    j = i - 61
    if j > 62 * 62 - 1:
        raise ValueError("too many elements for gen_key")
    hi, lo = divmod(j, 62)
    return "b" + BASE62[hi] + BASE62[lo]


# ---------------------------------------------------------------------------
# Element constructors — every element flows through base_element()
# ---------------------------------------------------------------------------

def base_element(type_, id_, x, y, w, h):
    """Every required field, set once. seed/versionNonce/index are assigned
    deterministically in finalize() once diagram_id is known."""
    return {
        "id": id_, "type": type_,
        "x": x, "y": y, "width": w, "height": h, "angle": 0,
        "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
        "roughness": 1, "roundness": None, "opacity": 100,
        "groupIds": [], "frameId": None, "boundElements": None,
        "updated": UPDATED_MS, "link": None, "locked": False,
        "seed": None, "version": 1, "versionNonce": None,
        "isDeleted": False, "index": None,
    }


def _shape(type_, id_, x, y, w, h, fill, stroke, stroke_width, dashed, roughness):
    el = base_element(type_, id_, x, y, w, h)
    el["backgroundColor"] = fill
    el["strokeColor"] = stroke
    el["strokeWidth"] = stroke_width
    if dashed:
        el["strokeStyle"] = "dashed"
    el["roughness"] = roughness
    return el


def rect(id_, x, y, w, h, *, fill="transparent", stroke="#1e1e1e",
         stroke_width=2, dashed=False, rounded=True, roughness=1):
    el = _shape("rectangle", id_, x, y, w, h, fill, stroke, stroke_width, dashed, roughness)
    if rounded:
        el["roundness"] = {"type": 3}
    return el


def ellipse(id_, x, y, w, h, *, fill="transparent", stroke="#1e1e1e",
            stroke_width=2, dashed=False, roughness=1):
    return _shape("ellipse", id_, x, y, w, h, fill, stroke, stroke_width, dashed, roughness)


def diamond(id_, x, y, w, h, *, fill="transparent", stroke="#1e1e1e",
            stroke_width=2, dashed=False, roughness=1):
    return _shape("diamond", id_, x, y, w, h, fill, stroke, stroke_width, dashed, roughness)


def text(id_, x, y, w, h, content, *, font="hand", font_size=20,
         align="center", color="#1e1e1e"):
    """Standalone text. For right-aligned text, autoResize is forced off so the
    fixed `width` (and thus the alignment) survives — Excalidraw ignores width
    when autoResize is true."""
    el = base_element("text", id_, x, y, w, h)
    el["strokeColor"] = color
    el["text"] = content
    el["originalText"] = content
    el["fontSize"] = font_size
    el["fontFamily"] = FONT[font]
    el["textAlign"] = align
    el["verticalAlign"] = "middle"
    el["lineHeight"] = 1.25
    el["autoResize"] = False if align == "right" else True
    return el


def label(id_, container, content, *, font="hand", font_size=20,
          align="center", color="#1e1e1e", pad=15):
    """Bound text that is positioned inside a container and linked reciprocally.
    Sets containerId on the text element and adds the binding to container's boundElements."""
    cx, cy, cw, ch = container["x"], container["y"], container["width"], container["height"]
    th = round(font_size * 1.25)
    el = base_element("text", id_, cx + pad, cy + ch / 2 - th / 2, cw - 2 * pad, th)
    el["text"] = content
    el["originalText"] = content
    el["containerId"] = container["id"]
    el["fontFamily"] = FONT[font]
    el["fontSize"] = font_size
    el["textAlign"] = align
    el["verticalAlign"] = "middle"
    el["lineHeight"] = 1.25
    el["autoResize"] = None
    el["strokeColor"] = color
    if container["boundElements"] is None:
        container["boundElements"] = []
    container["boundElements"].append({"id": id_, "type": "text"})
    return el


def _linear(type_, id_, points, stroke, stroke_width, dashed, curved, roughness):
    """Shared helper for arrow and line. `points` is a list of absolute [x, y];
    stored relative to points[0]. Element x,y = points[0]; width/height = bbox."""
    x0, y0 = points[0]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    el = base_element(type_, id_, x0, y0,
                      (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1)
    el["strokeColor"] = stroke
    el["strokeWidth"] = stroke_width
    el["points"] = [[p[0] - x0, p[1] - y0] for p in points]
    if dashed:
        el["strokeStyle"] = "dashed"
    if curved:
        el["roundness"] = {"type": 2}
    el["roughness"] = roughness
    return el


def arrow(id_, points, *, stroke="#1e1e1e", stroke_width=2, dashed=False,
          end_head="arrow", curved=False, roughness=1):
    """Free-form arrow through absolute `points`. Stored relative to points[0].
    Pass curved=True for smooth Bezier routing; dashed=True for a dashed stroke."""
    el = _linear("arrow", id_, points, stroke, stroke_width, dashed, curved, roughness)
    el["startArrowhead"] = None
    el["endArrowhead"] = end_head
    el["startBinding"] = None
    el["endBinding"] = None
    el["elbowed"] = False
    return el


def _center(e):
    return (e["x"] + e["width"] / 2, e["y"] + e["height"] / 2)


def _edge_anchor(a, b):
    """Midpoint of a's edge facing b's center (axis with the larger gap wins)."""
    ax, ay = _center(a)
    bx, by = _center(b)
    if abs(bx - ax) >= abs(by - ay):
        x = a["x"] + a["width"] if bx >= ax else a["x"]
        return (x, ay)
    y = a["y"] + a["height"] if by >= ay else a["y"]
    return (ax, y)


def connect(id_, src, dst, *, label=None, dashed=False, end_head="arrow", gap=1):
    """Glued arrow from src to dst, anchored at facing edge midpoints.

    Returns a list containing the arrow element, plus a free-text mid-label
    element when `label` is given. Mutates src/dst boundElements to register
    the arrow id on both ends."""
    sx, sy = _edge_anchor(src, dst)
    ex, ey = _edge_anchor(dst, src)
    el = base_element("arrow", id_, sx, sy, abs(ex - sx) or 1, abs(ey - sy) or 1)
    el["points"] = [[0, 0], [ex - sx, ey - sy]]
    el["startArrowhead"] = None
    el["endArrowhead"] = end_head
    el["startBinding"] = {"elementId": src["id"], "focus": 0, "gap": gap}
    el["endBinding"] = {"elementId": dst["id"], "focus": 0, "gap": gap}
    el["roundness"] = {"type": 2}
    if dashed:
        el["strokeStyle"] = "dashed"
    for shape in (src, dst):
        if shape["boundElements"] is None:
            shape["boundElements"] = []
        shape["boundElements"].append({"id": id_, "type": "arrow"})
    out = [el]
    if label is not None:
        mx, my = (sx + ex) / 2, (sy + ey) / 2
        out.append(text(f"{id_}-label", mx - 60, my - 12, 120, 24, label))
    return out


def line(id_, points, *, stroke="#1e1e1e", stroke_width=2, dashed=False, curved=False, roughness=1):
    """Free-form line through absolute `points`. Stored relative to points[0].
    Pass curved=True for smooth Bezier routing; dashed=True for a dashed stroke."""
    return _linear("line", id_, points, stroke, stroke_width, dashed, curved, roughness)


def group(group_id, elements):
    """Appends group_id to each element's groupIds list and returns the list."""
    for el in elements:
        el["groupIds"].append(group_id)
    return elements


# ---------------------------------------------------------------------------
# Assembly & writing
# ---------------------------------------------------------------------------

def finalize(elements, diagram_id):
    """Assign deterministic z-order keys, seeds, and versionNonces. Raises on
    duplicate element ids (semantic ids must be unique within a diagram).
    Mutates elements in place; all assigned values are deterministic and idempotent."""
    ids = [el["id"] for el in elements]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate element ids: {sorted(dupes)}")
    for i, el in enumerate(elements, start=1):
        el["index"] = gen_key(i)
        el["seed"] = stable_seed(diagram_id, el["id"])
        el["versionNonce"] = stable_nonce(diagram_id, el["id"])
    return elements


def write_excalidraw(path, elements, diagram_id=None):
    """Write a complete .excalidraw file. Top-level key order and the 5-key
    appState match what Excalidraw.com emits on Save — strict parsers depend on it."""
    path = Path(path)
    diagram_id = diagram_id or path.stem
    doc = {
        "type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
        "elements": finalize(elements, diagram_id),
        "appState": {
            "gridModeEnabled": False, "gridSize": 20, "gridStep": 5,
            "lockedMultiSelections": {}, "viewBackgroundColor": "#ffffff",
        },
        "files": {},
    }
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    problems = validate_file(path)
    print(f"wrote {path} ({len(elements)} elements) — " +
          ("OK" if not problems else f"{len(problems)} PROBLEM(S): {problems}"))
    return problems


# ---------------------------------------------------------------------------
# Validator — run before committing / opening a generated file
# ---------------------------------------------------------------------------

EXPECTED_APPSTATE = {"gridModeEnabled", "gridSize", "gridStep", "lockedMultiSelections", "viewBackgroundColor"}
TOPLEVEL_ORDER = ["type", "version", "source", "elements", "appState", "files"]
REQUIRED_ELEMENT_FIELDS = [
    "id", "type", "x", "y", "width", "height", "angle", "version", "versionNonce",
    "seed", "isDeleted", "index", "frameId", "strokeStyle",
]


def validate_key(k):
    """A fractional-indexing key is valid if: lowercase-letter prefix, body at
    least `head_len` chars (head_len = position of prefix in a..z), and the tail
    after the head does not end in '0'."""
    if not isinstance(k, str) or not k or k[0] not in "abcdefghijklmnopqrstuvwxyz":
        return False
    head_len = ord(k[0]) - ord("a") + 1
    body = k[1:]
    if len(body) < head_len:
        return False
    tail = body[head_len:]
    return not (tail and tail.endswith("0"))


def validate_file(path):
    """Return a list of problem strings (empty = valid)."""
    d = json.loads(Path(path).read_text())
    problems = []
    for i, el in enumerate(d.get("elements", [])):
        for fld in REQUIRED_ELEMENT_FIELDS:
            if fld not in el:
                problems.append(f"el[{i}] type={el.get('type')} missing required field: {fld}")
        if "index" in el and el["index"] is not None and not validate_key(el["index"]):
            problems.append(f"el[{i}] invalid index key: {el['index']!r}")
        if el.get("type") == "text" and el.get("textAlign") == "right" and el.get("autoResize", True):
            problems.append(f"el[{i}] textAlign=right needs autoResize=false")
    aps = set((d.get("appState") or {}).keys())
    if aps != EXPECTED_APPSTATE:
        extra = sorted(aps - EXPECTED_APPSTATE)
        missing = sorted(EXPECTED_APPSTATE - aps)
        problems.append(f"appState mismatch — extra: {extra}, missing: {missing}")
    present = [k for k in d.keys() if k in TOPLEVEL_ORDER]
    if present != [k for k in TOPLEVEL_ORDER if k in d]:
        problems.append(f"top-level key order: {present} (expected: {[k for k in TOPLEVEL_ORDER if k in d]})")
    ids = {el["id"] for el in d.get("elements", []) if el.get("id") is not None}
    for i, el in enumerate(d.get("elements", [])):
        for be in (el.get("boundElements") or []):
            if be.get("id") not in ids:
                problems.append(f"el[{i}] {el.get('id')} dangling boundElement: {be.get('id')!r}")
        cid = el.get("containerId")
        if cid is not None and cid not in ids:
            problems.append(f"el[{i}] {el.get('id')} containerId not found: {cid!r}")
        for key in ("startBinding", "endBinding"):
            b = el.get(key)
            if b and b.get("elementId") not in ids:
                problems.append(f"el[{i}] {el.get('id')} {key} elementId not found: {b.get('elementId')!r}")
        if el.get("updated") != UPDATED_MS:
            problems.append(f"el[{i}] {el.get('id')} non-constant updated (nondeterministic)")
    return problems


def _main():
    if len(sys.argv) < 2:
        print("usage: python3 excalidraw_toolkit.py FILE.excalidraw [FILE2 ...]")
        sys.exit(2)
    any_bad = False
    for p in sys.argv[1:]:
        probs = validate_file(p)
        if not probs:
            print(f"OK   {p}")
        else:
            any_bad = True
            print(f"FAIL {p} — {len(probs)} problem(s):")
            for x in probs:
                print(f"       - {x}")
    sys.exit(1 if any_bad else 0)


if __name__ == "__main__":
    _main()
