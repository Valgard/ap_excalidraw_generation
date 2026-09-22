# Design: Deterministic `.excalidraw` → PNG export ported from the Excalidraw source

- **Date:** 2026-07-01
- **Status:** Proposed (brainstorming) — pending user review → implementation plan
- **Scope:** Skill repository (standalone, shareable). Adds a rendering path alongside the existing stdlib-only generation toolkit. New PNG path is delivered as a **`uv` script** with pinned dependencies; the generation core stays stdlib-only and untouched.
- **Supersedes:** `2026-06-28-excalidraw-deterministic-generation-design.md` **§8 "PNG export"** ("Unchanged: a manual GUI export … No CLI rasterizer is bundled"). That decision is reversed here.

## Context

The current skill writes `.excalidraw` source deterministically (the 2026-06-28 rebuild), but turning a file into the PNG that articles/slides actually embed is a **manual GUI step** — open the file in a real Excalidraw client, click *Export image → PNG*. `png-export.md` justifies this: faithful rendering was assumed to require Excalidraw's own engine (a browser, or jsdom in Node), which is too heavy to ship in a shareable skill.

This design breaks that assumption. Instead of *driving* Excalidraw's renderer, we **port the render path from the source** into an own function: element → rough.js geometry → SVG → rasterize. The manual step disappears; the export becomes scriptable, CI-friendly, and reproducible.

Two facts, verified against the actual source, make a *byte-faithful* port feasible:

1. **The element `seed` is already rough.js-compatible.** `excalidraw_toolkit.py:48` derives `seed` deterministically from `diagram_id + element_id` in `[1, 2³¹)` — exactly what rough.js consumes. Geometry is therefore a pure function of the file.
2. **rough.js' seeded PRNG is a Park-Miller MINSTD** (verified from `rough-stuff/rough` `src/math.ts`):
   ```js
   next() { return ((2**31 - 1) & (this.seed = Math.imul(48271, this.seed))) / 2**31; }
   ```
   This ports to Python exactly (32-bit multiply mod 2³², then a 31-bit mask). Excalidraw vendors **rough.js `4.6.4`** (verified from `packages/excalidraw/package.json`) — the pinning reference for the port.

A browser export can *never* be byte-deterministic across machines (system Freetype version, font hinting, sub-pixel AA all drift). A ported pipeline + a rasterizer that carries its own shaping/raster engine can.

## Goal

Give the skill an **own deterministic `.excalidraw` → PNG export function**, faithful to Excalidraw's source, that replaces the manual GUI step for the diagrams the toolkit produces.

## Goals

- **PNG end artifact, delivered as a `uv` script.** `uv run export.py diagram.excalidraw -o diagram.png` produces the PNG blogs embed. Dependencies are allowed and **pinned** via PEP-723 inline metadata (`uv` builds an isolated, reproducible env).
- **Faithful to the source.** Port rough.js 4.6.4's seeded geometry + Excalidraw's `exportToSvg` element mapping. Output matches what excalidraw.com / ExcalidrawZ render for the same file (hand-drawn look preserved, default `roughness=1` correct).
- **Deterministic under a pinned toolchain.** Same file + same `uv` lock + same `resvg` build ⇒ same PNG bytes, practically OS-independent (resvg carries its own shaping + raster; no system font/AA stack).
- **Generation core stays stdlib-only.** The rendering path is decoupled: `excalidraw.py` / the toolkit never import a rasterizer. The SVG layer is *also* stdlib-only — only PNG rasterization pulls `resvg-py`.

## Non-Goals

- **Not a general Excalidraw renderer.** Only the element vocabulary the toolkit emits (see §6). No freedraw, images, frames, embeds.
- **Not hachure/cross-hatch fill.** The toolkit hardcodes `fillStyle: "solid"` (`base_element`); only solid fill is ported. Hachure is deferred until the toolkit exposes it.
- **Not a browser/Node dependency.** We port the algorithm; we do not drive `@excalidraw/utils` at runtime (it is used *once*, offline, only to mint golden reference fixtures — see Testing).
- **Not cross-rasterizer byte-identity.** Determinism is guaranteed *for a pinned resvg build*, not for arbitrary rasterizers. (Glyph-vectorization would buy that but was rejected as out of scope — see Risks.)

## Design

### 1. Module layout & boundaries

Three new modules + a bundled font directory. The existing toolkit / `Diagram` core is **unchanged and stays stdlib-only** — generation and rendering are decoupled.

| File | Deps | Responsibility |
|------|------|----------------|
| `roughjs.py` | **stdlib** | Faithful port of rough.js 4.6.4: `Random` (verified MINSTD PRNG) + exactly the ops our element set needs — `line`, `rectangle`, `ellipse`, `linearPath`, `curve`, `solidFill`. Returns op-sets (`move`/`line`/`bcurve`) serialized to an SVG path `d` string. No knowledge of Excalidraw. |
| `excalidraw_svg.py` | **stdlib** | Port of Excalidraw's `exportToSvg`: element dict → SVG. Calls `roughjs` with Excalidraw's `generateRoughOptions` defaults, computes the scene bounding box + export padding, emits shape `<path>`s, `<text>` with embedded `@font-face` (base64 OFL fonts), arrowheads, dashed strokes. **This layer alone produces deterministic SVG** and pulls no third-party deps. |
| `export.py` | **`resvg-py` (uv-pinned)** | The `uv` script (PEP-723 header). CLI + importable `render_png()`: load `.excalidraw` JSON → `excalidraw_svg.to_svg()` → resvg rasterize at scale → write PNG. |
| `fonts/` | — | The three OFL fonts + their licenses (see §5). |

**Bridge for the generation API (optional, thin):** a `Diagram.export_png(path, **opts)` convenience that **shells out** to `uv run export.py` rather than importing `resvg-py`, so the stdlib-only guarantee of `excalidraw.py` is preserved.

### 2. Data flow

```
.excalidraw file (or Diagram in memory)
   → parse elements
   → per element: map to rough options → roughjs seeded ops → SVG nodes
        text → <text> + @font-face embed
   → assemble <svg viewBox=…> (scene bbox + padding, background rect if opaque)
   → [resvg @ scale]                     ← only step with a third-party dep
   → PNG bytes → file
```

CLI flags mirror Excalidraw's export dialog: `--scale {1,2,3}` (default 2), `--background {light|transparent}` (default light), `-o OUT` (default: input stem + `.png`).

### 3. Faithfulness strategy (the core risk — validated against the real source)

- **Pin the port** against rough.js `4.6.4` and Excalidraw `master`'s `generateRoughOptions` + `exportToSvg` / `renderElementToSvg`. The exact option constants (bowing, `hachureGap` — unused here, `disableMultiStroke`, `preserveVertices`, dashed `strokeLineDash = [12,8]`, etc.) are read from the pinned source during implementation.
- **Port the verified RNG** (Park-Miller MINSTD). This is what makes the jitter reproducible from `element.seed`.
- **Validate by golden fixtures, not by eye.** Once, offline, generate **reference SVGs** from the real `@excalidraw/utils` (`exportToSvg`, Node — a one-time authoring step, never a runtime dependency) for a fixture set covering every element type/variant. Commit them. Our `to_svg()` must match each reference — path `d` equality within a float epsilon, or structural equivalence. This proves faithfulness against the *actual* source and catches any option-constant we got wrong.

### 4. Determinism strategy

- **Geometry** — fixed by `element.seed` (the toolkit is already deterministic here).
- **SVG** — pure string generation with a fixed float precision and a stable attribute order ⇒ byte-stable output.
- **PNG** — `resvg-py` pinned via `uv`'s PEP-723 block. resvg carries its own text shaping (rustybuzz) + rasterization, bypassing system Freetype/fontconfig ⇒ same version + same bundled font = byte-stable, practically OS-independent.
- **Fonts embedded** as base64 in the SVG so the SVG is self-contained and resvg resolves them deterministically (no font lookup by name).

### 5. Fonts

The toolkit emits only `fontFamily ∈ {1, 5, 3}` (`FONT = {"hand": 1, "normal": 5, "code": 3}`). The mapping is **verified against Excalidraw's `FONT_FAMILY` registry** (`packages/common/src/constants.ts`: `{Virgil:1, Helvetica:2, Cascadia:3, Excalifont:5, Nunito:6, …}`):

| code | toolkit role | family (Excalidraw) | bundled file |
|------|--------------|---------------------|--------------|
| 1 | `hand` | Virgil (hand-drawn, legacy) | `Virgil.woff2` |
| 5 | `normal` | Excalifont (hand-drawn, current default) | `Excalifont-Regular.woff2` |
| 3 | `code` | Cascadia (monospace) | `Cascadia.woff2` |

Excalifont and Cascadia are OFL/SIL — redistribution in the skill is permitted. Virgil's license is confirmed during implementation (Excalidraw ships it freely; `fonts/` carries each font's license file). `getFontFamilyString` fallbacks per code: Virgil→`"Virgil, sans-serif, Segoe UI Emoji"`, Excalifont→`"Excalifont, Xiaolai, sans-serif, Segoe UI Emoji"`, Cascadia→`"Cascadia, monospace, Segoe UI Emoji"`.

Note (out of scope, flagged for the toolkit author): the toolkit maps `"hand"→1` (Virgil, which Excalidraw deprecated) and `"normal"→5` (Excalifont, itself a hand-drawn font). The exporter renders faithfully whatever code the file carries; whether the toolkit's role→code map is ideal is a separate question.

### 6. Scope / element coverage

Exactly the toolkit's output — nothing more:

- **Shapes:** `rectangle`, `ellipse`, `diamond` — with `solid` fill (or transparent), stroke color/width, `dashed`, and `roughness`.
- **Linear:** `line`, `arrow` — straight and curved (multi-point), dashed, default `arrow` arrowhead (+ none); Excalidraw's arrowhead geometry ported for those two.
- **Text:** free `text` and **bound labels** (container-anchored), the three fonts, font size, alignment, multi-line.
- **Out of scope:** hachure/cross-hatch fill, freedraw, images, frames, non-`arrow` arrowheads — added only if the toolkit ever emits them.

### 7. CLI + API surface (illustrative — final names settled in the plan)

```python
# excalidraw_svg.py  (stdlib only)
def to_svg(doc: dict, *, background: str | None = "#ffffff", padding: int = 10) -> str: ...

# export.py  (uv script; PEP-723 header pins resvg-py)
def render_png(src: str | dict, out: str, *, scale: int = 2, background: str = "light") -> str: ...
# CLI:  uv run export.py diagram.excalidraw -o diagram.png --scale 2 --background light
```

PEP-723 header of `export.py`:
```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["resvg-py==0.3.3"]
# ///
```

### 8. Docs impact (supersedes prior spec §8)

- Rewrite `png-export.md` → the `uv` script becomes the **primary** export path; the manual GUI export stays documented as a zero-setup fallback.
- Update `SKILL.md` "Exporting to PNG" and the "Files in this skill" list.
- Note in the new material that this supersedes `2026-06-28` §8 ("manual GUI, no CLI rasterizer bundled").

## Testing / Verification

- **RNG unit test:** the ported `Random` reproduces the exact JS sequence for known seeds (values cross-computed from the MINSTD formula).
- **Golden SVG:** `to_svg()` output equals the reference SVG minted from the real `@excalidraw/utils` for the fixture set (one fixture per element type + variants: fill/no-fill, dashed, `roughness` 0/1/2, each font, bound label, multi-line text, curved arrow).
- **Golden PNG hash:** sha256 of the rendered PNG is stable across runs on the pinned toolchain; the pinned `resvg-py` version is recorded next to the fixtures.
- **Determinism test:** exporting the same file twice yields byte-identical SVG and PNG.
- TDD throughout (the implementation plan drives ordering).

## Risks / open questions

- **Option-constant drift.** If a `generateRoughOptions` constant is ported wrong, geometry diverges subtly. *Mitigation:* the golden-SVG diff against the real lib is the backstop — it fails loudly on any mismatch.
- **`resvg-py` fidelity for `@font-face`/base64 fonts.** Must confirm resvg resolves embedded base64 fonts (vs. only `--font-file`). *Fallback:* pass fonts to resvg via a resource dir instead of base64 embedding; SVG then references by family name. Decided during implementation once resvg behavior is checked.
- **Cross-rasterizer determinism not guaranteed.** Only the pinned resvg build is byte-stable. If hard, rasterizer-agnostic byte-identity is ever needed, escalate to glyph-vectorization (fonttools → `<path>`), which was explicitly deferred here.
- **rough.js curve/ellipse edge cases.** Ellipse and multi-point curve ops use bezier approximations with per-vertex jitter; the port must match rough.js' exact control-point math, not merely "a bezier." The fixture set must include these specifically.

## Open implementation details (decided during implementation, no further input needed)

- Exact `generateRoughOptions` constants + arrowhead geometry, read from Excalidraw `master`.
- Exact `FONT_FAMILY` code → font-file mapping, read from the pinned source.
- Float precision + attribute ordering for byte-stable SVG.
- Whether resvg gets fonts via base64 embed or a resource dir (per the risk above).
- Fixture-minting harness (one-time Node script; kept in the repo but not a runtime dep).

## Commit (global skills repo — its own repo, not the blogs repo)

Implementation lands in the skill repository, in a dedicated worktree, TDD-driven. This design document lives in the **blogs** repo under `docs/specs/` (tracked), alongside the two prior Excalidraw specs.
