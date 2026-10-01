---
name: excalidraw-generation
description: Use when programmatically creating, generating, or scripting .excalidraw diagram files (Excalidraw JSON) from code instead of drawing by hand — e.g. building diagrams for articles, slides, docs, or reports, or when you need to export such a diagram to PNG. Covers the format rules that make files open cleanly in Excalidraw.com and local clients (ExcalidrawZ), ships a Python toolkit + validator, and documents PNG export.
---

# Generating Excalidraw Diagrams

## Overview

Hand-writing Excalidraw JSON — or having an LLM emit it field by field — reliably
produces files that *look* correct but break in strict parsers. The format has
non-obvious required fields with no renderer fallbacks. This skill ships a small
Python toolkit that encodes every rule in one place, so generated files open
cleanly in both Excalidraw.com and ExcalidrawZ (local Apple client).

**Core principle: never construct an element dict by hand.** Build every shape
through the `Diagram` facade (or the underlying toolkit helpers), which route
through a single `base_element()` factory that sets all required fields. Then
`d.write(path)` assembles the document, validates it, and returns the list of
problems — an empty list means a valid file. The fields can't be forgotten because
no element sets them individually.

## When to use

- Generating `.excalidraw` files from a script (diagrams for articles, slides, docs)
- Producing many diagrams or multiple language variants of the same diagram
- Any time you'd otherwise write Excalidraw JSON with a file-write tool

**When NOT to use:** drawing a one-off diagram by hand in the Excalidraw UI (just
draw it), or editing an existing complex hand-drawn file (open it in the app).

## Why a toolkit and not direct JSON

A capable agent asked to emit Excalidraw JSON directly still misses the
non-intuitive fields. Measured baseline (3 boxes + 2 arrows, no toolkit): **all
elements missing the `index` z-order key, and `appState` with 2 of 5 required
keys** — a file that opens once, then throws `invalid order key` on tab-switch.
The toolkit closes exactly these gaps. Don't reconstruct the format from memory.

## Architecture — three layers

### Layer 1: `Diagram` facade (primary entry point)

`excalidraw.py` is the recommended interface. Instantiate with a semantic
diagram id, call builder methods, write:

```python
from excalidraw import Diagram

d = Diagram("my-diagram")          # semantic id seeds deterministic nonces
a = d.box("node-a", 0, 0, 160, 60, text="Input")
b = d.box("node-b", 320, 0, 160, 60, text="Output")
d.connect("a-to-b", a, b, label="transforms", dashed=True)
problems = d.write("diagram.excalidraw")   # [] = valid
```

**Primitive methods** (`box`, `ellipse`, `diamond`, `text`, `line`, `arrow`)
return the element dict — pass it to `connect`/`label`/`group` as a handle.
`text` on a shape (`d.box(..., text="...")`) emits an overlay label automatically.
Relations (`connect`, `label`, `group`) are optional — a diagram of free shapes is
perfectly valid.

**Determinism rule:** Element ids are semantic strings (`"node-a"`, `"flow"`).
The toolkit derives content-hashed `seed` and `versionNonce` values from these ids
so the same diagram id + element ids always produce bit-identical output. Never
pass raw JSON between sessions — regenerate from the script.

### Layer 2: layout and chart helpers

`excalidraw_helpers.py` provides higher-level composite builders, all accessible
as methods on `Diagram`:

| Method | What it builds |
|--------|----------------|
| `d.panel(prefix, title, rows, fill, accent, x, y)` | card with title + bound row labels |
| `d.flow(prefix, labels, ...)` | horizontal row of boxes with gap spacing |
| `d.grid(prefix, rows, cols, ...)` | regular grid; returns center-point dict |
| `d.columns(prefix, headers, rows, ...)` | table-style column layout |
| `d.timeline(prefix, points, ...)` | horizontal baseline + labeled dots |
| `d.axes(prefix, ox, oy, width, height)` | x/y axis lines with tick marks |
| `d.bars(prefix, data, ...)` | bar chart from `{label: value}` dict |
| `d.curve(prefix, fn, t0, t1, n, ox, oy, sx, sy, stroke)` | polyline from a function `f(t) → y` |
| `d.histogram(prefix, values, ...)` | frequency histogram |

Each helper returns a primary handle (element dict or list of element dicts) so
the result can be passed to `connect` as a source or target.

### Layer 3: raw toolkit (extension and validation)

`excalidraw_toolkit.py` exports the low-level free functions (`rect`, `ellipse`,
`diamond`, `text`, `line`, `arrow`, `label`, `connect`, `group`,
`write_excalidraw`) and the validator (`validate_file`). Use this layer when
extending the toolkit with new element types or when you need the free functions
directly. Do not call `base_element()` outside the toolkit.

**Re-validate any file** (after a manual edit, or for a legacy file):
```bash
python3 excalidraw_toolkit.py diagram.excalidraw
```

## Worked examples

Three complete, runnable examples live in `examples/`:

| File | Demonstrates |
|------|-------------|
| `examples/structured_flow.py` | `panel` composite + dashed labeled connector |
| `examples/illustration.py` | free primitives (`box`, `ellipse`), `group`, free-arrow bridge |
| `examples/chart.py` | `axes` + `curve` with a mathematical function |

Each exposes `make() -> Diagram` and runs standalone:
```bash
python3 examples/structured_flow.py    # writes structured_flow.excalidraw
```

## Style layer

The toolkit ships two production styles — **Sketch** and **Minimal** — built on
shared color atoms and typography. A diagram's content type (flow, chart, card,
etc.) is independent of its visual style; the caller chooses which one at
generation time. The color system is defined in `excalidraw_palette.py` (atoms:
`PALETTE`, `SEMANTIC`, `role()`, plus constants `FONT`, `TITLE`, `SUBTITLE`).
Archetype-specific styling guidance and conventions live in `style-guide.md`, which
documents both the base atom semantics and per-style design patterns.

## Quick reference — the six format rules

| # | Rule | Enforced by |
|---|------|-------------|
| 1 | `index` is a fractional-indexing key (tail must not end in `0`) | `gen_key()` / `finalize()` |
| 2 | `appState` has EXACTLY 5 keys | `write_excalidraw()` |
| 3 | `textAlign: "right"` requires `autoResize: false` | `text()` |
| 4 | Top-level key order: `type, version, source, elements, appState, files` | `write_excalidraw()` |
| 5 | Every element has all required fields (esp. `strokeStyle`, `index`, `versionNonce`) | `base_element()` |
| 6 | Python string delimiters when labels contain ASCII quotes | author discipline (see reference) |

Full rationale and the complete required-field table: **format-reference.md**.

## Exporting to PNG

The toolkit ships a **deterministic PNG exporter** — no browser, no manual GUI step
required. Primary path:

```bash
uv run export.py diagram.excalidraw -o diagram.png --scale 2 --background light
```

Or from Python: `Diagram(...).export_png("diagram.png", scale=2)`.
`--scale {1,2,3}` (default 2) and `--background {light|transparent}` (default
light). If `uv`/`resvg-py` is unavailable, fall back to the manual GUI export
(ExcalidrawZ on Apple, excalidraw.com anywhere). Full details, flags, and
determinism explanation: **png-export.md**.

## Running tests

Canonical command — runs the whole suite with the render-test dependencies present:

```bash
uv run run_tests.py            # full suite; -q, -k, etc. pass through to pytest
```

`run_tests.py` is a PEP-723 uv script whose inline deps (pytest, resvg-py, Pillow,
numpy, fontTools, brotli) are managed via `uv add --script run_tests.py <pkg>`. Use it
rather than a bare `python -m pytest`: the PNG-render tests (`test_emoji_rendering`,
`test_symbol_fallback`) import `resvg_py` and otherwise **skip** — a bare run leaves
them un-exercised (they once hid a broken render test behind a skip). Bare pytest still
works for the pure-stdlib tests; the render tests just skip gracefully.

## Triaging edits after opening in a client

Opening a generated `.excalidraw` in a client (ExcalidrawZ, excalidraw.com) — even
just to look, or to re-export a PNG — rewrites the file on save: `appState` grows
back the UI-state keys the format trims to 5 (rule 2), every element's
`version`/`versionNonce`/`seed` bumps, fractional `index` keys and group-id labels
are reassigned, coordinates drift sub-pixel, and the `elements` array is reordered.
So `git` shows a large diff even when the drawing did not change — and a genuine
edit (new text, a moved box, a regrouping) hides inside that churn.

`tools/check_appstate.py` classifies each file so you commit real edits and discard
the noise. Deterministic (stdlib only); compares the working tree against a git ref
(default `HEAD`):

```bash
python tools/check_appstate.py                  # triage every modified .excalidraw
python tools/check_appstate.py --revert-churn    # git checkout the pure-churn files
python tools/check_appstate.py --between a b      # two files directly, no git
```

Verdicts **APPSTATE-ONLY** (only `appState` differs) and **CHURN-ONLY** (only churn
fields / group-id labels / order) are safe to revert; **REAL-EDIT** flags a changed
field, an added/removed element, or a changed grouping *partition* — a member
entering or leaving a group counts, a group-id label rename does not. The bias is
deliberately safe: anything not on the known churn whitelist is treated as a real
edit, so `--revert-churn` never discards work.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Writing element JSON directly with a file tool | Use the toolkit — `base_element()` is the only safe path |
| Forgetting `index` keys | `write_excalidraw()` calls `finalize()`; never set `index` by hand |
| Adding extra `appState` keys (zoom, theme…) | Leave appState to `write_excalidraw()` — exactly 5 keys |
| Right-aligned text not aligning | Already handled by `text(align="right")`; if hand-editing, set `autoResize: false` |
| >61 elements with `gen_key` | It raises; switch to a `b`-prefix key scheme (see reference) |
| Python syntax error from a `"` inside a label | Single-quote the Python string; `ast.parse` before running |

## Files in this skill

- `excalidraw.py` — `Diagram` facade (primary entry point)
- `excalidraw_helpers.py` — layout and chart helper builders (`panel`, `flow`, `axes`, `curve`, …)
- `excalidraw_toolkit.py` — low-level free functions + `write_excalidraw()` + validator (also a CLI)
- `excalidraw_palette.py` — color atoms (`PALETTE`, `SEMANTIC`, `role()`) and typography constants (`FONT`, `TITLE`, `SUBTITLE`)
- `roughjs.py` — faithful rough.js 4.6.x geometry port (RNG, lines, rectangle, ellipse, curve, path, solid fill, ops_to_path)
- `fonts.py` — Excalidraw font mapping + metrics + base64 `@font-face` embedding
- `excalidraw_shape.py` — element → rough options + drawable OpSets + arrowheads
- `excalidraw_svg.py` — element document → deterministic SVG string
- `export.py` — uv script: SVG → PNG via pinned `resvg-py` + CLI entry point
- `tools/check_appstate.py` — classify `.excalidraw` diffs after a client rewrite (appState/churn vs real edits); deterministic, stdlib, CLI
- `font_files/` — bundled TTF fonts (Excalidraw text fonts, emoji and symbol fallbacks) + licenses; the proprietary Apple Color Emoji is not bundled — on macOS extract it with `uv run --with fonttools python tools/build_fonts.py --apple-emoji`, otherwise emoji render with Noto Color Emoji
- `examples/structured_flow.py` — panels + dashed labeled connector
- `examples/illustration.py` — free primitives + group + free-arrow bridge
- `examples/chart.py` — axes + function curve
- `format-reference.md` — full format spec, required-field table, binding fields, debugging tips
- `style-guide.md` — color system conventions, base atoms, Sketch and Minimal style patterns by archetype
- `png-export.md` — how to export a `.excalidraw` file to PNG (uv script primary, manual GUI fallback)

## Sharing

Self-contained: only the Python standard library is required (no pip installs).
Copy the whole `excalidraw-generation/` folder into another person's skills
directory, or keep the `.py` files together in any project and `import` from the
toolkit.
