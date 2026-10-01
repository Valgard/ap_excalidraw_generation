# Excalidraw File Format Reference

Detailed reference for the `.excalidraw` JSON format, as enforced by
`excalidraw_toolkit.py`. Read this when extending the toolkit (new element types,
bindings) or debugging a file that the validator passes but a client still
refuses to open. For everyday diagram generation you only need `SKILL.md` and the
toolkit — you never touch raw fields.

These rules were learned empirically: a bulk audit once found 55 of 61 hand/early
generated files broken, all from the pitfalls below. Targets both Excalidraw.com
and ExcalidrawZ (a local Apple client with a stricter state validator).

## The six rules

### 1. `index` must be a valid fractional-indexing key

Excalidraw orders elements (z-order) with [rocicorp/fractional-indexing](https://github.com/rocicorp/fractional-indexing) keys.

- The prefix letter sets the integer-head length: `a` = 1 char, `b` = 2, `c` = 3.
- The **tail** (everything after the head) must **not end in `0`**.

| Valid | Invalid |
|-------|---------|
| `a1`, `a2`, … `a9`, `aA`, … `aZ`, `aa`, … `az` (prefix `a`, 1-char head, up to 61 elements) | `a00`, `ag0`, `af0` — head `a0`/`ag`/`af` + tail `0` → trailing-0 in the tail |
| `b30`, `b34` (prefix `b`, full 2-char integer head — a trailing 0 *inside* the head is fine) | |

`gen_key(i)` in the toolkit produces `a1..az` and refuses i>61 so you can't
silently overflow. For larger diagrams, switch to a `b`-prefix scheme.

**Why it bites:** ExcalidrawZ throws `invalid order key: ag0` on tab-switch
between files. Double-click open still works (it falls back to array order); the
strict validator only runs on internal state sync — so a file can "open fine"
once and break later.

### 2. `appState` — exactly five keys

```json
{
  "gridModeEnabled": false,
  "gridSize": 20,
  "gridStep": 5,
  "lockedMultiSelections": {},
  "viewBackgroundColor": "#ffffff"
}
```

Excalidraw.com trims to exactly these five on Save. Extra UI-state keys (zoom,
theme, currentItemStrokeColor, exportBackground, …) can trip strict parsers on
re-read; they are UI state, not file content. The validator flags both extra and
missing keys.

**But a client grows this back on open.** Opening the file in ExcalidrawZ (and
excalidraw.com on the next save) re-adds the trimmed UI-state keys, so a file merely
*viewed* in a client shows an `appState` diff in git with no change to the drawing.
That is benign churn — `tools/check_appstate.py` tells it apart from a real edit
(see SKILL.md § *Triaging edits after opening in a client*).

### 3. `textAlign: "right"` requires `autoResize: false`

With `autoResize: true` Excalidraw ignores the set `width` and shrinks the text
box to the rendered text width — which kills right-alignment (the box ends exactly
at the text). For right-aligned labels, set `autoResize: false` + a fixed `width`,
and position `x` so that `x + width` lands at the desired right edge. The toolkit's
`text()` does this automatically when `align="right"`.

### 4. Top-level key order

Emit keys in Save order: `type, version, source, elements, appState, files`. JSON
is formally unordered, but some strict parsers iterate sequentially.

### 5. Element required fields — no renderer fallback

The renderer has no defaults for certain keys; if they're missing, the open fails
or the element is silently dropped. `base_element()` sets all of these once.

**Always, on every element:**

| Field | Value / source | Why |
|-------|----------------|-----|
| `id` | unique string (nanoid-style) | required for binding refs (`boundElements`, `containerId`, `startBinding`) |
| `type` | `rectangle`/`ellipse`/`diamond`/`line`/`arrow`/`text`/`image`/`freedraw` | renderer dispatch |
| `x`, `y`, `width`, `height`, `angle` | numbers | geometry |
| `version` | integer ≥ 1 | per-element versioning |
| `versionNonce` | `random.randrange(1, 2**31)`, unique per element | collab conflict resolution; missing → re-open fails in newer versions |
| `seed` | random integer | roughjs seed; same seed = identical render across sessions |
| `isDeleted` | `false` | tombstone flag |
| `index` | fractional-indexing key (rule 1) | z-order |
| `frameId` | `null` if not in a frame | missing → frame-layout pass breaks |
| `strokeStyle` | `"solid"` / `"dashed"` / `"dotted"` | **critical**: no fallback → missing = hard open failure |
| `strokeColor`, `strokeWidth`, `backgroundColor`, `fillStyle`, `roughness`, `roundness`, `opacity` | Excalidraw defaults | rendering |
| `groupIds` | `[]` if nothing grouped | required array |
| `boundElements` | `null` or array | required (may be null) |
| `link`, `locked` | `null` / `false` | required metadata |

**Recommended (expected by modern parsers):**

| Field | Value | Why |
|-------|-------|-----|
| `updated` | Unix-ms timestamp (once per run, not per element) | history/restore logic; not always a parse-break, but safer |

**Type-specific required fields:**

- **`text`**: `text`, `originalText`, `fontSize`, `fontFamily`, `textAlign`,
  `verticalAlign`, `lineHeight`. With `textAlign: "right"` → `autoResize: false` +
  fixed `width` (rule 3). `fontFamily`: `1` = hand-drawn, `2` = normal, `3` = code,
  `5` = a normal/bold variant used by the toolkit for emphasis.
- **`line` / `arrow`**: `points` (array of relative `[dx, dy]` pairs, starting with
  `[0, 0]`), `startArrowhead`, `endArrowhead` (arrow only), optionally
  `startBinding`/`endBinding` for arrows attached to shapes.
- **`text` inside a container**: `containerId` on the text + a matching
  `{type: "text", id: <textId>}` entry in the container's `boundElements`. (The
  toolkit's `text()` is standalone; add bindings by hand if you need bound labels —
  see "bound text" below.)

### 6. Python string delimiters for labels with ASCII quotes

When you build text labels in Python and a label contains an ASCII double-quote
`"`, a `"..."` Python string breaks. Strategies, in order of preference:

1. **Single-quote the Python string**: `'He said "hi"'` — no escaping, reads clean.
2. **Use curly quotes** (U+201C/U+201D) in the label — typographically nicer for
   published artifacts. But if the label must show a literal ASCII quote (a code
   snippet, a JSON string), keep ASCII and use strategy 1.
3. **Triple-quoted strings** for long multi-line labels.
4. **Backslash escape** `\"` — last resort, visually noisy.

Before running a generator: `python3 -c "import ast; ast.parse(open('gen.py').read())"`
catches quote/syntax errors without executing.

## Bound text (centered label inside a shape)

The toolkit's `text()` is a standalone text element positioned over a box — simple
and robust. If you want a *bound* label (moves/centers with the container), set on
the text element: `containerId = <rect id>`, and add to the rect's `boundElements`:
`[{"type": "text", "id": <text id>}]`. Bound text is harder to get right (geometry
is recomputed by Excalidraw) — prefer standalone overlay text unless you need the
box to resize around the label.

## Binding fields

### Container ↔ bound-text reciprocity

Two fields must always be set in tandem:

- On the **text element**: `containerId` set to the container's `id`.
- On the **container element**: `boundElements` array must include
  `{"type": "text", "id": <text-element-id>}`.

If either half is missing, the validator flags it as a dangling binding. The
toolkit's `label()` function sets both sides atomically — call it instead of
setting the fields by hand.

### Arrow bindings (`startBinding` / `endBinding`)

Each binding is a dict with three keys:

```json
{
  "elementId": "<id of the shape being attached to>",
  "focus":     0.0,
  "gap":       1
}
```

- `elementId` — the id of the shape the arrow end is glued to.
- `focus` — fractional position along the shape's edge where the arrow attaches
  (`0.0` = center, `−1`/`+1` = the two extremes). The toolkit's `connect()` uses
  `0.0` (center-to-center, geometrically adjusted).
- `gap` — pixel gap between the arrow tip and the shape boundary. Use `1` for
  tight attachment.

The corresponding shape must also list the arrow in its `boundElements`:
`{"type": "arrow", "id": <arrow-id>}`. Again, `connect()` handles both sides.

### `fillStyle` — hachure

There is no dedicated `fill` kwarg for hachure in the toolkit. When you want the
sketchy cross-hatched fill, set `fillStyle` directly on the returned element dict
after creation:

```python
box = d.box("my-box", 0, 0, 200, 100, fill="#d0ebff")
box["fillStyle"] = "hachure"
```

Other valid values for `fillStyle`: `"solid"` (default), `"cross-hatch"`,
`"dots"`, `"zigzag"`, `"zigzag-line"`. Hachure and solid are by far the most
common — the toolkit defaults to solid.

## Debugging a file the validator passes but a client rejects

Diff the element-key union between a known-good file and the broken one:

```python
import json
good = {k for el in json.load(open("good.excalidraw"))["elements"] for k in el}
bad  = {k for el in json.load(open("bad.excalidraw"))["elements"] for k in el}
print("in good, not in bad:", good - bad)
```

A field the validator doesn't yet know about will show up here.
