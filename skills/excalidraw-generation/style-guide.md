# Excalidraw Style Guide

This guide documents two visual styles — **Style A: Sketch** and **Style B: Minimal** — that share a common atom layer (`PALETTE`, `SEMANTIC`, `role(`, `TITLE`, `SUBTITLE`). Both styles are content-agnostic: the caller chooses which style fits the diagram's purpose, independent of content type. A flow diagram, a matrix, and a timeline can all be rendered in either style.

---

## Base atoms

All atoms live in `excalidraw_palette.py` and are re-exported through `excalidraw.py`. Import them directly:

```python
from excalidraw_palette import PALETTE, SEMANTIC, role, TITLE, SUBTITLE
from excalidraw_toolkit import FONT
```

### PALETTE — hue table

| Hue key      | Fill (`backgroundColor`) | Stroke (`strokeColor`) | Open-Color approx.         |
|--------------|--------------------------|------------------------|----------------------------|
| `blue`       | `#a5d8ff`                | `#1971c2`              | blue-3 fill / blue-7 stroke |
| `blue_pale`  | `#e7f5ff`                | `#74c0fc`              | blue-1 fill / blue-4 stroke |
| `green`      | `#b2f2bb`                | `#2f9e44`              | green-3 fill / green-7 stroke |
| `amber`      | `#ffe8cc`                | `#e8590c`              | orange-1 fill / orange-7 stroke |
| `yellow`     | `#fff3bf`                | `#f08c00`              | yellow-2 fill / yellow-8 stroke |
| `red`        | `#ffc9c9`                | `#e03131`              | red-2 fill / red-7 stroke  |
| `violet`     | `#d0bfff`                | `#862e9c`              | violet-3 fill / grape-9 stroke |
| `gray`       | `#e9ecef`                | `#868e96`              | gray-3 fill / gray-6 stroke |
| `dark`       | `#343a40`                | `#1e1e1e`              | gray-8 fill / near-black stroke |

**Corpus note:** The `violet.fill` atom is `#d0bfff` (Open-Color violet-3, 18× in the corpus — the dominant shade). Secondary corpus violets: `#e5dbff` (OC violet-2, 10×) and `#9775fa` (OC violet-5, 6×) appear in accent contexts and may be used directly for finer tonal variation.

**Secondary shades in the corpus (not in PALETTE):** Diagrams occasionally use lighter variants of the primary hues — `#d0ebff` (blue-2), `#d3f9d8` (green-2), `#ffec99` (yellow-3) — for nested or secondary elements. These are fine to use directly; they are not in `PALETTE` because the primary shades cover most uses.

### SEMANTIC — role map

`SEMANTIC` maps meaning to hue. Callers should reach for `SEMANTIC` (via `role()`) before picking a raw hue:

| Role key    | Hue        | Canonical use                              |
|-------------|------------|--------------------------------------------|
| `danger`    | `red`      | Errors, failures, blocked states           |
| `success`   | `green`    | Completed steps, positive outcomes         |
| `warning`   | `amber`    | Caution, partial states, pending           |
| `info`      | `blue`     | Primary data flow, informational nodes     |
| `optional`  | `blue_pale`| Secondary path, optional component        |
| `neutral`   | `gray`     | Background containers, neutral context     |
| `accent`    | `violet`   | Highlights, callouts, special emphasis     |
| `emphasis`  | `dark`     | Dark header bars, strong contrast labels   |

### `role()` usage idiom

```python
from excalidraw_palette import role

# Splat directly into box()/rect():
d.box("step-ok", x=40, y=100, w=200, h=60, **role("success"), text="Validation passed")
d.box("step-err", x=260, y=100, w=200, h=60, **role("danger"), text="Test failed")
```

`role(name)` returns a fresh `{"fill": ..., "stroke": ...}` dict each call (which map to `backgroundColor`/`strokeColor` in the output JSON) — safe to splat without aliasing.

**Bound-label overrides:** `Diagram.box()`, `ellipse()`, and `diamond()` accept `text_font` (default `"hand"`) and `text_color` (default `"#1e1e1e"`) to control the bound label when `text=` is also passed. These route to the label element, not the shape — `**kw` still controls fill/stroke on the rect itself. Example: `d.box("hdr", x, y, w, h, **role("emphasis"), text="Header", text_font="normal", text_color="#ffffff")`.

### FONT roles

`FONT` is defined in `excalidraw_toolkit.py` and re-exported via `excalidraw_palette.py`. Both import paths work (`from excalidraw_toolkit import FONT` or `from excalidraw_palette import FONT`):

| Key      | Family ID | Description                             |
|----------|-----------|-----------------------------------------|
| `hand`   | `1`       | Virgil / hand-drawn — Sketch default |
| `normal` | `5`       | Nunito (sans-serif) — clean/minimal     |
| `code`   | `3`       | Cascadia / monospace — code labels      |

### TITLE and SUBTITLE defaults

```python
TITLE    = {"font": "hand", "font_size": 28}
SUBTITLE = {"font": "hand", "font_size": 16}
```

Both use the hand font. Splat into `text()` calls:

```python
d.text("title",    40, 20, 800, 36, "Diagram Title",      **TITLE)
d.text("subtitle", 40, 60, 800, 24, "Supporting caption", **SUBTITLE)
```

---

## Choosing a style

Style is **orthogonal to content type** — the same diagram subject can be rendered in either style. The caller picks based on context and target audience:

| Signal | Reach for… |
|--------|-----------|
| Narrative article, blog post, talk slide | **Style A — Sketch** |
| Dense comparison, data matrix, benchmark table | **Style B — Minimal** |
| Colourful, expressive, hand-crafted feel | **Style A — Sketch** |
| Clean, flat, cell-by-cell semantic colouring | **Style B — Minimal** |
| Multiple archetypes in one article | Mix freely — one style per diagram |

Neither style is the default. Every diagram generation call must state the style explicitly.

---

## Style A — Sketch

**Character:** hand-drawn feel (Virgil font, roughness 1–2), Open-Color tints, airy spacing, arrows connecting named nodes. Used across all blog articles and talk slides except the excluded diagram set.

**Global conventions:**
- Font: `hand` (family 1) for all body text; `normal` (family 5) for display titles in mixed-font diagrams.
- Roughness: `1` for most shapes; `2` for deliberately sketchy layered containers. Set via the `roughness` kwarg (default `1`) on `rect`, `ellipse`, `diamond`, `line`, and `arrow`. Pass `roughness=0` for precise, jitter-free lines (timelines, chart reference lines).
- Stroke width: 1–2 px on boxes; arrows default to 1 px.
- Fill style: `hachure` is the Excalidraw default for hand-drawn shapes; the corpus mostly uses solid fill with Open-Color tints.
- Spacing: generous — nodes do not crowd. Typical inter-node gap: 20–40 px.
- Standalone diagram title: `font_size=24–30`, placed as a free text element above the diagram body.
- Subtitle / caption: `font_size=13–16`, one line below the title or as a footer.

### Flow (linear / branched)

**Representative diagrams:** `stateless-flow-en`, `rag-pipeline-en`, `reflection-cycle-en`

**Pattern:**
- Horizontal or vertical chain of rectangles connected by arrows.
- 3–8 nodes per flow; each node: width 140–280 px, height 50–100 px.
- Primary path nodes: `blue` (`#a5d8ff`). Diverging or alternative paths: `green` or `red` to signal contrast.
- Arrows are labelled sparingly; short directional label on the arrow mid-point when the transition name matters.
- Title at top-left; no subtitle unless clarification is needed.
- Branching flows use `red` for error/abort paths, `blue_pale` for optional branches.

**Example palette usage:**
```python
step  = d.box("step",  40,  80, 180, 56, **role("info"),    text="RAG Retrieval")
step2 = d.box("step2", 260, 80, 180, 56, **role("success"), text="Answer")
d.connect("a1", step, step2)          # connect() also accepts label="..." for a mid-arrow annotation
```

### Layered architecture

**Representative diagrams:** `memgpt-tiers-en`, `three-layers-en`, `engineering-stack-en`

**Pattern:**
- 3–5 full-width horizontal bands stacked top-to-bottom, each representing a tier/layer.
- Band height: 60–130 px; full diagram width: 320–900 px.
- Each band: a distinct hue from `SEMANTIC` to encode tier meaning (e.g. `danger`/red for hot cache, `info`/blue for context layer, `success`/green for persistent store).
- Short text block inside each band: tier name (fs 14–15) + brief descriptor (fs 13–14).
- No arrows between layers unless data flow direction needs emphasis; a single downward arrow or line may annotate the read/write path.
- Title above the stack; optional right-side annotation with call depth or access pattern.

**Example palette usage:**
```python
d.box("tier-hot",   0, 0,   320, 70, **role("info"),    text="Core Memory — Always in Context")
d.box("tier-warm",  0, 80,  320, 70, **role("warning"), text="Recall Memory — Searchable")
d.box("tier-cold",  0, 160, 320, 70, **role("success"), text="Archival Memory — Unlimited")
```

### Card / comparison columns

**Representative diagrams:** `drei-paradigmen-en`, `vier-patterns-map-en`, `user-segmentation-en`, `failure-mode-taxonomy-en`

**Pattern:**
- 2–4 side-by-side columns or cards. Each column: width 200–360 px, height 55–640 px.
- Column header box with prominent hue; body rows in lighter shade or `blue_pale`.
- Typical column width: 200–280 px; gap between columns: 20–40 px.
- Card header font size: 22–26 (`normal` font for display impact); body rows: 14–16 (`hand` font).
- Diagrams that compare before/after use paired colours: `red` (before) + `green` (after).
- Diagrams that classify use distinct hues per category: `blue`, `green`, `amber`, `red`.
- Decorative sub-labels (e.g. "Mechanism", "Quantifier") at font size 11–12 create scannable structure inside each card.

**Example palette usage:**
```python
d.box("col-a",    0, 40,  240, 200, **role("danger"),  text="Before")
d.box("col-b",  260, 40,  240, 200, **role("success"), text="After")
```

### Timeline

**Representative diagrams:** `timeline-en` (cognitive-psychology), `Metacognition ... Timeline-en`

**Pattern:**
- Single horizontal or vertical line (roughness 0, dark stroke) as the backbone.
- Milestone markers: filled ellipses (`#1e1e1e` fill, ~20 px diameter) placed on the line.
- Date/year label: `normal` font (family 5), font size 28–34, above the line.
- Event name label: `normal` font, font size 28–34, below the line (alternating above/below for density).
- No background fill on the canvas; the line and dots carry all structure.
- Set `roughness=0` for precise lines — timelines are precise, not sketchy.
- Spacing: 100–200 px between milestones depending on label length.

**Example palette usage:**
```python
# Backbone — roughness=0 for a clean, jitter-free line
d.line("axis", [[40, 200], [900, 200]], stroke="#1e1e1e", roughness=0)
# Milestone dot — roughness=0 for a crisp filled circle
d.ellipse("dot-1", 140, 185, 20, 20, fill="#1e1e1e", stroke="#1e1e1e", roughness=0)
# Labels — use FONT["normal"] directly in text() calls
d.text("yr-1", 130, 150, 80, 36, "1885",       font="normal", font_size=30)
d.text("ev-1", 100, 210, 120, 36, "Ebbinghaus", font="normal", font_size=30)
```

### Chart (bars / curve)

**Representative diagrams:** `ebbinghaus-kurve-en`, `locomo-benchmark-en`, `cost-flip-en`

**Pattern:**
- Bar charts: vertical rectangles of equal width (height ∝ value); height range 36–200 px per bar, width 140–370 px.
- Bars colour-coded by `SEMANTIC` role: `info` (neutral baseline), `success` (best result), `warning` (middle tier), `danger` (worst).
- Curve/line charts: `line` elements; axis labels as free text, font size 12–16.
- Reference lines (ceilings, baselines): dashed `line` elements with `roughness=0` for precise horizontals, annotation text at font size 12–14.
- Axis: implied by position (no drawn axes unless the curve needs a frame); axis tick labels at font size 12.
- Title: font size 24–28, `hand` or `normal` font, top of canvas.
- Source citation: font size 11–12 at bottom, `hand` font.
- Roughness: mixed — bar bodies at `roughness=1` (default, slightly sketchy) or `roughness=2` for a more hand-drawn feel; reference lines at `roughness=0` (precise).

**Example palette usage:**
```python
# Benchmark bars — tallest (best) bar in success green
d.box("bar-full-ctx", 40,  20,  264, 200, **role("success"), text="Full-Context  72.9 %")
d.box("bar-mem0",     320, 80,  264, 140, **role("info"),    text="Mem0 Graph  68.4 %")
d.box("bar-openai",   600, 140, 264,  80, **role("neutral"), text="ChatGPT  52.9 %")
# Reference / ceiling line — roughness=0 for a precise horizontal
d.line("ceiling", [[40, 20], [864, 20]], stroke="#868e96", dashed=True, roughness=0)
```

### Illustration / metaphor

**Representative diagrams:** `memory-stream-en`, `mental-time-travel-en`, `rezept-vs-koch`, `pattern-taxonomy-en`

**Pattern:**
- Freeform compositions — no strict grid. Shapes serve the analogy, not a data model.
- Mixed shape vocabulary: rectangles, ellipses, diamonds, arrows with curved or elbow routing.
- Colour signals meaning, not category: warm hues (`amber`, `yellow`) for "active/hot" concepts; cool hues (`blue`, `blue_pale`) for "stored/passive".
- Font size range wider than other archetypes (12–24); section labels prominent, fine details small.
- Roughness typically 1–2 for organic feel; 0 permitted for precision-heavy sub-elements.
- Arrows often carry a short label; multi-hop paths show causal or temporal flow.
- Title placed prominently; subtitle optional.
- Pattern taxonomies add a parent ellipse or frame enclosing a cluster of child nodes.

**Example palette usage:**
```python
event1 = d.box("event-1", 40,  80, 200, 80, **role("info"),    text="Observation")
event2 = d.box("event-2", 280, 80, 200, 80, **role("warning"), text="Synthesis")
d.ellipse("cluster", 20, 60, 480, 120, **role("optional"))  # loose grouping frame
d.connect("a1", event1, event2, label="triggers")
```

---

## Style B — Minimal

**Character:** flat colour-block cells, no hand-drawn jitter, solid fills with semantic stroke borders, tight grid layout. Designed for dense comparison matrices and data-heavy tables where colour encodes result/state at a glance.

**Nucleus:** `repro_paef.excalidraw` (the PAEF failure-mode matrix). See the code example in `examples/minimal_matrix.py`.

### Principles

1. **Semantic colour-block cells via `role()`** — every data cell is a rectangle filled and stroked via `role(name)`. The fill is the dominant signal; the stroke reinforces it. No decorative gradient or hachure.
2. **Flat and solid** — `fillStyle: "solid"`, `roughness: 1` (minimal jitter — the `roughness` kwarg default; pass `roughness=0` to eliminate jitter entirely), `strokeStyle: "solid"`, `strokeWidth: 1–2`. The slight roughness at the default of 1 is not intentional sketch-feel.
3. **Bound text labels** — text lives inside boxes as bound elements, not as floating free text beside shapes. This keeps the layout stable when cells resize.
4. **Matrix / grid layout** — rows and columns align on a strict grid. All cells in a column share the same `x` and `width`; all cells in a row share the same `y` and `height`. Cell height: 36–52 px; column widths vary by content but are consistent within a column.
5. **Dark header row** — column headers use `emphasis` / dark fill (`#343a40`) with white text (`#ffffff`). Use `text_font` and `text_color` directly on `d.box()`: `d.box("hdr", ..., **role("emphasis"), text="Failure Mode", text_font="normal", text_color="#ffffff")`. (`box` defaults to `text_font="hand"` and `text_color="#1e1e1e"` — override both for dark headers to avoid illegible near-black text on dark fill.) Row labels use `neutral` / light gray fill (`#e9ecef`) with dark text.
6. **Row-stripe semantics** — each data cell's colour is determined entirely by the value it represents, not its position. A "missed" result → `danger` (red); a "detected" result → `success` (green); "partial" → `warning`.
7. **Fonts: `normal` throughout** — no hand font in Minimal style. Title and all labels use `FONT["normal"]` (family 5). Title font size 20–24; column headers 13–15; data cells 13–16. Pass `text_font="normal"` on every `box()`/`ellipse()`/`diamond()` call that carries `text=`.
8. **No arrows** — Minimal style does not use connection arrows. Relationships are encoded by grid position and colour, not flow lines.
9. **Outer frame** — a single light-gray outer rectangle (`#fafafa` fill, `#868e96` stroke, `strokeWidth: 1`) wraps the entire diagram as a canvas boundary.

### Usage pattern

```python
from excalidraw import Diagram, role

d = Diagram("my-matrix")

# Outer frame
d.box("frame", 24, 30, 772, 596, fill="#fafafa", stroke="#868e96")

# Header row — one-call idiom: text_font="normal" + text_color="#ffffff" on dark fill
d.box("hdr-label",    40,  130, 360, 52, **role("emphasis"), text="Failure Mode",     text_font="normal", text_color="#ffffff")
d.box("hdr-baseline", 400, 130, 200, 52, **role("emphasis"), text="Standard Metrics", text_font="normal", text_color="#ffffff")
d.box("hdr-paef",     600, 130, 180, 52, **role("emphasis"), text="PAEF",             text_font="normal", text_color="#ffffff")

# Data rows — cell colour = result meaning; text_font="normal" throughout
y = 190
for label, baseline_role, paef_role in [
    ("Cascading Decision Error", "danger",  "success"),
    ("Silent Degradation",       "danger",  "success"),
    ("Consistency Collapse",     "neutral", "warning"),
]:
    d.box(f"lbl-{y}",   40,  y, 360, 52, **role("neutral"),      text=label,       text_font="normal")
    d.box(f"base-{y}", 400,  y, 200, 52, **role(baseline_role),  text="✗ missed",  text_font="normal")
    d.box(f"paef-{y}", 600,  y, 180, 52, **role(paef_role),      text="✓",         text_font="normal")
    y += 60
```

See `examples/minimal_matrix.py` for the full runnable example.

### Scope note

Style B currently covers matrix / comparison layouts. Other content types (flow, layered, timeline) rendered in Minimal style will be added as additional excluded diagrams are re-styled in later work. The caller may apply Minimal style to any content type by following these principles; only the matrix layout has a worked example today.
