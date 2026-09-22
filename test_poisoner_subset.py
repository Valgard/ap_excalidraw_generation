# test_poisoner_subset.py
import pathlib
from fontTools.ttLib import TTFont

_DIR = pathlib.Path(__file__).parent / "font_files"

def test_liberation_latin_only_exists_and_strips_symbols():
    p = _DIR / "LiberationLatinOnly.ttf"
    assert p.exists(), "run the subset builder to generate it"
    cmap = TTFont(str(p)).getBestCmap()
    assert 0x41 in cmap, "must keep Latin 'A'"
    assert 0x30 in cmap, "must keep digit '0' (Apple covers it, but hand-drawn fonts do too)"
    assert 0x20 in cmap, "must keep space"
    assert 0x2192 not in cmap, "must drop arrow → (owned by DejaVu fallback)"
    assert 0x2122 not in cmap, "must drop ™ (some hand-drawn fonts cover it, not all → intersection strips it)"
    assert TTFont(str(p))["name"].getDebugName(1) == "Liberation Sans"

def test_cascadia_latin_only_exists_and_strips_symbols():
    p = _DIR / "CascadiaLatinOnly.ttf"
    assert p.exists()
    cmap = TTFont(str(p)).getBestCmap()
    assert 0x41 in cmap, "must keep Latin 'A'"
    assert 0x30 in cmap, "must keep digit '0'"
    assert 0x20 in cmap, "must keep space"
    assert 0x2192 not in cmap, "must drop arrow →"
    assert 0x2122 not in cmap, "must drop ™"
    assert TTFont(str(p))["name"].getDebugName(1) == "Cascadia Code"
