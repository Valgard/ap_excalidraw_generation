"""Deterministic builder for EVERY bundled exporter TTF.

Single entry point (`main`) that rebuilds all of font_files/ byte-reproducibly:
  - Excalidraw text fonts (Virgil, Excalifont, Cascadia, Comic Shanns, Nunito,
    Lilita One, Liberation Sans) from the ExcalidrawZ woff2 sources,
  - DejaVuSubset (Latin-free monochrome symbol fallback) from texlive DejaVu,
  - NotoColorEmoji from texlive, AppleColorEmoji extracted from the macOS TTC,
  - NotoSymbols (merged secondary symbol net) via tools/build_noto_symbols.py.

Determinism: every save goes through _fix_timestamps (recalcTimestamp=False +
zeroed head timestamps); the merged-Noto builder is SHA-256 pinned. Running this
twice yields byte-identical outputs (see the double-build check in the repo).

Requires: uv run --with fonttools --with brotli python tools/build_fonts.py

AppleColorEmoji.ttf is proprietary and therefore not in the repository. On macOS,
extract it from the system font without rebuilding anything else:
  uv run --with fonttools python tools/build_fonts.py --apple-emoji"""
import glob, os, pathlib
from fontTools.ttLib import TTFont
from fontTools.merge import Merger
from fontTools.subset import Subsetter, Options

# Fixed epoch so head.created/head.modified are deterministic across builds.
_EPOCH = 0
os.environ.setdefault("SOURCE_DATE_EPOCH", str(_EPOCH))

EZ = pathlib.Path("/Applications/ExcalidrawZ.app/Contents/Resources/excalidraw-latest")
NOTO = pathlib.Path("/usr/local/texlive/2026/texmf-dist/fonts/truetype/google/noto-emoji/NotoColorEmoji.ttf")
# DejaVu Sans (Bitstream Vera / Arev license — free to reproduce, distribute, modify;
# see font_files/LICENSE-DejaVuSans.txt). Bundled as a *symbol* fallback for glyphs the
# hand-drawn fonts, Cascadia and Noto all lack (e.g. ✗ U+2717, ✘ U+2718, ∼ U+223C).
DEJAVU = pathlib.Path("/usr/local/texlive/2026/texmf-dist/fonts/truetype/public/dejavu/DejaVuSans.ttf")
OUT = pathlib.Path(__file__).resolve().parent.parent / "font_files"

# Unicode blocks that hold "technical symbols" the hand-drawn text fonts lack.
# DejaVuSubset.ttf is subsetted to (these blocks ∩ DejaVu coverage) MINUS every glyph
# Noto already renders as a color emoji — so DejaVu is the single monochrome *symbol*
# fallback for glyphs a primary hand-drawn font lacks (arrows, math operators, dingbats
# incl. ✓ ✗ ✘, ∼, ∞, ≈ …).
#
# WHY A SUBSET (critical): resvg resolves the font for a whole <text> run at once. If a
# <tspan> names a fallback font that ALSO covers the surrounding Latin letters (e.g. the
# full Cascadia or full DejaVu), resvg mis-renders the *entire* run — the hand-drawn text
# flips to that font / sans-serif. Subsetting DejaVu to ONLY these symbol glyphs (no Latin
# coverage) means the fallback tspan can never "capture" the primary run. This mirrors why
# Noto Color Emoji is safe: it carries no Latin glyphs either.
_SYMBOL_BLOCKS = [
    (0x2190, 0x21FF),  # Arrows
    (0x2200, 0x22FF),  # Mathematical Operators
    (0x2300, 0x23FF),  # Miscellaneous Technical
    (0x2500, 0x257F),  # Box Drawing
    (0x25A0, 0x25FF),  # Geometric Shapes
    (0x2600, 0x26FF),  # Miscellaneous Symbols
    (0x2700, 0x27BF),  # Dingbats (holds ✓ ✗ ✘ …)
    (0x27F0, 0x27FF),  # Supplemental Arrows-A
    (0x2900, 0x297F),  # Supplemental Arrows-B
    (0x2A00, 0x2AFF),  # Supplemental Mathematical Operators
]
_EXTRA_SYMBOL_CPS = {0x00D7, 0x00F7, 0x2212}  # ×  ÷  − (minus sign)


def _fix_timestamps(font: TTFont) -> None:
    """Disable timestamp recalculation and zero head timestamps for byte-stable output.
    fontTools re-stamps head.modified at compile time via TTFont.recalcTimestamp;
    setting recalcTimestamp=False prevents that, and zeroing the fields handles
    any path that reads-then-rewrites (e.g. _rename_family's second TTFont load).
    """
    font.recalcTimestamp = False
    if "head" in font:
        font["head"].created = _EPOCH
        font["head"].modified = _EPOCH


def _to_ttf(woff2, dst):
    f = TTFont(woff2)
    f.flavor = None
    _fix_timestamps(f)
    f.save(dst)


def _rename_family(path, new_family, ps_name=None, unique_id=None):
    """Patch nameID=1 (Family) and nameID=4 (Full name) in-place so resvg fontdb
    matches by exactly the CSS token we put in font-family: "new_family, ...".
    Also removes nameID=16 (Preferred Family) which can shadow nameID=1 in some runtimes.
    If *ps_name* is given, also patch nameID=6 (PostScript name) — needed to reproduce
    a specific vendored byte layout (e.g. Virgil's "Virgil-Regular"); other callers omit it
    so their bytes stay unchanged. *unique_id* likewise patches nameID=3 (Unique ID).
    """
    def _enc(rec, value):
        return value.encode('utf-16-be') if rec.isUnicode() else value.encode('latin-1', errors='replace')

    f = TTFont(path)
    to_remove = []
    for rec in f['name'].names:
        if rec.nameID == 16:  # Preferred Family — remove to avoid ambiguity
            to_remove.append(rec)
        elif rec.nameID == 1:
            rec.string = _enc(rec, new_family)
        elif rec.nameID == 4:
            rec.string = _enc(rec, new_family + ' Regular')
        elif rec.nameID == 6 and ps_name is not None:
            rec.string = _enc(rec, ps_name)
        elif rec.nameID == 3 and unique_id is not None:
            rec.string = _enc(rec, unique_id)
    for rec in to_remove:
        f['name'].names.remove(rec)
    _fix_timestamps(f)
    f.save(path)


def _merge_subsets(glob_pattern, out_name, family_name=None):
    """Merge woff2 subsets into a single TTF, optionally renaming the family."""
    subs = sorted(glob.glob(str(EZ / glob_pattern)))
    if not subs:
        raise FileNotFoundError(f"No woff2 files matched: {EZ / glob_pattern}")
    out_path = str(OUT / out_name)
    if len(subs) == 1:
        _to_ttf(subs[0], out_path)
    else:
        tmp = []
        for i, w in enumerate(subs):
            stem = out_name.replace(".ttf", "")
            p = OUT / f".{stem}-sub-{i}.ttf"
            _to_ttf(w, p)
            tmp.append(str(p))
        merged = Merger().merge(tmp)
        _fix_timestamps(merged)
        merged.save(out_path)
        for p in tmp:
            pathlib.Path(p).unlink()
    if family_name:
        _rename_family(out_path, family_name)


def _cmap_set(name: str) -> set:
    f = TTFont(str(OUT / name))
    cmap = f.getBestCmap()
    return set(cmap.keys()) if cmap else set()


def _text_font_union() -> set:
    """Union of the cmaps of every text font (all FONT_FAMILY rendering codes)."""
    return (
        _cmap_set("Virgil.ttf") | _cmap_set("Excalifont-Regular.ttf")
        | _cmap_set("Cascadia.ttf") | _cmap_set("LiberationSans.ttf")
        | _cmap_set("Nunito.ttf") | _cmap_set("LilitaOne.ttf") | _cmap_set("ComicShanns.ttf")
    )


def _emoji_codepoints() -> set:
    """Codepoints in NotoColorEmoji that are NOT in any text font (the Noto routing set).
    Computed straight from the bundled TTFs."""
    return _cmap_set("NotoColorEmoji.ttf") - _text_font_union()


def _build_dejavu_subset() -> None:
    """Subset DejaVuSans.ttf → font_files/DejaVuSubset.ttf, keeping only the
    "technical symbol" glyphs (see _SYMBOL_BLOCKS) that Noto does not already render
    as a color emoji. Renames the family to "DejaVu Sans" (unchanged; the license
    only forbids the Bitstream/Vera names, which we do not use).

    Deliberately NOT restricted by the text fonts: the subset must carry every symbol a
    hand-drawn primary might lack (e.g. arrows, which live only in Cascadia among the text
    fonts). A little redundancy here is harmless. Excluding Noto's emoji codepoints keeps
    color emoji (⚠ ✅ …) flowing to Noto, not to monochrome DejaVu.

    CRUCIAL: the subset carries NO Latin coverage, so its fallback <tspan> can never capture
    the surrounding primary run in resvg (see _SYMBOL_BLOCKS note).
    """
    def _cmap_set_path(path) -> set:
        cmap = TTFont(str(path)).getBestCmap()
        return set(cmap.keys()) if cmap else set()

    dejavu = _cmap_set_path(DEJAVU)
    # Emoji codepoints (Noto minus the text fonts) are routed to Noto, never DejaVu —
    # exclude them so color emoji (⚠ ✅ …) don't get a monochrome DejaVu glyph instead.
    emoji_cps = _emoji_codepoints()

    block_cps = set(_EXTRA_SYMBOL_CPS)
    for lo, hi in _SYMBOL_BLOCKS:
        block_cps |= set(range(lo, hi + 1))
    # Residual = DejaVu-covered symbols that are not emoji-classified.
    keep = {cp for cp in block_cps if cp in dejavu and cp not in emoji_cps}

    f = TTFont(str(DEJAVU))
    opts = Options()
    opts.name_IDs = ["*"]          # keep name records (we patch nameID 1/4 below)
    opts.notdef_outline = True
    opts.recalc_bounds = True
    opts.glyph_names = False
    ss = Subsetter(options=opts)
    ss.populate(unicodes=sorted(keep))
    ss.subset(f)
    f.flavor = None
    _fix_timestamps(f)
    out_path = str(OUT / "DejaVuSubset.ttf")
    f.save(out_path)
    _rename_family(out_path, "DejaVu Sans")
    print(f"DejaVuSubset.ttf written: {len(keep)} symbol codepoints")


# Poisoner text fonts (Latin + symbols) that, when co-loaded with a hand-drawn
# font, let resvg pull a symbol-bearing hand-drawn run wholesale into them
# (usvg all_matched). We ship Latin-only subsets: same Latin/punctuation/digits,
# but with the "contested" symbol codepoints removed, so the subset can never
# cover a symbol run. A subset is a modified font, so it may not keep the original's
# name ("Cascadia Code" is an OFL Reserved Font Name, "Liberation" a Red Hat trademark):
# each gets its own family, which fonts.resvg_families() substitutes into the SVG.
_POISONER_SUBSETS = {
    "LiberationSans.ttf": ("SubsetSans.ttf", "SubsetSans"),
    "Cascadia.ttf": ("SubsetMono.ttf", "SubsetMono"),
}
# Hand-drawn text fonts whose symbol coverage defines "safe" codepoints that the
# poisoner subsets may retain. ALL five are included so the intersection protects the
# weakest font: a codepoint is only safe if EVERY hand-drawn font covers it. The union
# approach would leave ~18 poison holes — e.g. ™ (U+2122), † (U+2020), ∑ (U+2211),
# ∆ (U+2206), Ω (U+2126) — because some hand-drawn fonts cover those but not all do.
# Digits/space survive because all five fonts cover them (so they're in the intersection).
# Latin/punctuation is never in fallback_owned (Latin-free fallbacks), so no conflict.
_HANDDRAWN_FILES = ("Virgil.ttf", "Excalifont-Regular.ttf", "Nunito.ttf", "LilitaOne.ttf", "ComicShanns.ttf")

def _build_poisoner_latin_only() -> None:
    fallback_owned = (
        _cmap_set("DejaVuSubset.ttf") | _cmap_set("NotoSymbols.ttf")
        | _cmap_set("NotoColorEmoji.ttf")
    )
    # AppleColorEmoji.ttf is deliberately absent: it is optional (not in the repository),
    # and adding its cmap leaves both subsets unchanged (546 / 763 codepoints kept).
    # INTERSECTION: a codepoint is "safe" only if ALL hand-drawn fonts cover it.
    # This protects the weakest font — the one whose run poisons when a fallback font
    # also covers the same symbol. Using union (old bug) would leave ~18 poison holes
    # because symbols covered by some but not all hand-drawn fonts would survive in
    # the poisoner subset, letting a Virgil run containing e.g. ™ collapse.
    handdrawn_common = set.intersection(*[_cmap_set(name) for name in _HANDDRAWN_FILES])
    # Contested = fallback-owned codepoints not in EVERY hand-drawn font. Digits/space
    # are safe (all five cover them); Latin is never in fallback_owned (Latin-free fallbacks).
    contested = fallback_owned - handdrawn_common
    for src_name, (out_name, family) in _POISONER_SUBSETS.items():
        src = OUT / src_name
        keep = sorted(_cmap_set(src_name) - contested)
        f = TTFont(str(src))
        opts = Options()
        opts.name_IDs = ["*"]          # keep name records
        opts.notdef_outline = True
        opts.recalc_bounds = True
        opts.glyph_names = False
        ss = Subsetter(options=opts)
        ss.populate(unicodes=keep)
        ss.subset(f)
        f.flavor = None
        _fix_timestamps(f)
        out_path = str(OUT / out_name)
        f.save(out_path)
        _rename_family(out_path, family, ps_name=family, unique_id=family)
        print(f"{out_name}: kept {len(keep)} cps, dropped {len(_cmap_set(src_name)) - len(keep)} contested")


def _build_apple_emoji() -> bool:
    """Extract AppleColorEmoji.ttf from the system TTC if the bundled file is missing.

    Apple Color Emoji ships as a TTC (TrueType Collection) at:
      /System/Library/Fonts/Apple Color Emoji.ttc

    This function extracts font index 0 from that TTC and writes it as a plain TTF to
    font_files/AppleColorEmoji.ttf — but ONLY if the file does not already exist.
    Returns False when the system TTC is missing (non-macOS); emoji then render with
    NotoColorEmoji. main() treats that as optional, --apple-emoji as an error.

    The resulting TTF is used by resvg (via font_file_paths()) to render sbix colored emoji.
    Apple has no Latin letter coverage (cmap only: space, #, *, 0-9, ©, ®, plus emoji),
    so it cannot poison lettered runs in resvg.
    """
    APPLE_TTC = pathlib.Path("/System/Library/Fonts/Apple Color Emoji.ttc")
    out_path = OUT / "AppleColorEmoji.ttf"
    if out_path.exists():
        print(f"AppleColorEmoji.ttf already exists ({out_path.stat().st_size // 1024 // 1024} MB), skipping extraction")
        return True
    if not APPLE_TTC.exists():
        print(f"WARNING: {APPLE_TTC} not found (non-macOS?), skipping Apple emoji extraction")
        return False
    print(f"Extracting AppleColorEmoji font 0 from {APPLE_TTC} …")
    f = TTFont(str(APPLE_TTC), fontNumber=0)
    f.flavor = None
    _fix_timestamps(f)
    f.save(str(out_path))
    print(f"AppleColorEmoji.ttf written: {out_path.stat().st_size // 1024 // 1024} MB")
    return True


def main():
    # Apple Color Emoji: extract from system TTC (existence-guarded, no-op if already present)
    _build_apple_emoji()
    # Excalifont: merge subsets → full TTF
    _merge_subsets("fonts/Excalifont/*.woff2", "Excalifont-Regular.ttf")
    # Cascadia: full top-level woff2
    _to_ttf(str(EZ / "Cascadia.woff2"), str(OUT / "Cascadia.ttf"))
    # Noto Color Emoji: copy as TTF (already TTF)
    f = TTFont(str(NOTO))
    _fix_timestamps(f)
    f.save(str(OUT / "NotoColorEmoji.ttf"))
    # ComicShanns (code 8): merge 4 subsets → rename family to "Comic Shanns"
    _merge_subsets("fonts/ComicShanns/*.woff2", "ComicShanns.ttf", "Comic Shanns")
    # Nunito (code 6): merge 5 subsets → rename family to "Nunito"
    _merge_subsets("fonts/Nunito/*.woff2", "Nunito.ttf", "Nunito")
    # Lilita One (code 7): merge 2 subsets → "Lilita One" is already correct
    _merge_subsets("fonts/Lilita/*.woff2", "LilitaOne.ttf", "Lilita One")
    # Liberation Sans (codes 2 + 9): single woff2 → "Liberation Sans" is already correct
    _to_ttf(str(EZ / "fonts/LiberationSans/LiberationSans-Regular.woff2"), str(OUT / "LiberationSans.ttf"))
    # Virgil (code 1): woff2 → TTF, rename family "Virgil" + PostScript "Virgil-Regular".
    # (Source family is "Virgil 3 YOFF"; renaming is metadata-only — rendering is
    # pixel-identical to the vendored file, verified via render diff.)
    _to_ttf(str(EZ / "Virgil.woff2"), str(OUT / "Virgil.ttf"))
    _rename_family(str(OUT / "Virgil.ttf"), "Virgil", ps_name="Virgil-Regular")
    # DejaVu Sans symbol subset (primary symbol fallback: ✗ ✘ ∼ …).
    _build_dejavu_subset()
    # Merged Noto symbol fallback (secondary net after DejaVu, for rarer symbols).
    # SHA-256-pinned OFL sources → deterministic; see tools/build_noto_symbols.py.
    import build_noto_symbols
    try:
        build_noto_symbols.build()
        print("NotoSymbols.ttf built (merged Noto Symbols + Symbols2 + Math)")
    except Exception as e:  # network unavailable / upstream drift — keep existing file
        print(f"WARNING: NotoSymbols merge skipped ({type(e).__name__}: {e}); "
              f"using existing font_files/NotoSymbols.ttf if present")
    # Latin-only poisoner subsets (must run AFTER DejaVuSubset + NotoSymbols are built,
    # because _build_poisoner_latin_only reads their cmaps to compute fallback_owned).
    _build_poisoner_latin_only()
    print("fonts built:", sorted(p.name for p in OUT.glob("*.ttf")))


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--apple-emoji"]:
        sys.exit(0 if _build_apple_emoji() else 1)
    else:
        main()
