# Design: A style layer (style guide + palette atoms) for the `excalidraw-generation` skill

- **Date:** 2026-06-29
- **Status:** Proposed (brainstorming) — pending user review → implementation plan
- **Scope:** Skill repository (the skill is standalone & shareable — stdlib only). Reference corpus for extraction: blog `.excalidraw` files from the blog's `articles/**/sources/` + talk `.excalidraw` files under talk source folders, plus `repro_paef.excalidraw`.

## Context

The 2026-06-29 rebuild gave the skill **mechanics** (a deterministic, binding-capable compiler + a `Diagram` facade) but **no shared visual vocabulary**. The fair reproduction tests showed the consequence directly: a blind builder, given only a diagram's intent, produced clean valid diagrams — but *invented* its own colour coding and spacing each time. Without a documented house style, every caller (including a colleague's Claude Code, since the skill is shared) drifts stylistically, even though each diagram is individually fine.

The author's existing diagrams are **not one style**. Curating the corpus (one language per diagram) yielded two deliberate families:

- A **house canon** (the majority — hand-drawn feel, Open-Color tints, airy layout).
- A **second, distinct style** the author wants preserved, whose polished nucleus is `repro_paef.excalidraw` (the better-than-original reproduction from the fair test: semantic colour-block cells, bound text, matrix layout).

Key principle the author established: **style is orthogonal to content type — the caller picks the style per diagram; the content type does not dictate it.**

## Goals

- A **style layer** shipped *inside the skill* (so the colleague inherits it), consisting of: documented conventions (a `style-guide.md`) plus the visual **atoms in code** (palette + semantic roles + font roles) so the house look is the path of least resistance.
- **Two named style families** on a shared atomic base, each archetype-differentiated, the caller choosing per diagram.
- **Consistency by default, freedom of composition.** The atoms (colours/fonts) are standardized; layout/composition stays the agent's judgment — because that freedom is exactly what produced the better `repro_paef` result.

## Non-Goals

- **Rigid archetype/style helpers** (e.g. `matrix(style="B")`, style-aware `panel`). *Considered, rejected* (Approach 3): they would straitjacket the composition freedom that made `repro_paef` better than its original.
- **Style enforcement / linting.** The layer is guidance + default atoms, not a checker. The agent applies judgment.
- **Mass-adapting the excluded diagrams into Style B now.** Style B is articulated from its nucleus; growing it by re-styling the excluded corpus is a future path (see §6).
- **Changing the compiler/determinism mechanics.** This layer only adds palette data + docs; `excalidraw_toolkit.py` is untouched (the new `excalidraw_palette.py` imports `FONT` from it and adds the new atoms).

## Design

### 1. Three-part model

- **Base atoms** (shared across all styles): the palette (named hues → fill/stroke), semantic colour roles, font roles. Constant everywhere.
- **Style A — "Sketch"** (the house canon): derived *empirically* from the curated reference set; differentiated by archetype (linear flow, layered architecture, comparison cards, timeline, chart, illustration, …). Hand-drawn feel, Open-Color tints, airy.
- **Style B — "Minimal":** a flat, clean, structured aesthetic whose **nucleus is `repro_paef`**; *articulated from that exemplar's principles* (semantic colour-block cells, bound text, matrix layout), not read from the excluded originals. Open to growth.

The caller chooses Style A or B for a given diagram; the content type does not force the choice.

### 2. Artifacts & files (new branch in the skill repo)

- `excalidraw_palette.py` — **created** — the atoms in code (data + tiny helpers, no layout logic). Imported by `excalidraw.py` / helpers and re-exported from the facade (`from excalidraw import PALETTE, SEMANTIC, role`).
- `style-guide.md` — **created** — the knowledge: base atoms, "choosing a style", Style A per-archetype idioms, Style B conventions.
- `SKILL.md` — **modified** — adds a short "Style layer" pointer (atoms + style guide); the mechanics/determinism sections stay.

### 3. The atoms (`excalidraw_palette.py`)

Plain data + a thin accessor. Indicative shape (exact shades confirmed by the extraction in §5, candidates from the corpus palette scan):

```python
PALETTE = {                                  # named hue -> fill (light) + stroke (dark)
    "blue":   {"fill": "#a5d8ff", "stroke": "#1971c2"},
    "blue_pale": {"fill": "#e7f5ff", "stroke": "#74c0fc"},
    "green":  {"fill": "#b2f2bb", "stroke": "#2f9e44"},
    "amber":  {"fill": "#ffe8cc", "stroke": "#e8590c"},
    "red":    {"fill": "#ffc9c9", "stroke": "#e03131"},
    "violet": {"fill": "#eebefa", "stroke": "#862e9c"},
    "gray":   {"fill": "#e9ecef", "stroke": "#868e96"},
    "dark":   {"fill": "#343a40", "stroke": "#1e1e1e"},
}
SEMANTIC = {                                 # role -> hue name
    "danger": "red", "success": "green", "warning": "amber",
    "info": "blue", "optional": "blue_pale", "neutral": "gray", "accent": "violet",
}
def role(name):                              # -> {"fill": ..., "stroke": ...}, splat into box()/rect()
    return dict(PALETTE[SEMANTIC[name]])
```

Usage: `d.box("x", ..., **role("danger"), text="…")`. `FONT` (already defined in the toolkit: `hand`/`code`/`normal`) is **re-exported** here — `excalidraw_palette.py` imports it from the toolkit (one-way, no cycle) and adds `TITLE`/`SUBTITLE` size+font defaults as named constants. No layout logic lives in this module.

### 4. The guide (`style-guide.md`)

Sections:
1. **Base atoms** — the palette table, the semantic-role mapping, the font roles, default sizes/spacing.
2. **Choosing a style** — Style A vs B, the caller decides, orthogonal to content type.
3. **Style A — Sketch** — per archetype: which palette roles, spacing, title/subtitle pattern, hand-drawn feel. Derived from the reference set.
4. **Style B — Minimal** — flat/clean colour-block cells coded by semantic outcome, bound text, matrix layout; derived from `repro_paef`; growth path noted.

### 5. Extraction method (the implementation work the plan executes)

- **Reference set (curated by the author), defined by complement** — everything in the one-language corpus *except* these non-matches:
  - Blog (10): `roocode/1-origin-story/{workflow-bug-investigation, workflow-enterprise, workflow-new-web-app}`, `roocode/2-technical-deepdive/team-lead-orchestrator`, `sdd/2-practice-learnings-153-commits/phase-timeline`, `metacognition-self-learning-ai-agents/{agent-architecture, reflexion-workflow, trap-framework}`, `ai-code-defect-profile/{paef-matrix, volume-quality}`.
  - Talk (4, Metacognition talk): base file, `Agenten-Komponenten`, `Trap Framework`, `Verticcal` (the Metacognition-talk `Timeline` **stays**).
  - Result: **~41 blog + ~34 talk ≈ 75 Style-A reference diagrams.**
- **Style A:** an agent fan-out clusters the 75 by archetype; per cluster an agent derives the conventions (palette usage, spacing, fonts, title/subtitle idioms). Parallel; synthesized into `style-guide.md` § Style A.
- **Style B:** a single agent articulates the conventions from `repro_paef.excalidraw` (the nucleus) into `style-guide.md` § Style B.
- **Atoms:** finalize `PALETTE`/`SEMANTIC` hex values from the empirical palette scan over the reference set (the candidates in §3 come from it).
- **Excluded set = Style B growth material (future):** the 14 non-matches are raw material to be *re-styled into Style B* later, enriching its exemplars — not descriptive of it, and not part of this v1.

### 6. Scope / phasing

- **v1:** the atoms module + `style-guide.md` (base + Style A empirical + Style B from nucleus) + SKILL.md pointer + tests.
- **Later:** name Style B; grow Style B by adapting the excluded diagrams; consider more styles. No rigid helpers unless real usage demands them.

## Testing / Verification

- `test_excalidraw_palette.py`: every `PALETTE` entry has valid 6-digit hex `fill`+`stroke`; every `SEMANTIC` role resolves to an existing `PALETTE` hue; `role(name)` returns a `{fill, stroke}` dict splat-able into `box()`; font-role constants are valid `FONT` keys.
- A **style-conformance example** (a small build that uses only `PALETTE`/`SEMANTIC`/`role`) writes + validates clean (`write()` → `[]`), proving the atoms integrate with the compiler.
- `style-guide.md` is reviewed by the author (not unit-testable).

## Open items (decided with the author, not blocking the plan)

- Style names are set: **Style A = "Sketch"**, **Style B = "Minimal"**.
- Final canonical hex shades per hue (confirmed during extraction; candidates already scanned).

## Commit (global skills repo — its own repo)

`feat(excalidraw-generation): add style layer — palette atoms + corpus-derived style guide`
