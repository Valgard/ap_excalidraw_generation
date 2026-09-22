# fonts.py — Excalidraw font mapping + SVG embedding (stdlib only).
# source: excalidraw constants.ts (FONT_FAMILY), common/utils.ts (getFontFamilyString),
#         packages/common/src/font-metadata.ts (metrics, getVerticalOffset)
# Font files are bundled in font_files/ (renamed from fonts/ to avoid Python namespace collision).
import base64
import pathlib

_DIR = pathlib.Path(__file__).parent / "font_files"

# FONT_FAMILY codes from packages/common/src/constants.ts
# 1=Virgil (deprecated), 2=Helvetica (deprecated, local; maps to LiberationSans TTF),
# 3=Cascadia (deprecated), 5=Excalifont (current default),
# 6=Nunito, 7=Lilita One, 8=Comic Shanns, 9=Liberation Sans
#
# NOTE: the bundled TTFs have been re-named so their internal family (name ID 1) is
# a SINGLE plain token — "Virgil"/"Cascadia"/"Excalifont". Two reasons: resvg matches
# fonts by this name, AND usvg's CSS parser rejects unquoted multi-word / numeric
# family values (the original "Virgil 3 YOFF" / "Cascadia Code" failed to parse and
# the text vanished under skip_system_fonts). Keep these in lockstep with the TTF
# name tables in font_files/.
FAMILY = {
    1: "Virgil",
    2: "Liberation Sans",    # Helvetica (deprecated) → metric-compatible Liberation Sans
    3: "Cascadia Code",      # matches the bundled Cascadia.ttf internal family (name ID 1)
    5: "Excalifont",
    6: "Nunito",
    7: "Lilita One",
    8: "Comic Shanns",
    9: "Liberation Sans",
}

# fonts.py — match @excalidraw/utils exactly (no sans-serif/monospace); resvg matches the
# first token against the bundled TTF's (renamed) family name.
# Code 2 (Helvetica) uses LiberationSans as a metric-compatible substitute.
_FALLBACK = {
    1: "Virgil, Segoe UI Emoji",
    2: "Liberation Sans, Segoe UI Emoji",
    # Code 3: the bundled TTF's internal family is the multi-word "Cascadia Code", so the
    # first CSS token MUST be the quoted exact name — resvg matches fontdb by that token
    # and, under skip_system_fonts, an unquoted bare "Cascadia" matches NOTHING (text
    # vanishes entirely). The quotes are XML-attr-escaped (→ &quot;) at emit time.
    3: '"Cascadia Code", Segoe UI Emoji',
    5: "Excalifont, Xiaolai, Segoe UI Emoji",
    6: "Nunito, Segoe UI Emoji",
    7: "Lilita One, Segoe UI Emoji",
    8: "Comic Shanns, Segoe UI Emoji",
    9: "Liberation Sans, Segoe UI Emoji",
}

# Filenames as bundled in font_files/ — TTF (not WOFF2): resvg's fontdb cannot
# decode Brotli-compressed WOFF2 ("malformed font"), so the bundled fonts are
# plain uncompressed TrueType, which resvg loads and matches by internal name.
# Codes 2 and 9 share the same LiberationSans.ttf file.
_FILE = {
    1: "Virgil.ttf",
    2: "LiberationSans.ttf",
    3: "Cascadia.ttf",
    5: "Excalifont-Regular.ttf",
    6: "Nunito.ttf",
    7: "LilitaOne.ttf",
    8: "ComicShanns.ttf",
    9: "LiberationSans.ttf",
}

# Emoji + symbol coverage fed to resvg for per-glyph fallback (glyphs absent from the
# text fonts — e.g. arrows in Excalifont, all emoji — resolve here without displacing the run).
# Segmentation in excalidraw_svg._render_text routes each glyph to the covering family via
# an explicit <tspan font-family=…>; these files must be loadable by resvg's fontdb so those
# tspans actually match. NotoColorEmoji = emoji; DejaVuSubset = last-resort technical symbols
# (✗ U+2717, ✘ U+2718, ∼ U+223C …) that neither the text fonts nor Cascadia nor Noto cover.
_FALLBACK_FILES = ["AppleColorEmoji.ttf", "NotoColorEmoji.ttf", "DejaVuSubset.ttf", "NotoSymbols.ttf"]

# Poison-guard tables: codes whose TTF contains hand-drawn glyphs (and thus symbols
# that can poison a resvg text run) vs. codes whose TTF is a full Latin+symbol font.
# When BOTH appear in a document, swap the poisoner for its Latin-only subset so resvg
# cannot pull a symbol-bearing hand-drawn run into it.
_HANDDRAWN_CODES = {1, 5, 6, 7, 8}
_POISONER_CODES = {2, 3, 9}
# Full poisoner TTF filename → Latin-only subset TTF filename (built by tools/build_fonts.py)
_LATIN_ONLY = {"LiberationSans.ttf": "LiberationLatinOnly.ttf",
               "Cascadia.ttf": "CascadiaLatinOnly.ttf"}

# Real metrics from packages/common/src/font-metadata.ts (verified 2026-07-04 via
# ExcalidrawZ bundle index-BonTAGtm.js font-metadata block).
# NOTE: The brief had Cascadia wrong (1000/950/-222); actual is 2048/1900/-480.
# Virgil (deprecated) matches Excalifont exactly (same base font, pre-rename).
# Code 2 (Helvetica) uses Helvetica's original metrics (not Liberation Sans metrics)
# so that existing diagrams using fontFamily=2 are vertically positioned correctly.
FONT_METRICS = {
    1: {"unitsPerEm": 1000, "ascender": 886,  "descender": -374, "lineHeight": 1.25},  # Virgil
    2: {"unitsPerEm": 2048, "ascender": 1577, "descender": -471, "lineHeight": 1.15},  # Helvetica (deprecated)
    3: {"unitsPerEm": 2048, "ascender": 1900, "descender": -480, "lineHeight": 1.20},  # Cascadia
    5: {"unitsPerEm": 1000, "ascender": 886,  "descender": -374, "lineHeight": 1.25},  # Excalifont
    6: {"unitsPerEm": 1000, "ascender": 1011, "descender": -353, "lineHeight": 1.25},  # Nunito
    7: {"unitsPerEm": 1000, "ascender": 923,  "descender": -220, "lineHeight": 1.15},  # Lilita One
    8: {"unitsPerEm": 1000, "ascender": 750,  "descender": -250, "lineHeight": 1.25},  # Comic Shanns
    9: {"unitsPerEm": 2048, "ascender": 1854, "descender": -434, "lineHeight": 1.15},  # Liberation Sans
}

# Fallback code used for any FONT_FAMILY code not in the tables above.
# Excalifont (code 5) is the current Excalidraw default font.
_UNKNOWN_FALLBACK_CODE = 5


def family_string(code: int, authentic_virgil: bool = False) -> str:
    """Return CSS font-family string for the given Excalidraw FONT_FAMILY code.

    For unknown codes, falls back to Excalifont (code 5) instead of raising KeyError.
    Deprecated Virgil (code 1) renders as Excalifont by default (matches Excalidraw);
    authentic_virgil=True keeps the genuine Virgil font.
    """
    if code == 1 and not authentic_virgil:
        code = 5
    return _FALLBACK.get(code, _FALLBACK[_UNKNOWN_FALLBACK_CODE])


def line_height(code: int) -> float:
    """Return unitless line-height multiplier for the given FONT_FAMILY code.

    For unknown codes, falls back to Excalifont (code 5).
    """
    return FONT_METRICS.get(code, FONT_METRICS[_UNKNOWN_FALLBACK_CODE])["lineHeight"]


def vertical_offset(code: int, font_size: float, line_height_px: float) -> float:
    """Compute the CSS top/vertical baseline offset in pixels.

    Mirrors getVerticalOffset() in packages/common/src/font-metadata.ts.

    Args:
        code: Excalidraw FONT_FAMILY code.
        font_size: Font size in pixels.
        line_height_px: Line height in pixels (font_size * lineHeight multiplier).

    Returns:
        Vertical offset in pixels (ascender contribution adjusted for line-gap).

    For unknown codes, falls back to Excalifont (code 5) metrics.
    """
    m = FONT_METRICS.get(code, FONT_METRICS[_UNKNOWN_FALLBACK_CODE])
    em = font_size / m["unitsPerEm"]
    line_gap = (line_height_px - em * m["ascender"] + em * m["descender"]) / 2
    return em * m["ascender"] + line_gap


def font_face_css() -> str:
    """Return CSS @font-face declarations for all bundled fonts (base64-embedded).

    Emits one block per unique TTF file (codes 2 and 9 share LiberationSans.ttf,
    so only one @font-face block with family "Liberation Sans" is emitted).

    Suitable for embedding in an SVG <defs><style> block or an HTML <style> tag
    so that renderers (Pillow/Cairo/Inkscape) can load the fonts without network access.
    """
    parts = []
    seen_files = set()
    for code in (1, 2, 3, 5, 6, 7, 8, 9):
        fname = _FILE[code]
        if fname in seen_files:
            continue  # codes 2 and 9 share LiberationSans.ttf — emit only once
        seen_files.add(fname)
        b64 = base64.b64encode((_DIR / fname).read_bytes()).decode("ascii")
        parts.append(
            f'@font-face {{ font-family: "{FAMILY[code]}"; '
            f'src: url(data:font/ttf;base64,{b64}) format("truetype"); }}'
        )
    return "\n".join(parts)


def used_codes(doc: dict) -> set:
    """FONT_FAMILY codes actually referenced by a document's live text elements.

    Frame-name labels render in the Helvetica/Liberation face (code 2), so a document
    containing any live frame implicitly needs code 2 too.
    """
    els = doc.get("elements", [])
    codes = {e["fontFamily"] for e in els
             if e.get("type") == "text" and not e.get("isDeleted") and e.get("fontFamily") is not None}
    if any(e.get("type") in ("frame", "magicframe") and not e.get("isDeleted") for e in els):
        codes.add(2)
    return codes


def font_file_paths(codes=None, authentic_virgil: bool = False) -> list:
    """Absolute paths of the bundled TTF files to hand to resvg's font loader.

    resvg ignores base64 ``@font-face`` in the SVG and matches fonts only from its own
    fontdb, so the exporter passes these files to ``svg_to_bytes(font_files=...)``.

    When *codes* is None, load ALL text fonts (back-compat). When a set of FONT_FAMILY
    codes is given (see ``used_codes``), load ONLY those text fonts plus the always-safe
    Latin-free fallbacks. This is load-bearing: resvg resolves a whole text run to a single
    font that covers every glyph in it, so if an UNUSED complete Latin+symbol font (e.g.
    LiberationSans) is loaded, a hand-drawn run containing a symbol (→ ✗ …) gets dragged
    into it — the "run poison" (verified: a Virgil line with → renders sans iff LiberationSans
    is loaded). Loading only referenced text fonts removes that trap; the Latin-free fallbacks
    (DejaVu subset, Apple/Noto emoji, Noto symbols) never poison, so they are always included.
    Deduplicates files shared across multiple codes (e.g. LiberationSans for codes 2+9).
    """
    want = (1, 2, 3, 5, 6, 7, 8, 9) if codes is None else sorted(c for c in codes if c in _FILE)
    seen = set()
    files = []
    for code in want:
        fname = _FILE[code]
        if code == 1 and not authentic_virgil:
            fname = _FILE[5]   # deprecated Virgil → Excalifont (matches ExcalidrawZ)
        if fname not in seen:
            seen.add(fname)
            files.append(fname)
    # Poison guard: if a hand-drawn font AND a Latin+symbol poisoner font are both
    # referenced, swap each poisoner for its symbol-stripped Latin-only subset so
    # resvg cannot pull a symbol-bearing hand-drawn run wholesale into it. Skipped
    # for codes is None (back-compat "load everything").
    if codes is not None:
        cs = set(codes)
        if cs & _HANDDRAWN_CODES and cs & _POISONER_CODES:
            files = [_LATIN_ONLY.get(f, f) for f in files]
    files.extend(_FALLBACK_FILES)
    return [str(_DIR / f) for f in files]
