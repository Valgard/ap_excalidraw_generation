# Exporting `.excalidraw` to PNG

The toolkit ships a **deterministic PNG exporter** ported from Excalidraw's own
render path (rough.js + `exportToSvg`). No browser, no manual GUI step.

## Primary path — the uv script

```bash
uv run export.py diagram.excalidraw -o diagram.png --scale 2 --background light
```

`uv` reads the pinned dependency (`resvg-py`) from the script header and builds an
isolated env on first run. Output is byte-deterministic for a given file + pinned
toolchain. Or from Python:

```python
from excalidraw import Diagram

d = Diagram("my-diagram")
# ... build diagram ...
d.write("diagram.excalidraw")
d.export_png("diagram.png", scale=2)
```

**Flags:**

- `--scale {1,2,3}` (default `2`) — 2× or 3× for retina output.
- `--background {light|transparent}` (default `light` — the blog convention).

## How it stays deterministic

Geometry is fixed by each element's `seed`; the SVG is pure string generation at
2-decimal precision; `resvg` carries its own text shaping + rasterization (no
system font / AA stack), so the same file + pinned `resvg-py` ⇒ identical PNG
bytes.

This supersedes the earlier "manual GUI, no CLI rasterizer" decision in the
`2026-06-28` design (§8).

## Conventions (match what the blog uses)

- **Light background** (not transparent) for published article diagrams.
- **2×–3× scale** for crisp / retina output.
- For bilingual diagrams, export each language file separately, keeping the stem:
  `ttc-curve-de.excalidraw → ttc-curve-de.png`, `ttc-curve-en.excalidraw → ttc-curve-en.png`.

## Parity — verified vs known limitations

The deterministic exporter faithfully reproduces the following Excalidraw features
as of P14 verification (2026-07-02, 164 unit tests + 15 fixture determinism checks;
run the current suite with `uv run run_tests.py`, which includes the resvg-py-gated
PNG-render tests that a bare `pytest` skips):

**Verified faithful (golden-tested):**

- **Rotation-aware bounds** — arbitrary element rotation (all element types)
- **Curved/bezier line bounds** — geometry ops for curved arrows and connectors
- **Arrow/triangle arrowheads** — `arrow`, `bar`, `triangle`/`triangle_outline`,
  `diamond`/`diamond_outline` on either end; solid fills match Excalidraw exactly
- **Bound text in shapes** — center-aligned label computed from container geometry
- **Freedraw paths** — Catmull-Rom spline through captured pointer points
- **Images** — PNG/SVG embedded as data URI, aspect-ratio preserved
- **Frames** — `name` label rendered above frame (Helvetica metrics); `<clipPath>`
  emitted in `<defs>` (golden parity)
- **Embeddables** — rough-rect placeholder; `<a href>` wrapper with protocol whitelist
  (`http:`, `https:`, `mailto:`) and attribute-injection escaping
- **RTL text** — bidirectional layout, correct alignment direction
- **Z-order** — element stacking/layering matches `elements` array order
- **Per-glyph font fallback** — each text line is ONE `<text>` run (no `<tspan>`
  routing); resvg's native fallback renders any glyph the primary font lacks from the
  loaded Latin-free fallback fonts: color emoji → **Apple Color Emoji**
  (`AppleColorEmoji.ttf`, sbix — proprietary, not bundled: on macOS extract it with
  `uv run --with fonttools python tools/build_fonts.py --apple-emoji`) when present,
  otherwise **Noto Color Emoji**; technical symbols (arrows → ↑ ↓ ←, ∞ ≈ ∼, dingbats
  ✓ ✗ ✘, …) → a Latin-free **DejaVu Sans symbol subset** (`DejaVuSubset.ttf`) and a merged
  **Noto Sans Symbols** font (`NotoSymbols.ttf`, Symbols+Symbols2+Math, ≥U+2000) for rarer
  symbols. Every fallback is Latin-free on purpose — a Latin-covering font in resvg's
  font database can pull a whole hand-drawn run into it. For the same reason, a diagram
  mixing a hand-drawn font with Liberation Sans or Cascadia loads Latin-only subsets of
  those two instead (`SubsetSans.ttf`, `SubsetMono.ttf`, see `fonts.font_file_paths` and
  `fonts.resvg_families`).
- **lineHeight** — per-font metrics (Excalifont, Helvetica, Cascadia); baseline offset
- **Scaffolding cosmetics** — roundness (sharp/proportional/legacy), stroke style
  (solid/dashed/dotted), fill (solid/hatch/cross-hatch), stroke width, opacity
- **Corpus diagrams** — validated on three live blog diagrams (multi-stage pipeline,
  cognitive model, failure-mode taxonomy); all produced valid PNGs at 2× scale

> **Structural comparison:** golden SVGs are compared by viewBox dimensions and path
> counts, not byte-for-byte. Minor floating-point formatting differences are tolerated.

**Known limitations / not-parity-verified (no golden/corpus case):**

- **circle/dot/crowfoot arrowhead fills** — `dot`, `circle`, `circle_outline`,
  and all `cardinality_*` crowfoot variants are implemented but use polygon
  approximations; pixel-level fidelity against Excalidraw's ellipse rendering
  is not verified.
- **line/arrow-bound text `verticalAlign`** — Excalidraw uses `"top"` for labels
  bound to lines/arrows; the exporter defaults to `"middle"` (shape-bound
  corpus-verified); no line-bound-text golden exists.
- **Rotated-frame label centering** — frame name label width uses `frame.width`
  as an approximation (canvas `measureText` unavailable); centering of long
  labels on rotated frames is approximate.
- **Frame child clipping** — `<clipPath>` is emitted in `<defs>` for golden parity
  but is never applied to child elements; populated frames export children
  unclipped (no populated-frame corpus case).

**Tooling note — do not blind-re-mint `frame.svg`:**

`tests/fixtures/svg/frame.svg` (and any fixture that requires canvas `measureText`)
is NOT reproducible via a plain `node tools/mint_fixtures.mjs` run — it was
generated with a `canvas.measureText` mock that returns width = 0 (label width
approximated as `frame.width`). Running `mint_fixtures.mjs` without the mock
will degrade the fixture. If you must re-mint, restore afterwards:

```bash
git checkout tests/fixtures/svg/frame.svg
```

## Fallback — manual GUI export

If `uv` / `resvg-py` is unavailable, export from a real Excalidraw client:

### On Apple platforms — ExcalidrawZ (recommended)

[ExcalidrawZ](https://github.com/chocoford/ExcalidrawZ) is a native Excalidraw
client for macOS / iPadOS / iOS (App Store or `.dmg`). It opens the files this
toolkit produces directly — it is the strict client whose validator the format
rules target, so a file that validates here opens cleanly there.

Export: open the `.excalidraw` file, trigger the export-image / share action, and
choose **PNG**. ExcalidrawZ embeds Excalidraw's own export dialog, so the
background and scale options above apply.

### On any platform — excalidraw.com or the Excalidraw Desktop app

For colleagues not on Apple hardware (ExcalidrawZ is Apple-only), the
cross-platform equivalent gives the identical export:

1. Open <https://excalidraw.com> (or the official Excalidraw Desktop app).
2. Drag the `.excalidraw` file onto the canvas (or main menu → **Open**).
3. Main menu → **Export image…** (or the export icon).
4. In the export dialog:
   - **Background**: ON → light background (the blog convention). OFF → transparent.
   - **Scale**: 2× or 3× for crisp / retina output.
   - **Format**: PNG.
5. Save.
