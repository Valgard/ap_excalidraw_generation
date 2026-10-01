import re
import excalidraw_palette as P

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

def test_palette_entries_are_valid_hex_fill_stroke():
    assert P.PALETTE, "PALETTE must not be empty"
    for hue, pair in P.PALETTE.items():
        assert set(pair) == {"fill", "stroke"}, hue
        assert HEX.match(pair["fill"]) and HEX.match(pair["stroke"]), hue

def test_semantic_roles_resolve_to_existing_hues():
    for r, hue in P.SEMANTIC.items():
        assert hue in P.PALETTE, (r, hue)

def test_role_returns_a_fresh_fill_stroke_dict():
    d = P.role("danger")
    assert d == {"fill": "#ffc9c9", "stroke": "#e03131"}
    d["fill"] = "x"                       # must be a copy, not the PALETTE entry
    assert P.PALETTE[P.SEMANTIC["danger"]]["fill"] == "#ffc9c9"

def test_font_reexported_and_title_subtitle_use_valid_font_roles():
    assert P.FONT["hand"] == 1 and P.FONT["code"] == 3 and P.FONT["normal"] == 5
    assert P.TITLE["font"] in P.FONT and P.SUBTITLE["font"] in P.FONT
    assert isinstance(P.TITLE["font_size"], int) and isinstance(P.SUBTITLE["font_size"], int)
