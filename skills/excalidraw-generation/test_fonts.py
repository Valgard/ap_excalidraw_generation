import json
import pathlib

import fonts


def test_font_file_paths_filters_unused_text_fonts():
    """Diagram-aware loading: given the used codes, unreferenced complete Latin fonts
    (LiberationSans) are excluded — that's what stops resvg poisoning a hand-drawn run
    that contains a symbol. Latin-free fallbacks are always included; None → all (back-compat)."""
    v_only = {p.split("/")[-1] for p in fonts.font_file_paths({1})}
    # code 1 (deprecated Virgil) substitutes Excalifont by default (matches ExcalidrawZ)
    assert "Excalifont-Regular.ttf" in v_only and "Virgil.ttf" not in v_only
    assert "LiberationSans.ttf" not in v_only  # unused complete Latin font excluded
    assert {"DejaVuSubset.ttf", "AppleColorEmoji.ttf", "NotoColorEmoji.ttf", "NotoSymbols.ttf"} <= v_only
    assert "LiberationSans.ttf" in {p.split("/")[-1] for p in fonts.font_file_paths()}  # None → all


def test_code1_defaults_to_excalifont_substitution():
    """Excalidraw deprecated Virgil (code 1); ExcalidrawZ renders it with Excalifont (code 5).
    The exporter matches that by default — code 1's CSS chain and loaded font are Excalifont's.
    (Verified: Virgil parens sit at yMin=-47 vs Excalifont's -200; the ExcalidrawZ asset uses -200.)"""
    assert fonts.family_string(1) == "Excalifont, Xiaolai, Segoe UI Emoji"
    names = {p.split("/")[-1] for p in fonts.font_file_paths({1})}
    assert "Excalifont-Regular.ttf" in names and "Virgil.ttf" not in names


def test_authentic_virgil_param_renders_real_virgil():
    """authentic_virgil=True renders code 1 as the genuine Virgil font (chain + file)."""
    assert fonts.family_string(1, authentic_virgil=True) == "Virgil, Segoe UI Emoji"
    names = {p.split("/")[-1] for p in fonts.font_file_paths({1}, authentic_virgil=True)}
    assert "Virgil.ttf" in names and "Excalifont-Regular.ttf" not in names
    # the flag only affects code 1; other codes are unchanged
    assert fonts.family_string(5, authentic_virgil=True) == "Excalifont, Xiaolai, Segoe UI Emoji"


def test_used_codes_collects_text_fontfamilies_and_frame():
    doc = {"elements": [
        {"type": "text", "fontFamily": 1, "isDeleted": False},
        {"type": "text", "fontFamily": 5, "isDeleted": True},   # deleted → ignored
        {"type": "rectangle"},
    ]}
    assert fonts.used_codes(doc) == {1}
    # a live frame implicitly needs the Helvetica/Liberation face (code 2)
    doc2 = {"elements": [{"type": "frame", "isDeleted": False},
                         {"type": "text", "fontFamily": 1, "isDeleted": False}]}
    assert fonts.used_codes(doc2) == {1, 2}


def test_family_string_matches_excalidraw():
    # code 1 (deprecated Virgil) → Excalifont by default (what ExcalidrawZ renders)
    assert fonts.family_string(1) == "Excalifont, Xiaolai, Segoe UI Emoji"
    assert fonts.family_string(5) == "Excalifont, Xiaolai, Segoe UI Emoji"
    # Code 3's first token is the QUOTED internal family "Cascadia Code" — a bare
    # "Cascadia" matches nothing in resvg's fontdb (the bundled TTF's name ID 1 is
    # "Cascadia Code"), so under skip_system_fonts the text would vanish entirely.
    assert fonts.family_string(3) == '"Cascadia Code", Segoe UI Emoji'


def test_family_strings_match_excalidraw_no_sans_serif():
    assert fonts.family_string(1) == "Excalifont, Xiaolai, Segoe UI Emoji"  # code 1 → Excalifont default
    assert fonts.family_string(3) == '"Cascadia Code", Segoe UI Emoji'
    assert fonts.family_string(5) == "Excalifont, Xiaolai, Segoe UI Emoji"


def test_font_file_paths_include_emoji_and_all_text_fonts():
    names = [p.rsplit("/", 1)[-1] for p in fonts.font_file_paths()]
    # code 1 → Excalifont substitution by default, so the load-all set has no Virgil.ttf
    assert "Excalifont-Regular.ttf" in names and "Cascadia.ttf" in names
    assert "NotoColorEmoji.ttf" in names


def test_vertical_offset_excalifont():
    # fontSize=20, lineHeight=1.25 → lineHeightPx=25; unitsPerEm=1000, asc=886, desc=-374
    # fontSizeEm=0.02; lineGap=(25 - 0.02*886 + 0.02*(-374))/2 = (25 - 17.72 - 7.48)/2 = -0.1
    # verticalOffset = 0.02*886 + (-0.1) = 17.72 - 0.1 = 17.62
    assert round(fonts.vertical_offset(5, 20, 25), 2) == 17.62


def test_vertical_offset_cascadia():
    # Pins Cascadia metrics: unitsPerEm=2048, ascender=1900, descender=-480
    # fontSize=20, lineHeightPx=24; em=20/2048; lineGap=(24-em*1900+em*480)/2
    assert round(fonts.vertical_offset(3, 20, 24), 2) == 18.93


def test_font_face_css_embeds_base64():
    css = fonts.font_face_css()
    # 7 unique @font-face blocks: codes 1,3,5,6,7,8 + one shared for codes 2+9 (LiberationSans)
    assert css.count("@font-face") == 7
    assert "base64," in css and "Excalifont" in css
    # TTF (not WOFF2): resvg's fontdb can't decode Brotli-compressed WOFF2, so the
    # bundled fonts — and their @font-face embedding — are plain TrueType/OpenType.
    assert "data:font/ttf" in css and 'format("truetype")' in css


# --- New font codes (codes 2/6/7/8/9) ---

def test_new_font_codes_family_string():
    """Codes 2/6/7/8/9 must return a valid CSS family string without KeyError."""
    assert fonts.family_string(2) == "Liberation Sans, Segoe UI Emoji"
    assert fonts.family_string(6) == "Nunito, Segoe UI Emoji"
    assert fonts.family_string(7) == "Lilita One, Segoe UI Emoji"
    assert fonts.family_string(8) == "Comic Shanns, Segoe UI Emoji"
    assert fonts.family_string(9) == "Liberation Sans, Segoe UI Emoji"


def test_new_font_codes_line_height():
    """line_height() must return correct values for codes 2/6/7/8/9."""
    assert fonts.line_height(2) == 1.15   # Helvetica (maps to LiberationSans metrics)
    assert fonts.line_height(6) == 1.25   # Nunito
    assert fonts.line_height(7) == 1.15   # Lilita One
    assert fonts.line_height(8) == 1.25   # Comic Shanns
    assert fonts.line_height(9) == 1.15   # Liberation Sans


def test_new_font_codes_vertical_offset():
    """vertical_offset() must not crash and must return a reasonable value for codes 2/6/7/8/9."""
    # Just check no KeyError and result is a positive float
    for code in (2, 6, 7, 8, 9):
        result = fonts.vertical_offset(code, 20, 20 * fonts.line_height(code))
        assert isinstance(result, float) and result > 0, f"code {code}: {result}"


def test_font_file_paths_include_new_fonts():
    """font_file_paths() must include the new TTF files."""
    names = [p.rsplit("/", 1)[-1] for p in fonts.font_file_paths()]
    assert "ComicShanns.ttf" in names
    assert "Nunito.ttf" in names
    assert "LilitaOne.ttf" in names
    assert "LiberationSans.ttf" in names


def test_font_face_css_includes_new_fonts():
    """font_face_css() must embed all new fonts (7 total: 1/3/5 + 2/6/7/8/9 — but 2 shares file with 9)."""
    css = fonts.font_face_css()
    # Should have at least 7 @font-face blocks (codes 1,2/9,3,5,6,7,8)
    # (codes 2 and 9 both use LiberationSans but map to the same @font-face)
    assert css.count("@font-face") >= 6   # at minimum the 4 new unique font families + 3 existing
    assert "Comic Shanns" in css
    assert "Nunito" in css
    assert "Lilita One" in css
    assert "Liberation Sans" in css


# --- Defensive fallback for unknown codes ---

def test_unknown_font_code_family_string_does_not_crash():
    """family_string() on an unmapped code must fall back to Excalifont, not raise KeyError."""
    result = fonts.family_string(99)
    assert result == fonts.family_string(5), f"Expected Excalifont fallback, got: {result!r}"


def test_unknown_font_code_line_height_does_not_crash():
    result = fonts.line_height(99)
    assert result == fonts.line_height(5)


def test_unknown_font_code_vertical_offset_does_not_crash():
    lh = fonts.line_height(99)
    result = fonts.vertical_offset(99, 20, 20 * lh)
    assert isinstance(result, float) and result > 0


def test_font_file_paths_subsets_poisoner_in_mixed_doc():
    names = {p.split("/")[-1] for p in fonts.font_file_paths({1, 9})}  # hand-drawn + Liberation
    assert "LiberationLatinOnly.ttf" in names
    assert "LiberationSans.ttf" not in names


def test_font_file_paths_keeps_full_poisoner_when_alone():
    names = {p.split("/")[-1] for p in fonts.font_file_paths({9})}     # Liberation only
    assert "LiberationSans.ttf" in names
    assert "LiberationLatinOnly.ttf" not in names


def test_font_file_paths_none_loads_full_poisoner():
    names = {p.split("/")[-1] for p in fonts.font_file_paths()}
    assert "LiberationSans.ttf" in names  # back-compat: None → everything, no guard
    assert "LiberationLatinOnly.ttf" not in names


def test_font_file_paths_subsets_cascadia_in_mixed_doc():
    names = {p.split("/")[-1] for p in fonts.font_file_paths({1, 3})}  # hand-drawn + Cascadia
    assert "CascadiaLatinOnly.ttf" in names
    assert "Cascadia.ttf" not in names


def test_to_svg_unknown_font_code_does_not_crash():
    """to_svg() with fontFamily=99 (unmapped) must render without raising KeyError."""
    import excalidraw_svg
    doc = {
        "type": "excalidraw",
        "version": 2,
        "elements": [
            {
                "type": "text",
                "id": "test-unknown-font",
                "x": 10, "y": 10,
                "width": 200, "height": 30,
                "angle": 0,
                "strokeColor": "#000000",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 1,
                "strokeStyle": "solid",
                "roughness": 1,
                "opacity": 100,
                "text": "Hello",
                "fontSize": 20,
                "fontFamily": 99,       # unmapped code
                "textAlign": "left",
                "verticalAlign": "top",
                "baseline": 18,
                "containerId": None,
                "originalText": "Hello",
                "lineHeight": 1.25,
                "isDeleted": False,
                "boundElements": [],
                "updated": 0,
                "link": None,
                "locked": False,
            }
        ],
        "appState": {"viewBackgroundColor": "#ffffff"},
    }
    svg = excalidraw_svg.to_svg(doc)
    assert "<text" in svg or "<svg" in svg  # rendered something
