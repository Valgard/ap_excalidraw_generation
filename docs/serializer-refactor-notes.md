# SVG Serializer Refactor — Step 1 Summary & Step 2 Decision Record

**Date:** 2026-07-05  
**Branch:** `svg-el-refactor`  
**Author:** Claude Code (claude-sonnet-4-6)

---

## 1. What Step 1 Achieved

### The `el()` builder (Task 1, commit `b9846fe`)

A centralised `el(tag, attrs, *children, void=False)` helper was introduced in
`excalidraw_svg.py`. It escapes every attribute value through `_escape_attr()`
before interpolation, eliminating the SVG-XSS path that previously existed when
user-controlled data (labels, link URLs, font family strings with embedded quotes)
was composed via bare f-strings. Attribute order is deterministic (dict insertion
order); void elements emit `" />"` (space before slash) to match the existing
`<path …/>` format already present in the golden corpus.

### Migration coverage (Tasks 2–6)

All SVG element-emitting sites were assessed across Tasks 2–6. Outcome by
element group:

| Group | Migrated to `el()` | Remaining manual (f-string) | Reason left manual |
|---|---|---|---|
| `<path>` emitters (`_path_el`, `_render_freedraw`) | ✓ | 0 | — |
| Shape/image/embeddable group wrappers (`_render_image_use`, `_render_embeddable_paths`) | ✓ | 0 | — |
| `_render_text` (all `<text>` lines) | ✓ | 0 | — |
| Frame emitters (`_render_frame_name_label`, `_render_frame_rect`, `_build_frame_clip_path` inner rect) | partially | 3 `<rect>` sites | void-format inconsistency (see §4) |
| Root assembly: background `<rect>`, image `<symbol>`, arrow mask inner `<rect>`s | partially | 3 sites | void-format inconsistency (see §4) |

**`el()` call count:** 32 call sites in the final file (`grep -oE '\bel\(' excalidraw_svg.py | wc -l` → 33, minus 1 for the `def el(` definition); `_escape_attr` is
unconditionally applied to every attribute value at all of those sites.
Escaping centralisation is therefore structural for all migrated element types.

### Byte preservation

Every migration step was gated on the existing pin-down test net (golden
corpus round-trips). All tasks landed green — no golden was regenerated.
The refactor is purely an internal escaping/attribute-building change with
zero observable output difference on the corpus.

---

## 2. Mutate-Before-Emit Coupling Assessment

### What the coupling is

`scene_layout()` runs a **pre-pass** before any string is emitted:

1. Sorts elements by fractional index.
2. Builds synthetic frame-name-label dicts (extend scene bounds upward).
3. Computes `_arrow_label_scene` — the recomputed midpoint position of every
   arrow/line bound label (correcting stale stored `x`/`y`).
4. Derives scene bounds over ALL contributing objects, substituting recomputed
   positions where applicable.
5. Returns `off_x`, `off_y`, `width`, `height` — the coordinate offset and
   canvas size needed by every emitted `translate(…)`.

`to_svg()` then uses `off_x`/`off_y` as a single pass over the element list,
building `body[]` as plain strings. Arrow masks are built **inline** within the
loop once `off_x`/`off_y` are known (lines 804–816) — they cannot be deferred
because the mask rect coordinates (`svg_lx = lx + off_x`) depend on the
pre-computed offset.

### Is the coupling painful after Step 1?

**No.** The coupling is well-contained and the code is not complex:

- `scene_layout` is a single coherent function (~110 lines) that returns a
  named tuple. There is no mutation of shared state; the pre-pass is
  read-only over the element list and writes only to local dicts
  (`_arrow_label_scene`, `frame_labels`).
- `to_svg` reads the layout struct and emits strings in a single forward pass.
  The only "stitching" — building arrow mask strings after offsets are known —
  is three lines of arithmetic (lines 804–816) and is already inline.
- No bug has been traced to this pattern. The two layout bugs that were fixed
  (`Fix 1`: stale arrow-label stored position; `Fix 2`: missing empty mask
  element) were caused by incorrect arithmetic or missing structural parity
  with Excalidraw's output, not by mutate-before-emit ordering.
- The pattern is already separated cleanly: `scene_layout` is independently
  callable and is used by `tools/font_diff.py` for bbox mapping. This
  separation was deliberately chosen and is an asset.

**Before `el()`**, the primary motivation for a mutable node tree would have
been to retrofit escaping after the fact — i.e., build a tree, then walk it
and escape leaves before serialisation. That motivation is **gone**: `el()`
escapes unconditionally at the point of attribute construction. There is no
remaining path where a later "escape pass" would add safety.

---

## 3. Decision: Skip the Node Tree (Step 2 is YAGNI)

**Decision: do NOT build a mutable node tree.**

Reasoning:

1. **Primary motive already delivered.** The SVG-XSS / unescaped-attribute
   risk — the original motivation for this refactor — is solved structurally by
   `el()`. A node tree would have been one possible implementation of the same
   escaping guarantee, but `el()` achieves it with far less code and zero
   behavioural change.

2. **Unique benefit of a tree is post-build structural mutation.** A tree
   allows visiting and rewriting the output *after* it is logically assembled —
   e.g., to retroactively inject attributes, reorder children, or patch
   structure based on later-known context. The pre-pass in `scene_layout` is
   the only place in this codebase where such "retroactive patching" is needed,
   and it already handles it correctly and readably by computing the required
   data before the emit loop rather than after. There is no concrete case where
   post-build mutation would simplify anything.

3. **A tree would face the same `" />"` vs `"/>"` inconsistency.** The four
   remaining manual `<rect>` f-string sites all produce `"/>"`-terminated void elements
   matching the golden corpus. A tree's serialiser would need to reproduce this
   inconsistency — emitting `" />"` for elements produced via `el()` and `"/>"`
   for those produced manually — or accept a byte-level diff on the corpus. A
   tree does not, by itself, resolve this inconsistency; it just moves it.

4. **No complexity or bugs have been attributed to the coupling.** After
   careful reading of `scene_layout` and `to_svg`, the pre-pass is the correct
   and natural approach for an immutable-string emitter: compute what you need
   first, then emit once. The coupling is not a source of bugs and does not
   make the code hard to follow.

5. **Cost-benefit.** A mutable node tree would be a substantial addition (a new
   data structure, a serialiser, migration of all `el()` call sites to return
   nodes, a second round of pin-down verification) with no new capability beyond
   what already exists. The refactor would increase code size and introduce new
   failure modes (serialiser bugs, ordering bugs) for no observable gain.

---

## 4. Remaining Work: "Punkt 2" (Canonicalisation) — Out of This Refactor's Scope

Four `<rect>` emitter sites (by function) and one `<symbol>`/`<image>` block remain as
manual f-strings. These fall into two sub-groups:

**a. Void-format inconsistency (`"/>"`  vs `" />"`):**  
`el()` emits `" />"` (with space). The golden corpus has `"/>"`-terminated
void elements at: the background `<rect>`, the frame outline `<rect>` (in
`_render_frame_rect`), the clip-path inner `<rect>` (in
`_build_frame_clip_path`), and both mask inner `<rect>`s. Migrating these to
`el()` would produce a byte diff. Canonicalising to `" />"` across all sites
— which is valid XML/SVG — would require regenerating goldens, which is
deliberately deferred Punkt-2 work. This inconsistency is documented via
inline comments at each affected site.

**b. Image `<symbol>` block:**  
The `<symbol id="image-{file_id}"><image … /></symbol>` block uses f-strings.
The inner `<image>` is a non-void element (has `></image>` close tag) so it
does not hit the void-format issue, but `href="{data_url}"` inlines a
pre-escaped value (via `_escape_attr` called explicitly before the f-string).
This is safe but not structurally centralised. Migrating to `el()` would be
Punkt-2 cleanup.

**Neither of these is a correctness or security issue in the current corpus.**
Punkt-2 (canonicalisation) is a separate future task. It requires:
- Deciding on a canonical void format (`" />"` or `"/>"`)
- Regenerating all pin-down goldens to match
- Optionally migrating the image symbol block

This refactor (`svg-el-refactor`, Tasks 1–7) is complete without Punkt-2.

---

## 5. Summary Table

| Question | Answer |
|---|---|
| Does `el()` centralise escaping for the primary SVG-XSS risk? | **Yes** — all attribute values at 32 sites |
| Is the mutate-before-emit coupling a source of bugs or complexity? | **No** |
| Does a node tree deliver unique benefit not already provided by `el()`? | **No** |
| Does a node tree resolve the `" />"` vs `"/>"` inconsistency? | **No** — same problem in the serialiser |
| Decision on Step 2 (node tree) | **Skip — YAGNI** |
| Remaining work | Punkt-2 (canonicalisation) — separate future task |

---

## 6. When a node tree WOULD be genuinely required (the future trigger)

The skip decision is not "never build a tree" — it is "not for a **static, one-shot** exporter." The distinguishing property:

> **Static SVG export is a pure function of fully-known element data:** `output = f(input)`, with the entire input known up front. Anything a mutable tree would patch *after* building can instead be *pre-computed* in a pass (as `scene_layout` already does). So for this exporter, a tree is an ergonomics choice, never a capability requirement.

Checked against upstream Excalidraw's own DOM usage (`packages/excalidraw/renderer/staticSvgScene.ts`): every tree operation it performs is pre-computable string-side — post-hoc `setAttribute` (opacity/transform), `maybeWrapNodesInFrameClipPath`, deduplicated `<defs>` symbols/clipPaths, arrow-label masks. Our exporter replicates all of these via the pre-pass + string concatenation.

**A mutable node tree becomes genuinely REQUIRED only if the skill gains an *interactive / incremental* rendering mode** — i.e. a live editor that re-renders on each edit by **patching the changed node** instead of re-serialising the whole document (for performance). That requires stable node identity + in-place mutation over time; `output` is then incrementally derived from *previous output*, no longer a pure function of the input. That is Excalidraw's *canvas/editor*, NOT this skill's static `.excalidraw → SVG/PNG` one-shot generation.

The dividing line: **pure function (input fully known) → string builder + pre-pass wins; stateful mutation over time (output evolves incrementally) → tree required.** This exporter is the former. If it ever becomes the latter, revisit Step 2 as a NEW plan.

Note: the `" />"` vs `"/>"` void-format inconsistency (§4) is orthogonal — a tree's serialiser would face the same reproduce-or-canonicalise choice, so it is not a reason to build one.
