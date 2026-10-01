# excalidraw-generation

A Claude Code skill for generating `.excalidraw` diagram files from code instead
of drawing them by hand. Hand-written Excalidraw JSON tends to look right and
still break in strict parsers; the skill ships the format rules that make files
open cleanly in Excalidraw.com and local clients (ExcalidrawZ), a Python toolkit
with a validator, and a deterministic SVG/PNG exporter.

## Layout

```
.claude-plugin/plugin.json                 plugin manifest
skills/excalidraw-generation/SKILL.md      entry point: workflow, rules, pitfalls
skills/excalidraw-generation/*.py          toolkit, SVG renderer, PNG export
skills/excalidraw-generation/font_files/   bundled fonts + their licenses
skills/excalidraw-generation/tools/        dev-time builders and diagnostics
docs/specs/                                design documents
```

## Installation

From the repository root:

```bash
ln -s "$PWD/skills/excalidraw-generation" ~/.claude/skills/excalidraw-generation
```

Generating diagrams needs only the Python standard library. PNG export runs as
a `uv` script with pinned dependencies (`resvg-py`); see
`skills/excalidraw-generation/png-export.md`.

### Apple Color Emoji (optional, macOS)

Apple Color Emoji is proprietary and not part of this repository. Without it,
emoji render with Noto Color Emoji. To match diagrams exported on a Mac, extract
it from the system font once:

```bash
cd skills/excalidraw-generation
uv run --with fonttools python tools/build_fonts.py --apple-emoji
```

The file is git-ignored and picked up automatically when present.

## Tests

```bash
cd skills/excalidraw-generation
uv run run_tests.py
```

The runner supplies the rendering dependencies, so the PNG tests run instead
of being skipped. Without the extracted Apple font, its one rendering test is
skipped.

## Fonts

Every bundled font carries its license under `font_files/LICENSE-*.txt`.
`SubsetSans.ttf` and `SubsetMono.ttf` are Latin-only subsets of Liberation Sans
and Cascadia Code. They keep a hand-drawn line from being rendered in the wrong
font when a diagram mixes font families. Because they are modified versions,
they carry their own names, as the Liberation agreement and the OFL Reserved
Font Name require.
