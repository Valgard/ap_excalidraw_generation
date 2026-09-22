# Excalidraw Native Font Fallback — Design

- **Date:** 2026-07-05
- **Status:** Approved (2026-07-05) — ready for implementation planning
- **Component:** `excalidraw-generation` skill (`fonts.py`, `excalidraw_svg.py`, `export.py`, coverage-build tooling)
- **Related:** alters `to_svg` output (removes per-glyph `<tspan>`s), so the pin-down-net goldens (`2026-07-05-excalidraw-pindown-net-design`) must be minted **after** this lands — see Dependencies & Sequencing. Upstream fix "Weg C" (resvg issue #301) is tracked separately in a separate ideas list.

## Context

The exporter rasterizes SVG → PNG via `resvg-py==0.3.3`. A large font-fallback
workaround was built on the belief that resvg does **font-level fallback only**
(a missing glyph renders blank): per-glyph `<tspan>` segmentation in
`excalidraw_svg._render_text`, driven by `fonts.resolve_char_font`, driven by
build-time coverage sets in `emoji_coverage.py` / `font_coverage.py`.

**That belief is stale.** Verified 2026-07-05, empirically and against the usvg
source:

- `resvg-py 0.3.3` wraps **`resvg 0.47.0`** (latest tag; text-fallback logic is
  byte-identical to `main`) and wires `font_resolver: FontResolver::default()`.
- `FontResolver::default()` does **native per-glyph fallback**
  (`default_fallback_selector` scans the fontdb per character). Probe: `A→` with a
  Latin-free DejaVu loaded → `A` stays Excalifont, `→` renders via DejaVu.
- The tspan routing is therefore **redundant for rendering**; a plain `<text>` plus
  the fallback fonts in the fontdb produces the same glyphs.

The one real remaining hazard is the **"run poison"** — a deliberate usvg branch,
not a bug (`crates/usvg/src/text/layout.rs`, `fn shape_text`):

```rust
let all_matched = fallback_glyphs.iter().all(|g| !g.is_missing());
if all_matched { glyphs = fallback_glyphs; break 'outer; }  // whole chunk → one font
```

If a **single loaded font covers an entire chunk**, usvg replaces the whole chunk
with it. So co-loading a Latin+symbol font (Liberation `2`/`9`, Cascadia `3`) with a
hand-drawn run that contains a symbol (`→ ✓ …`) collapses the whole line into that
font. This is **per-chunk, not per-span** — verified: `flow <tspan
font-family="DejaVu Sans">→</tspan> next` with LiberationSans loaded still collapses
`flow`. **tspans do not guard the poison.** Upstream issue #301 ("Prefer
font-family during font fallback") has been open since 2020-06-26.

**Corpus reality (103 `.excalidraw`):** only Virgil (87) + Excalifont (46) are used,
both hand-drawn, neither covers symbols → no single loaded font ever covers a
Latin+symbol run → the poison is currently **structurally impossible**. But the
exporter is a general tool, and **frame labels render in Helvetica (code `2` →
LiberationSans)**, so any future diagram with a frame *and* a hand-drawn line
carrying a symbol would load a poisoner and collapse.

### Evidence (scratchpad probes, resvg-py 0.3.3)

| Probe | Result |
|---|---|
| `A→` + Latin-free DejaVu | per-glyph ✓ (A=Excalifont, →=DejaVu) |
| `A→` + full LiberationSans | poison ✗ (whole run → LiberationSans) |
| `flow <tspan>→</tspan> next` + LiberationSans | poison ✗ (tspan does not guard) |
| `flow 🔑 → next` + LiberationSans | no poison ✓ (emoji breaks `all_matched`) |
| `flow → next` + **Latin-only** LiberationSans + DejaVu | no poison ✓, → rendered via DejaVu |

## Goal

Replace the always-on per-glyph tspan machinery with resvg's native per-glyph
fallback, delete the redundant coverage-baking, and keep the poison fully handled
via load-set curation + Latin-free fallbacks + a **font-subset guard** for the
mixed-font case — at unchanged visual fidelity and byte-determinism.

## Non-Goals

- Patching usvg/resvg (issue #301 → "Weg C", separate project).
- Changing the fallback **font set** or the emoji/symbol **priority** order.
- Any change to shape/arrowhead/geometry rendering.

## Design

### 1. Rendering path — plain `<text>`, native per-glyph fallback

`excalidraw_svg._render_text` stops emitting per-glyph `<tspan>` segmentation and
emits the text as a single run with the element's primary `font-family`. resvg's
`FontResolver::default()` resolves any glyph the primary font lacks from the loaded
Latin-free fallback fonts, per character. A line the primary font fully covers is
already a single `<text>` (unchanged fast path).

### 2. Font loading — curation stays, add the subset guard

`fonts.font_file_paths(used_codes(doc))` keeps loading **only referenced text
fonts + the Latin-free fallbacks** (`AppleColorEmoji`, `NotoColorEmoji`,
`DejaVuSubset`, `NotoSymbols`, in that fixed order). This remains the primary
poison-avoidance: in a single-hand-drawn-font document no poisoner is ever loaded.

**Font-subset guard (new).** When `used_codes(doc)` contains **both** a hand-drawn
code (`1/5/6/7/8`) **and** a poisoner code (`2/3/9` — Liberation/Helvetica/Cascadia;
note code `2` is also implied by any frame), load the poisoner as a **symbol-stripped
subset** instead of the full font. The subset keeps Latin + punctuation but drops the
symbol codepoints the Latin-free fallbacks own, so it can no longer cover a
Latin+symbol run → `all_matched` never fires → native per-glyph fallback → no
poison. The poisoner's own Latin text still renders in it; a symbol inside a
poisoner element falls back to DejaVu. (Verified with a fontTools Latin-only subset.)

### 3. Fallback priority — preserved by load order (no new code)

The emoji/symbol priority `resolve_char_font` hard-coded (Apple → Noto → DejaVu →
NotoSymbols) is already the load order in `_FALLBACK_FILES`; the native resolver
iterates the fontdb in insertion order and picks the first covering, style-matching
face. Deleting `resolve_char_font` loses nothing on priority.

### 4. What gets deleted

- `fonts.resolve_char_font` and its now-unused helpers/constants
  (`is_emoji_cp`, `APPLE_QUOTED_FAMILY` etc.) if unused elsewhere.
- `emoji_coverage.py`, `font_coverage.py`, and the fontTools build tooling that
  generates them.
- The per-glyph segmentation loop in `excalidraw_svg._render_text`.

**Kept:** `family_string`, `line_height`, `vertical_offset`, `font_face_css`,
`used_codes`, `font_file_paths` (extended with the subset guard), `FONT_METRICS`,
`FAMILY`, `_FALLBACK`, `_FILE`, `_FALLBACK_FILES`.

### 5. Determinism

Native fallback is deterministic given a fixed fontdb load order (deterministic in
`font_file_paths`) and `skip_system_fonts=True`. The subset is generated
deterministically at build time (fixed codepoint set, fixed fontTools options). PNG
output must stay byte-stable across repeated runs.

## Success Criteria

- All existing resvg-gated PNG-render tests produce **visually equivalent** output
  (glyphs render; no blanks, no sans-serif collapse).
- **Complex emoji still render as single glyphs** — ZWJ sequences (e.g. family
  emoji) and skin-tone modifiers (U+1F3FB–U+1F3FF), which `resolve_char_font`
  handled explicitly, must survive native fallback via harfbuzz cluster handling.
  Not yet probed → must be verified during implementation; if native fallback
  splits a cluster, that is a blocker for full deletion of the routing.
- New **mixed-font poison test**: a doc combining a hand-drawn font with a
  Liberation/frame element and a symbol in the hand-drawn line renders the
  hand-drawn line in its font (guard green); the same without the guard reproduces
  the poison (guards the guard).
- Determinism fixtures byte-stable across runs.
- `emoji_coverage.py` / `font_coverage.py` / their build tooling removed; the full
  `uv run run_tests.py` suite stays green.
- `to_svg` no longer emits per-glyph `<tspan>`s for the common case.

## Dependencies & Sequencing

- **Cross-spec with the pin-down net (Spec 2, 2026-07-05):** that spec freezes the
  *current* `to_svg` output byte-exact to protect the SVG-serializer refactor
  (Spec 3). This change deliberately changes `to_svg` output (drops tspans), so it
  must land **before** the pin-down goldens are minted, or the goldens must be
  re-minted from the post-change output. Decide the order with the user before
  implementing (see Open Questions).
- fontTools is already a build-time dependency (used for the existing coverage
  baking and the DejaVu subset), so the subset guard adds no new runtime dep.

## Resolved Decisions (2026-07-05)

1. **Subset strip boundary — surgical.** The poisoner subset drops only the
   codepoints the Latin-free fallbacks cover that the hand-drawn fonts lack (the
   "contested" set: arrows/math/dingbats/emoji ranges), preserving the poisoner's
   normal Latin + punctuation (en/em-dash, curly quotes, bullet). The exact
   contested set is computed at build time from the bundled fonts' cmaps.
2. **Conditional subsetting.** A poisoner is subset only when co-loaded with a
   hand-drawn font; a pure-poisoner document loads the full font so its own symbols
   render in it.
3. **Sequencing — this lands first.** Land this change, then mint the pin-down-net
   goldens from the simplified (tspan-free) output. The serializer refactor
   (Spec 3) preserves that simplified output byte-exact.
