# test_poisoner_subset.py
import pathlib
from fontTools.ttLib import TTFont

_DIR = pathlib.Path(__file__).parent / "font_files"

# Name records that identify a font (family, unique id, full name, PostScript name,
# typographic/WWS family+subfamily, compatible full name). A modified font may not
# carry a reserved name in any of them: Cascadia Code is an OFL Reserved Font Name,
# Liberation is a Red Hat trademark. Copyright (0) and trademark notices (7) stay.
_IDENTIFYING_NAME_IDS = {1, 3, 4, 6, 16, 17, 18, 21, 22}


def _identifying_names(font):
    return {r.toUnicode() for r in font["name"].names if r.nameID in _IDENTIFYING_NAME_IDS}


def test_sans_latin_subset_exists_and_strips_symbols():
    p = _DIR / "SubsetSans.ttf"
    assert p.exists(), "run the subset builder to generate it"
    cmap = TTFont(str(p)).getBestCmap()
    assert 0x41 in cmap, "must keep Latin 'A'"
    assert 0x30 in cmap, "must keep digit '0' (Apple covers it, but hand-drawn fonts do too)"
    assert 0x20 in cmap, "must keep space"
    assert 0x2192 not in cmap, "must drop arrow → (owned by DejaVu fallback)"
    assert 0x2122 not in cmap, "must drop ™ (some hand-drawn fonts cover it, not all → intersection strips it)"
    assert TTFont(str(p))["name"].getDebugName(1) == "SubsetSans"


def test_mono_latin_subset_exists_and_strips_symbols():
    p = _DIR / "SubsetMono.ttf"
    assert p.exists()
    cmap = TTFont(str(p)).getBestCmap()
    assert 0x41 in cmap, "must keep Latin 'A'"
    assert 0x30 in cmap, "must keep digit '0'"
    assert 0x20 in cmap, "must keep space"
    assert 0x2192 not in cmap, "must drop arrow →"
    assert 0x2122 not in cmap, "must drop ™"
    assert TTFont(str(p))["name"].getDebugName(1) == "SubsetMono"


def test_subsets_carry_no_reserved_name():
    for fname in ("SubsetSans.ttf", "SubsetMono.ttf"):
        names = _identifying_names(TTFont(str(_DIR / fname)))
        leaked = {n for n in names if "Liberation" in n or "Cascadia" in n}
        assert not leaked, f"{fname} still identifies as {leaked}"
