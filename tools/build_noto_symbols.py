#!/usr/bin/env python3
"""Deterministic builder for the merged Noto symbol fallback font.

Produces ``font_files/NotoSymbols.ttf`` — the *secondary* symbol fallback (used
by the exporter only for symbols the primary DejaVu subset does not cover).

Why a dedicated builder: the exporter routes every glyph to a concrete font via
``<tspan>`` because resvg does **font-level** fallback only, never per-glyph (a
missing glyph renders blank, it is not searched for in other loaded fonts). To
give one clean symbol family to route to, the three Noto symbol fonts
(Symbols, Symbols 2, Math) are merged into a single TTF. ``fontTools.merge``
cannot merge OpenType layout / variation tables (MATH, GSUB/GPOS, HVAR, STAT,
VarStore …), so each source is first reduced to a uniform minimal table set.

Pipeline (per source): download (SHA-256 pinned) -> instantiate variable axes ->
keep only glyph-outline tables -> merge all three -> subset to codepoints
>= U+2000 (drops every ASCII/Latin glyph, so the resulting tspan can never
poison a hand-drawn run in resvg) -> zero timestamps for byte-deterministic
output.

Deterministic: same pinned sources always yield a byte-identical TTF (zeroed
head timestamps, ``recalcTimestamp=False``, stable merge/subset ordering). Run
it twice and compare SHA-256 to confirm.

Run:  uv run --with fonttools python tools/build_noto_symbols.py
Deps: fontTools (build-time only; the runtime never imports this).
"""
from __future__ import annotations

import hashlib
import pathlib
import tempfile
import urllib.request

from fontTools import merge, subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

# --- pinned OFL sources (Google Fonts repo). SHA-256 guarantees deterministic
#     input; if a hash mismatches, the build fails loudly instead of drifting. ---
SOURCES = [
    {
        "name": "NotoSansSymbols[wght].ttf",
        "url": "https://github.com/google/fonts/raw/main/ofl/notosanssymbols/NotoSansSymbols%5Bwght%5D.ttf",
        "sha256": "f7e7e04b4a24b6c78893d50cbfd2b2f6cae49617ab047bfef668d252adb128f7",
        "instance": {"wght": 400},  # variable font -> pin to Regular
    },
    {
        "name": "NotoSansSymbols2-Regular.ttf",
        "url": "https://github.com/google/fonts/raw/main/ofl/notosanssymbols2/NotoSansSymbols2-Regular.ttf",
        "sha256": "7d5fb73b7ca67a6798101741f5d280a3d016a56a197afcd4199dbb57b4b82a21",
        "instance": None,
    },
    {
        "name": "NotoSansMath-Regular.ttf",
        "url": "https://github.com/google/fonts/raw/main/ofl/notosansmath/NotoSansMath-Regular.ttf",
        "sha256": "3f495fe933c06786e4d5f6d86b8ee70b6753a68ee3b9d87528726de0f6e2c47d",
        "instance": None,
    },
]

# Only glyph-outline + required tables survive the strip. Everything else
# (MATH, GSUB, GPOS, GDEF, HVAR, VVAR, MVAR, STAT, fvar, gvar, avar, VarStore …)
# both breaks fontTools.merge and is unused for pure glyph rendering in resvg.
KEEP_TABLES = {"glyf", "loca", "cmap", "head", "hhea", "hmtx", "maxp", "name", "OS/2", "post"}

MIN_CODEPOINT = 0x2000  # drop all ASCII/Latin-1 -> Latin-free -> resvg poison-safe
FAMILY_NAME = "Noto Sans Symbols"  # merged family; the exporter quotes it in tspans

GEN = pathlib.Path(__file__).resolve().parent.parent
OUT = GEN / "font_files" / "NotoSymbols.ttf"
CACHE = pathlib.Path(tempfile.gettempdir()) / "excalidraw-noto-src-cache"


def _fetch(src: dict) -> pathlib.Path:
    """Download (or reuse cached) source, verifying the pinned SHA-256."""
    CACHE.mkdir(parents=True, exist_ok=True)
    dst = CACHE / src["name"].replace("[", "_").replace("]", "_")
    if dst.exists() and hashlib.sha256(dst.read_bytes()).hexdigest() == src["sha256"]:
        return dst
    req = urllib.request.Request(src["url"], headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=60).read()  # noqa: S310 (pinned host)
    got = hashlib.sha256(data).hexdigest()
    if got != src["sha256"]:
        raise SystemExit(
            f"SHA-256 mismatch for {src['name']}:\n  expected {src['sha256']}\n  got      {got}\n"
            f"  The upstream font changed — review and re-pin before trusting the build."
        )
    dst.write_bytes(data)
    return dst


def _prep(path: pathlib.Path, instance: dict | None) -> pathlib.Path:
    """Instantiate variable axes, then keep only KEEP_TABLES; write to a temp TTF."""
    font = TTFont(path)
    if "fvar" in font and instance is not None:
        font = instancer.instantiateVariableFont(font, instance, inplace=False)
    for tag in [t for t in list(font.keys()) if t not in KEEP_TABLES]:
        del font[tag]
    out = CACHE / (path.stem + ".min.ttf")
    font.save(out)
    return out


def _make_deterministic(font: TTFont) -> None:
    """Zero head timestamps AND disable recalc so the saved bytes never depend on
    build time. TTFont.save() defaults to recalcTimestamp=True and would otherwise
    re-stamp head.modified with the current time — the sole non-determinism here."""
    font.recalcTimestamp = False
    head = font["head"]
    head.created = 0
    head.modified = 0


def _rebuild_name(font: TTFont, family: str) -> None:
    """Replace the name table with a fixed, minimal set (deterministic + non-empty
    after subsetting drops the originals). Both Windows (3,1,0x409) and Mac (1,0,0)."""
    name = font["name"]
    name.names = []
    ps = family.replace(" ", "")
    records = {1: family, 2: "Regular", 3: ps, 4: family, 6: ps}
    for platformID, platEncID, langID in ((3, 1, 0x409), (1, 0, 0)):
        for nameID, value in records.items():
            name.setName(value, nameID, platformID, platEncID, langID)


def build() -> pathlib.Path:
    prepped = [_prep(_fetch(s), s["instance"]) for s in SOURCES]

    # Merge the reduced trio into one font (later sources fill glyphs the earlier lack).
    merged = merge.Merger().merge([str(p) for p in prepped])

    # Subset to symbol codepoints only (>= U+2000) -> Latin-free, poison-safe.
    keep = sorted(cp for cp in merged.getBestCmap() if cp >= MIN_CODEPOINT)
    ss = subset.Subsetter(options=subset.Options(
        notdef_glyph=True, glyph_names=False, recalc_bounds=False,
        recalc_timestamp=False, layout_features=[], name_IDs=[],
    ))
    ss.populate(unicodes=keep)
    ss.subset(merged)

    _rebuild_name(merged, FAMILY_NAME)
    _make_deterministic(merged)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    merged.save(OUT)
    return OUT


if __name__ == "__main__":
    out = build()
    f = TTFont(out)
    cmap = f.getBestCmap()
    syms = sum(1 for c in cmap if (0x2000 <= c <= 0x2E7F) or (0x1D000 <= c <= 0x1FBFF))
    has_latin = any(c in cmap for c in list(range(0x41, 0x5B)) + list(range(0x61, 0x7B)))
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"wrote {out}")
    print(f"  size={out.stat().st_size / 1024:.0f} KB  family={f['name'].getDebugName(1)!r}")
    print(f"  codepoints={len(cmap)}  symbols={syms}  latin={has_latin}")
    print(f"  sha256={sha}")
