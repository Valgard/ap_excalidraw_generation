import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / "tools"))
import svg_compare

def test_normalize_strips_font_style_and_whitespace():
    svg = '<svg>\n  <style class="style-fonts">@font-face{}</style>  <path d="M0 0"/>\n</svg>'
    n = svg_compare.normalize(svg)
    assert "style-fonts" not in n
    assert "  " not in n  # collapsed
    assert '<path d="M0 0"/>' in n

