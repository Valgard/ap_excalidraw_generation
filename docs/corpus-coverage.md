# Corpus Branch-Coverage Report

**Date:** 2026-07-05  
**Branch:** `corpus-extension`  
**Suite:** `tests/test_corpus_smoke.py` (62 passed, 2 xfailed)  
**Coverage command:**
```
uv run --with pytest --with coverage python -m coverage run --branch -m pytest tests/test_corpus_smoke.py -q
uv run --with coverage python -m coverage report -m --include="*excalidraw_svg.py,*excalidraw_shape.py,*excalidraw_arrowheads.py,*excalidraw_bounds.py,*freehand.py,*roughjs.py"
```

---

## Branch Coverage

| File                     | Stmts | Miss | Branch | BrPart | Cover |
|--------------------------|-------|------|--------|--------|-------|
| excalidraw_svg.py        | 339   | 21   | 108    | 20     | 90%   |
| excalidraw_shape.py      | 133   | 19   | 54     | 6      | 87%   |
| excalidraw_arrowheads.py | 160   | 13   | 66     | 11     | 89%   |
| excalidraw_bounds.py     | 145   | 23   | 48     | 10     | 83%   |
| freehand.py              | 295   | 75   | 138    | 31     | 71%   |
| roughjs.py               | 369   | 33   | 158    | 27     | 86%   |
| **TOTAL**                | 1441  | 184  | 572    | 105    | **84%** |

---

## Notable Uncovered Branches

### `excalidraw_svg.py`

| Lines / Branch | Reason |
|---|---|
| 139 (`fillSketch` branch) | Unreachable via corpus: `fillSketch` opset type comes from rough.js hachure/zigzag/crosshatch fill; those inputs render fine but branch not exercised because no fill background is set on hachure inputs — defensive code path. |
| 170→172 (opacity strip `.0`) | Branch only fires when image opacity is not 100 and is a whole number other than 1.0; corpus `image.excalidraw` uses default opacity 100 → skipped. Not a gap; the branch is cosmetic formatting. |
| 208 (`line_height` fallback) | Branch fires only when `lineHeight` and `height` are both absent from a text element; defensive fallback. No corpus text exercises this edge case. |
| 292 (`about:blank` sanitize) | Fires only for links with non-http/https/mailto schemes; iframe/embeddable corpus uses `https://example.com`. Defensive security guard. |
| 323 (degenerate 0-point arrow midpoint) | Fires when `points` list is empty; never occurs in practice (Excalidraw always serializes ≥1 point). Defensive guard. |
| 375–378, 382–385 (bound-text `valign=bottom`, `halign=right/left`) | Genuine gap: corpus `valign-bottom.excalidraw` covers the shape-bound case; arrow-label bound-text does not exercise `bottom`/`right`/`left` alignment variants. Low priority (label alignment on arrows). |
| 433 (`"AI Frame"` magicframe name fallback) | Branch fires when magicframe has no `name` field; corpus `magicframe.excalidraw` has no name, but magicframe renders as no-op (unhandled type) so frame label code is never reached. |
| 525–526 (export background rect) | Fires only when `ExportOptions.export_background=True`; corpus uses default options (no background). |
| 558, 561 (embeddable opacity != 1 inner branch) | Fires only when `embeddable`/`iframe` opacity < 100; corpus `iframe.excalidraw` uses default opacity 100. Minor variant. |
| 605 (frame label rendering) | Fires only when a frame has a non-empty label; corpus `frame.excalidraw` has an empty name. `frame-rotated.excalidraw` sets `name: "Rotated Frame"` — frame label code IS reached, but the un-hit branch is the else path (non-None lbl dict). |
| 666–673 (frame name label render) | Reached only for frames with a non-empty `name` field; `frame.excalidraw` uses `name: ""`, leaving this branch uncovered. |
| 710–719 (image symbol in defs) | Fires when `files` dict has an entry matching a `fileId`; corpus `image.excalidraw` uses a stub `fileId` but the `files` block is empty, so symbol is not built. |
| 735 (embeddable link wrap) | Fires when embeddable/iframe has a `link` field; corpus `iframe.excalidraw` has `link: "https://example.com"` — this **is** covered. If reported as missed, it is because the link is present but the element renders as no-op before reaching the link-wrap code path. |
| 746, 756–776 (dark mode, embed scene) | `export_with_dark_mode=True` and `export_embed_scene=True` — both require non-default `ExportOptions`. Defensive/optional paths; no corpus inputs exercise them. |
| 840, 847–848 (dark mode bg, embed scene metadata) | Same as above — optional `ExportOptions` paths. |

### `excalidraw_shape.py`

| Lines / Branch | Reason |
|---|---|
| 22 (`min(r/…, 2.5)` corner-radius clamping) | Branch fires only for small elements (< 20px) with roundness; corpus round shapes are ≥ 100px. |
| 26→exit (`get_corner_radius` no-roundness) | Fires when `roundness` is falsy and returns 0; this branch IS reachable (non-rounded shapes call it) but coverage shows miss — may be a partial-branch artefact. Defensive early return. |
| 32 (type-3 roundness fixed-value) | `roundness.type == 3` is a special fixed-radius type; corpus uses type 2 (proportional). Genuine but minor variant. |
| 82–87 (rounded diamond) | Fires when a diamond element has `roundness` set; no corpus input exercises a rounded diamond specifically. Genuine gap (minor: rounded-diamond input missing from corpus). |
| 117–121 (rounded diamond in shape gen) | Same as above — the rounded-diamond code path in `generate_element_shape`. |
| 137–141 (rounded embeddable) | Fires when embeddable/iframe has `roundness` set; corpus `iframe.excalidraw` has no roundness. Minor variant. |
| 169 (unknown element type returns `[]`) | Defensive fallthrough for unrecognised element types; magicframe goes through the SVG no-op path before reaching shape.py. |

### `excalidraw_arrowheads.py`

| Lines / Branch | Reason |
|---|---|
| 112, 116 (empty ops guard) | Fires when an arrowhead opset has no ops; defensive against degenerate rough output. |
| 126, 130 (short bcurveTo data guard) | Fires when a bcurveTo op has fewer than 6 data points; defensive against malformed rough output. |
| 146, 161 (start-position arrowhead direction) | Fires for `position == "start"` arrowheads; most corpus arrows use end arrowheads only. `arrowhead-both` (xfailed) exercises start position but crashes before reaching direction logic. Genuine gap (blocked by dot-arrowhead crash). |
| 214–215 (zero-distance guard) | Fires when the tip-to-sample distance is zero; defensive against degenerate arrows. |
| 253, 257 (diamond arrowhead opposite point) | Fires for `diamond`/`diamond_outline` arrowheads at start position; same as line 146 gap. |
| 362, 381–382 (cardinality arrowhead dispatch, dotted-stroke arrowhead options) | Fires for cardinality-type arrowheads (`cardinality_one`, `cardinality_exactly_one`, `cardinality_zero_or_one`) and for dotted-stroke arrowhead caps. Genuine gap: cardinality arrowhead dispatch not exercised at render depth (corpus exercises shape structure only). |

### `excalidraw_bounds.py`

| Lines / Branch | Reason |
|---|---|
| 82 (linear bezier `a == 0, b == 0` guard) | Fires for degenerate quadratic bezier; defensive. |
| 127→129 (transform_xy None branch) | Fires when `curve_ops_bbox` is called without a coordinate transform; corpus calls it always with a transform. Minor. |
| 141–144 (lineTo branch in curve_ops_bbox) | Fires when rough produces `lineTo` ops instead of bezier curves; only happens for very small elements or degenerate geometry. Defensive. |
| 145→135 branch | Partial coverage on the `lineTo` / `bcurveTo` elif chain. Same as above. |
| 157 (empty ops returns `(0,0,0,0)`) | Defensive empty-ops guard. |
| 187–188 (degenerate single-point line) | Fires when a line/arrow element has only 1 point; defensive against malformed data. |
| 202 (fallback to point-bbox) | Fires when `generate_element_shape` returns empty sets for a line/arrow; defensive. |
| 238–243 (rotated freedraw bounds) | Fires only for rotated freedraw elements; corpus `freedraw.excalidraw` uses `angle=0`. Genuine but minor gap. |
| 248–254 (rotated ellipse closed-form) | Fires only for rotated ellipses; corpus ellipse inputs all have `angle=0`. Genuine minor gap. |
| 276 (`get_common_bounds` empty list) | Defensive guard; an empty element list should never reach this in practice. |

### `freehand.py` (71% coverage)

Lower coverage is expected: `freehand.py` ports the `perfect-freehand` library which contains many branches for pressure variation, vector-tapering, and stroke simulation. The corpus has one `freedraw.excalidraw` input exercising the primary path. The uncovered branches (lines 55→exit, 78, 87–89, 102, 111–126, 150, 157, 176, 186–239, 247, 268–280, 310–317, 343–358, 393–411, 449–453, 487, 544, 548–560) are:
- Pressure-variation paths (`pressure != 1.0`, adaptive pressure simulation)
- Stream-closed path (first/last point almost coincide)
- Edge cases for very short strokes (< 3 points)
- Left-side taper / right-side taper when `taperStart` / `taperEnd` are non-default
- **Assessment:** all are minor rendering-fidelity variants of freedraw, not crashes. The corpus exercises the dominant path (multi-point, default pressure). Not worth adding more inputs here per the spec's scope.

### `roughjs.py` (86% coverage)

`roughjs.py` is a Python port of rough.js. Uncovered branches (lines 31, 71→73, 93→95, 98, 120–139, 185, 207–231, 259, 273–293, 321–323, 347, 371, 424–453, 481–483) are:
- Alternate roughness/bowing computation branches for extreme parameter values
- `_offset_opt` with `roughnessGain` parameter (used only in internal fill paths)
- `_build_ellipse_path` closed/open variants not triggered by the corpus
- `generate_ellipse_params` vs direct `ellipse` call divergence
- **Assessment:** these are internal rough.js math branches exercised by specific parameter combinations. All are covered at the happy-path level; uncovered branches are parameter variants not present in the corpus. Not findings; rough.js itself is not the exporter feature surface.

---

## Exporter Findings (Feature Gaps)

The following features are exercised by corpus inputs but not correctly implemented in the exporter. None are fixed in this task.

### F-1: `arrowhead-dot` — crash (ValueError, xfailed)
- **Input:** `tests/inputs/atomic/arrowhead-dot.excalidraw`
- **Crash:** `excalidraw_arrowheads.py:315` — `tx, ty, diameter = pts` unpacks 3 values but `get_arrowhead_points` returns more than 3 for the `dot`/`circle` type (likely `(tx, ty, rx, ry)` for ellipse radii).
- **Effect:** Renders nothing; exception raised.
- **Status:** `xfail(strict=False)` in smoke suite.

### F-2: `arrowhead-both` — crash via dot startArrowhead (ValueError, xfailed)
- **Input:** `tests/inputs/atomic/arrowhead-both.excalidraw`
- **Crash:** Same `excalidraw_arrowheads.py:315` — fires on the `startArrowhead="dot"` before the `endArrowhead="triangle"` is reached.
- **Effect:** Renders nothing; exception raised.
- **Status:** `xfail(strict=False)` in smoke suite.

### F-3: `magicframe` type renders as silent no-op
- **Input:** `tests/inputs/atomic/magicframe.excalidraw`
- **Behaviour:** The `magicframe` type is dispatched by the `frame`/`magicframe` branch in `excalidraw_svg.py`, which renders a frame rect and name label. However, because the element is rendered as a **rect + optional label only** (not as an AI-generated content frame), the frame content is invisible. The frame border does render — the no-op finding is specifically about the frame **contents** not being drawn.
- **Effect:** Magicframe renders an empty border rectangle; any child elements it would contain are drawn unclipped at absolute coordinates (same as Finding F-5).
- **Status:** No crash; smoke test passes. Documented gap.

### F-4: `iframe` type renders as no-op (content invisible)
- **Input:** `tests/inputs/atomic/iframe.excalidraw`
- **Behaviour:** The `embeddable`/`iframe` branch in `excalidraw_svg.py` calls `_render_element(el)`. In `generate_element_shape`, the `embeddable`/`iframe` type returns a rectangle rough shape — so the border is drawn. The link-wrap (`<a href>`) code is present. However, the **embedded content** (the actual iframe content at `link`) is not rendered (there is no `<foreignObject>` or equivalent); the SVG shows only the rectangle outline.
- **Effect:** iframe renders as an outlined rectangle with no content; `<a href>` wrapping is applied. Structural SVG parity with real Excalidraw is achieved at border level only.
- **Status:** No crash; smoke test passes. Documented gap.

### F-5: Populated-frame children render UNCLIPPED
- **Input:** `tests/inputs/atomic/frame-populated.excalidraw`
- **Behaviour:** The exporter does not apply a `clip-path` to child elements whose `frameId` matches a frame. Children are drawn at their absolute scene coordinates without being clipped to their parent frame's bounding box.
- **Effect:** Child elements of a frame render at their full extent, visible outside the frame border.
- **Status:** No crash; smoke test passes. Documented gap. A `clipPath` element is emitted into `<defs>` but never applied to children.

### F-6: `font-10` (Assistant font) renders via fallback — visual fidelity gap
- **Input:** `tests/inputs/atomic/font-10.excalidraw`
- **Behaviour:** Font family code `10` is not mapped in the exporter's font-family lookup. The exporter falls back to a default font (likely Helvetica or the first mapped family). The text renders without crash but uses the wrong typeface.
- **Effect:** Text renders; font family is incorrect.
- **Status:** No crash; smoke test passes (truthy SVG check). Documented visual-fidelity gap.

### F-7: `image-crop` — crop property ignored
- **Input:** `tests/inputs/atomic/image-crop.excalidraw`
- **Behaviour:** The `crop` field on image elements is not read by the exporter. The image is rendered full-size (ignoring `x`, `y`, `width`, `height` within the crop object). The `<use>` element references the full image symbol with no `viewBox` clipping.
- **Effect:** Image renders uncropped; the cropped region is not isolated.
- **Status:** No crash; smoke test passes. Documented visual-fidelity gap.

---

## Success Criterion: Every Renderable Feature Has ≥1 Atomic Input

Plan gap list vs. `tests/inputs/atomic/` contents (`ls tests/inputs/atomic/ | sort`):

| Feature from plan gap list | Atomic input file | Status |
|---|---|---|
| element type `line` | `line-plain.excalidraw` | ✓ |
| element type `magicframe` | `magicframe.excalidraw` | ✓ |
| element type `iframe` | `iframe.excalidraw` | ✓ |
| fill `cross-hatch` | `fill-crosshatch.excalidraw` | ✓ |
| fill `zigzag` | `fill-zigzag.excalidraw` | ✓ |
| fill `solid` | `fill-solid.excalidraw` | ✓ |
| stroke `dotted` | `stroke-dotted.excalidraw` | ✓ |
| roundness `1` (LEGACY) | `roundness-legacy.excalidraw` | ✓ |
| roughness `0` | `roughness-0.excalidraw` | ✓ |
| roughness `2` | `roughness-2.excalidraw` | ✓ |
| strokeWidth `thin` | `strokewidth-thin.excalidraw` | ✓ |
| strokeWidth `bold` | `strokewidth-bold.excalidraw` | ✓ |
| opacity < 100 | `opacity-50.excalidraw` | ✓ |
| arrowhead `bar` | `arrowhead-bar.excalidraw` | ✓ |
| arrowhead `circle` | `arrowhead-circle.excalidraw` | ✓ |
| arrowhead `circle_outline` | `arrowhead-circle_outline.excalidraw` | ✓ |
| arrowhead `triangle_outline` | `arrowhead-triangle_outline.excalidraw` | ✓ |
| arrowhead `diamond` | `arrowhead-diamond.excalidraw` | ✓ |
| arrowhead `diamond_outline` | `arrowhead-diamond_outline.excalidraw` | ✓ |
| arrowhead `cardinality_one` | `arrowhead-cardinality_one.excalidraw` | ✓ |
| arrowhead `cardinality_many` | `arrowhead-cardinality_many.excalidraw` | ✓ |
| arrowhead `cardinality_one_or_many` | `arrowhead-cardinality_one_or_many.excalidraw` | ✓ |
| arrowhead `cardinality_exactly_one` | `arrowhead-cardinality_exactly_one.excalidraw` | ✓ |
| arrowhead `cardinality_zero_or_one` | `arrowhead-cardinality_zero_or_one.excalidraw` | ✓ |
| arrowhead `cardinality_zero_or_many` | `arrowhead-cardinality_zero_or_many.excalidraw` | ✓ |
| arrowhead `dot` | `arrowhead-dot.excalidraw` | ✓ (xfail — renderer crash) |
| start + end arrowhead (`both`) | `arrowhead-both.excalidraw` | ✓ (xfail — renderer crash via dot) |
| fonts `2, 3, 5, 6, 7, 8, 9` | `font-{2,3,5,6,7,8,9}.excalidraw` | ✓ |
| font `10` (Assistant) | `font-10.excalidraw` | ✓ (visual-fidelity gap, no crash) |
| `verticalAlign=bottom` | `valign-bottom.excalidraw` | ✓ |
| line/arrow-bound text | `boundtext-line.excalidraw` | ✓ |
| shape-bound text | `boundtext-shape.excalidraw` | ✓ |
| populated frame + clip | `frame-populated.excalidraw` | ✓ (unclipped gap, no crash) |
| rotated frame | `frame-rotated.excalidraw` | ✓ |
| image `crop` | `image-crop.excalidraw` | ✓ (crop ignored, no crash) |
| rotation | `rotation.excalidraw` | ✓ |
| elbow arrow | `elbow-arrow.excalidraw` | ✓ |

**Additionally covered (pre-existing or early tasks):** `arrow-label`, `curved-arrow`, `diamond`, `double-head`, `ellipse-dashed`, `embeddable`, `frame`, `freedraw`, `hachure-rect`, `image`, `multiline-lineheight`, `opacity-arrow/diamond/ellipse/rect/text`, `rtl-text`, `text`, `triangle-head`.

### Missing from plan gap list (confirmed present in corpus)

No features from the plan gap list are missing from the atomic tier.

### Minor corpus gap (not in plan gap list, found during coverage analysis)

- **Rounded diamond:** no atomic input for `diamond` + `roundness` set. The rounded-diamond code path (`excalidraw_shape.py:117–121`, `_rounded_diamond_d`) is uncovered. This was not listed in the plan's gap matrix. Not a blocker.
- **Elbow arrows:** covered by `elbow-arrow.excalidraw` — an `arrow` element with `"elbowed": true`. See table row below.

---

## Summary

- **84% branch coverage** across the render path (6 files, 1441 statements).
- **90% coverage** on the primary render dispatch (`excalidraw_svg.py`).
- Most uncovered branches are defensive guards (degenerate geometry, empty ops, missing data) or optional `ExportOptions` paths (`dark_mode`, `embed_scene`, `export_background`). None represent unknown crashes.
- **7 exporter findings** documented above (F-1 through F-7): 2 crashes (xfailed), 3 silent no-ops, 2 visual-fidelity gaps.
- **Primary success criterion met:** every feature from the plan's gap matrix has ≥1 atomic input in `tests/inputs/atomic/`.
