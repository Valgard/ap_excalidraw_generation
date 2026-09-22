# Excalidraw Export Fidelity — 1:1 Python Port Design

**Date:** 2026-07-02
**Status:** Design (brainstorming output) — pending user review
**Component:** `excalidraw-generation` skill, branch `excalidraw-export` (a dedicated worktree)
**Supersedes/extends:** `docs/specs/2026-07-01-excalidraw-deterministic-export-design.md`

## Goal

A pure-Python `.excalidraw` → PNG exporter that reproduces Excalidraw/ExcalidrawZ's own
export output. Exported PNGs must match the original article PNGs in **form, layout,
colour, font, position** — not pixel-exact, but visually faithful.

## Requirements (verbatim from author)

1. A 1:1 Python port of the Excalidraw export.
2. Settings from the `.excalidraw` files are taken over 1:1.
3. Exported PNGs must match the original PNGs in form/layout/colour/font/position/etc.
   (not pixel-exact).
4. The export port should behave exactly like the ExcalidrawZ export.
5. The export port accepts the same settings as the Excalidraw export.
6. Default export values are defined so the export works without further configuration.

## Success criterion (resolved 2026-07-04)

Author confirmed the article PNGs now match the current sources (drift fixed), making them
authoritative ExcalidrawZ output. Byte- and pixel-exact PNG identity to ExcalidrawZ was
requested but is **technically incompatible with pure Python** (proven below), so the
criterion is split:

- **Primary (port correctness, machine-checkable): byte-exact SVG** vs. `@excalidraw/utils`
  `exportToSvg` for the same source — geometry, path `d` data (incl. number formatting),
  element order, positions, structure. This is the concrete "1:1 port" target.
- **Secondary (PNG): visually faithful** — the resvg rasterisation of that SVG matches the
  original PNG in form/layout/colour/font/position/dimensions; edge anti-aliasing differences
  are accepted. **Not** pixel- or byte-exact.

### Why pixel/byte-exact PNG is impossible in pure Python (measured)

For `four-phases-de` (scale 1): our render's dimensions are **exact** (1173×359, matching
ExcalidrawZ). But the PNG cannot match byte- or pixel-exact:

- **Encoder differs (byte):** original chunks `IHDR, sRGB, eXIf, IDAT×8, IEND` vs. resvg
  `IHDR, IDAT, IEND`. Different PNG encoders → different bytes even for identical pixels.
- **Rasteriser differs (pixel):** ExcalidrawZ = WKWebView (WebKit/CoreGraphics canvas); we =
  resvg/tiny-skia. With matched transparent background, 9.4% of pixels differ (PSNR 25 dB) —
  **entirely at shape borders, glyph edges and lines** (a diff image shows fills/structure
  identical, only edges red). This is anti-aliasing + font-hinting divergence, unavoidable
  without WebKit's own rasteriser. No Python library replicates CoreGraphics text rendering.

Byte/pixel-exactness lives at the rasteriser+encoder layer, below what a geometry port
controls. Achieving it would require rendering **in** ExcalidrawZ/WKWebView — contradicting
the pure-Python requirement. Author chose pure-Python + visually-faithful + byte-exact-SVG.

**Caveat on byte-exact SVG:** resvg's usvg CSS parser constrains font-family attributes
(single-token families, no unquoted multi-word/numeric names). Where this forces a deviation
from `@excalidraw/utils`'s exact `font-family` string, it is a documented,
semantically-neutral exception; byte-exactness is asserted on geometry/structure/positions.

## Non-Goals

- Pixel- or byte-exact PNG identity to ExcalidrawZ (proven impossible in pure Python — above).
- Node/browser at **runtime** (see Architecture). Node is dev-time only.
- Re-styling or redesigning diagram sources (that is content work, not the exporter).

## Architecture: runtime vs. dev-time

| | Runtime (shipped) | Dev-time (testing only) |
|---|---|---|
| Language | **Pure Python** | Node allowed |
| Pipeline | `excalidraw_svg.to_svg` (Python) → `resvg-py` (Python pkg, Rust rasteriser) → PNG | `@excalidraw/utils` `exportToSvg` (jsdom, headless) → reference SVGs |
| Role | The actual exporter | Golden-fixture **oracle** to verify the port against |
| Fonts | pre-converted TTFs bundled in `font_files/` (no conversion at runtime) | — |

**Node never runs at export time.** `tools/mint_fixtures.mjs` (`@excalidraw/utils`) exists
solely to mint reference SVGs the Python port is verified against.

### Dev-time oracle is an approximation, not ground truth

`@excalidraw/utils` shares Excalidraw's export **code**, but the headless mint is NOT
byte-identical to ExcalidrawZ's in-app export: (a) version skew (ExcalidrawZ bundles build
`2026-06-30…14256cc31`; our `@excalidraw/utils` is `0.1.3-test32`), (b) headless jsdom +
Path2D-polyfill + no loaded fonts vs. a real WKWebView, (c) the mint embeds no `@font-face`.
**rough.js geometry is deterministic and matches regardless of environment.** The true
ground truth remains the **original article PNGs** (rendered by ExcalidrawZ in-browser);
the reference SVGs are a close, geometry-exact approximation used for structural checks.

## Font layer — source of truth = ExcalidrawZ's own fonts

All fonts are taken from ExcalidrawZ (`/Applications/ExcalidrawZ.app/Contents/Resources/excalidraw-latest/`),
which produced the originals. woff2 → TTF conversion (fontTools + brotli) is a **one-time
build step**; the resulting TTFs are bundled in `font_files/`. resvg cannot decode woff2,
hence TTF.

| FONT_FAMILY code | Font | Source | Notes |
|---|---|---|---|
| 1 | Virgil | top-level `Virgil.woff2` | **Already correct** — our bundled `Virgil.ttf` is byte-identical (same 534 outlines, v001.001); only the internal family name was renamed to a single token for usvg. No change needed beyond keeping it. |
| 2 | Liberation Sans | `fonts/LiberationSans/` | For completeness (Helvetica fallback); not in corpus. |
| 3 | Cascadia | top-level `Cascadia.woff2` (full, 1548 glyphs) | Prefer the full top-level file over the subset. |
| 5 | Excalifont | `fonts/Excalifont/*.woff2` (7 subsets) | **Merge all 7 subsets → one full TTF (573 glyphs).** Current bundle is only one 217-glyph subset — glyphs outside it silently fall back. |
| 6/7/8 | Nunito / Lilita / Comic Shanns | `fonts/…` | For completeness; not in corpus. |
| — | NotoColorEmoji | local TeXLive `NotoColorEmoji.ttf` | Bundle pinned for emoji (🎯 ✅ ✘ …). Verify resvg renders colour emoji (COLR/CBDT) during implementation. |

**font-family strings:** match real Excalidraw (`Virgil, Segoe UI Emoji` /
`Excalifont, Xiaolai, Segoe UI Emoji` / `Cascadia, Segoe UI Emoji`); drop the stray
`sans-serif` we currently append.

**Per-glyph fallback:** a glyph missing from the primary font (e.g. `→` is absent even from
the full 573-glyph Excalifont; emoji absent from all text fonts) must fall back **per glyph**
(→ Cascadia; emoji → NotoColorEmoji) without displacing the surrounding run to the fallback
font. Feed all bundled TTFs to `resvg_py.svg_to_bytes(font_files=…, skip_system_fonts=True)`.

### Finding A (code-1 "font wrong") is refuted

Reported for cost-flip / mapping-tabelle / threat-model. Investigation: our `Virgil.ttf`
has **byte-identical glyph outlines** to ExcalidrawZ's `Virgil.woff2`; resvg selects it
correctly (render with our family string == render with plain `Virgil`, byte-for-byte);
cost-flip code-1 text matches the original visually. The earlier "too heavy" impression was
the 3× render scale on the A/B page. **No Virgil font bug exists.** Any residual code-1
discrepancy is text **position** (class B), not font.

## Fill layer — port rough.js hachure & cross-hatch (class F)

Current port implements only `solid_fill_polygon`; `fillStyle` is read but every fill is
rendered solid. Proven divergence: hachured boxes emit far fewer `M` path commands than real
(locomo −73, static-vs-inplace −201).

- Port rough.js `hachureFillShape` / `patternFillPolygons` (hachure line generator honouring
  `fillWeight`, `hachureGap`, `hachureAngle`), and cross-hatch (two hachure passes).
- Dispatch in `_with_fill` by `fillStyle`: `solid` → existing solid filler; `hachure` →
  hachure; `cross-hatch` → cross-hatch. (zigzag/dots only if a corpus source needs them.)
- Respect transparent background: `backgroundColor: transparent` → no fill (verified: some
  boxes are transparent in the originals but currently rendered filled).

## Arrowhead layer (class C)

Dashed and `roundness: 2` arrows render broken/short arrowheads (proven: arrow-diagram `d`
length diverges — memgpt −716, atkinson −1592 — with matching path counts). Correct the
arrowhead geometry for `strokeStyle: dashed` and rounded (`roundness type: 2`) arrows to
match `@excalidraw/utils` output, verified per-arrow against the reference SVGs.

## Text-position layer (class B)

13/102 diagrams show text-position divergence vs. the reference SVGs (up to 16.6px; e.g.
generative-agents, memory-governance, delegation-layers, consistency-metrics, atkinson
"KI-Parallelen", user-segmentation). Align the port's text baseline / positioning with
Excalidraw's computation. Note the user-segmentation shift is compounded with class D
(dropped emoji altering text metrics) — fixing D removes part of B.

## Options API (requirements 2, 5, 6)

`ExportOptions` mirrors Excalidraw's `exportToSvg` options:

- `exportBackground: bool` — draw background rect or transparent
- `viewBackgroundColor: str` — background colour when `exportBackground`
- `exportPadding: int` — padding around scene bounds (Excalidraw default 10)
- `exportScale: float` — zoom multiplier (Excalidraw default 1)
- `exportWithDarkMode: bool` — dark theme
- `exportEmbedScene: bool` — embed the source scene in SVG metadata (optional)

**Precedence chain (the core rule):** explicit caller argument **>** the `.excalidraw`
file's `appState` value **>** hard default.

- Req 2: absent an explicit argument, each option inherits the file's `appState`
  (`viewBackgroundColor`, `exportBackground`, `exportWithDarkMode`, `exportPadding`,
  `exportScale`).
- Req 5: any option can be overridden per call (function kwargs and CLI flags), exactly as
  Excalidraw's `exportToSvg` opts override `appState`.
- Req 6: hard defaults (Excalidraw-conformant: `exportPadding=10`, `exportScale=1`,
  `exportBackground=true`, `viewBackgroundColor=#ffffff`, `exportWithDarkMode=false`) so a
  bare `export.py file.excalidraw` works.

`render_png` / `to_svg` and the CLI expose the full set.

## Verification

1. **Primary — byte-exact SVG** (dev-time, machine-checkable): our `to_svg` vs. minted
   `@excalidraw/utils` reference SVGs across all 102 sources. Compare the normalised SVG:
   path `d` data (incl. number formatting), element order, text positions, attributes,
   structure — targeting byte identity (modulo the documented font-family caveat). This is
   the hard "1:1 port" gate. Count-only checks are insufficient (a hachure and a solid box
   share element counts); compare `d` content (e.g. `M`-command count as a hachure detector).
2. **Secondary — visual PNG near-match**: rendered PNG (transparent bg to match originals'
   RGBA) vs. original article PNG for all 102 — form/layout/colour/font/position/dimensions
   match; edge anti-aliasing differences accepted. Use ImageMagick `compare` (AE/PSNR) as a
   regression signal, not a pass/fail threshold at pixel level.
3. Since the source↔PNG drift is fixed, the original PNGs are authoritative; no G/H
   reclassification is needed anymore.

## PNG regeneration

The source↔PNG drift is already fixed by the author (existing `assets/` PNGs are current
ExcalidrawZ output). So mass regeneration is **not** required to correct drift, and the
classes G (restore source) and H (re-export stale PNG) are moot.

The exporter's role is Python-native PNG generation **going forward** (new/edited diagrams
without opening ExcalidrawZ). Whether to replace the existing WebKit-rendered PNGs with
resvg-rendered ones is the author's call — it would swap WebKit edge-AA for resvg edge-AA
(visually faithful, not identical), so the default is to leave existing PNGs untouched and
use the exporter for new work.

## Findings roll-up (24 reported → classified)

- **F** (fill): locomo-benchmark, static-vs-inplace-ttt.
- **C** (arrowheads): memgpt-tiers, atkinson-shiffrin.
- **B** (position): atkinson "KI-Parallelen", user-segmentation (+D), generative-agents,
  memory-governance, delegation-layers, consistency-metrics.
- **D** (emoji/coverage): ~14 sources; + Excalifont subset-completion; + per-glyph fallback.
- **A** (Virgil font): **refuted** — font correct; residuals are B.
- **G/H** (source drift / stale PNG): **resolved** by the author's drift fix (2026-07-04);
  originals now match current sources. No exporter or source work needed.
- Overturned non-bugs: #15 reflexion near-white bg (correct), #17 DPI-only, #18 trap-framework
  dark fills (correct; only its emoji drop is real).
