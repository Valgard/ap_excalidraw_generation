# test_native_fallback.py
import io
import pathlib
import pytest
import excalidraw_svg
import fonts

FONTS_DIR = pathlib.Path(__file__).parent / "font_files"

def _text_doc(text, code=1):
    return {"elements": [{
        "id": "t1", "type": "text", "x": 10, "y": 10, "width": 400, "height": 40,
        "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1,
        "opacity": 100, "text": text, "fontSize": 20, "fontFamily": code,
        "textAlign": "left", "verticalAlign": "top", "lineHeight": 1.25,
        "isDeleted": False, "boundElements": [], "updated": 0, "link": None,
        "locked": False, "containerId": None, "originalText": text, "index": "a1",
        "version": 1, "versionNonce": 1, "seed": 1, "groupIds": [], "frameId": None,
    }], "appState": {"viewBackgroundColor": "#ffffff"}, "files": {}}

def test_render_text_emits_no_tspans_for_symbol_line():
    svg = excalidraw_svg.to_svg(_text_doc("A→B ✓ 😀", code=1))
    assert "<tspan" not in svg, "native fallback path must emit a single <text> run"
    assert "<text" in svg

def test_pure_latin_line_has_no_tspan():
    svg = excalidraw_svg.to_svg(_text_doc("hello world", code=1))
    assert "<tspan" not in svg


def _render_gray(doc, font_files=None):
    resvg_py = pytest.importorskip("resvg_py")
    from PIL import Image
    import fonts as _f
    files = font_files if font_files is not None else [str(p) for p in _f.font_file_paths(_f.used_codes(doc))]
    png = resvg_py.svg_to_bytes(svg_string=excalidraw_svg.to_svg(doc), zoom=2.0,
                                font_files=files, skip_system_fonts=True)
    im = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, im).convert("L")


def _ink(img):
    return sum(1 for p in img.getdata() if p < 250)


def test_zwj_and_skintone_emoji_render():
    # BLOCKER gate: complex emoji must render as real clusters, not blank AND not tofu.
    # `_ink > threshold` alone can't tell a colored cluster from a notdef box (boxes have
    # outline ink too). So compare against a MISS baseline: the same string rendered with
    # ONLY the hand-drawn font loaded (no emoji/fallback fonts → the emoji is uncovered).
    virgil_only = [str(FONTS_DIR / "Virgil.ttf")]
    for label, s in [("zwj-family", "\U0001F468‍\U0001F469‍\U0001F467"),
                     ("skin-tone", "\U0001F44D\U0001F3FD")]:
        doc = _text_doc(s, code=1)
        real = _ink(_render_gray(doc))
        miss = _ink(_render_gray(doc, font_files=virgil_only))
        assert real > miss * 3 + 200, f"{label}: emoji not rendering (real={real} miss={miss})"


def test_to_svg_is_byte_deterministic():
    doc = _text_doc("A→B ✓ 😀 hello", code=1)
    assert excalidraw_svg.to_svg(doc) == excalidraw_svg.to_svg(doc)


def test_png_is_byte_deterministic():
    resvg_py = pytest.importorskip("resvg_py")
    import fonts as _f
    doc = _text_doc("A→B ✓ 😀 hello", code=1)
    svg = excalidraw_svg.to_svg(doc)
    files = [str(p) for p in _f.font_file_paths(_f.used_codes(doc))]
    a = bytes(resvg_py.svg_to_bytes(svg_string=svg, zoom=2.0, font_files=files, skip_system_fonts=True))
    b = bytes(resvg_py.svg_to_bytes(svg_string=svg, zoom=2.0, font_files=files, skip_system_fonts=True))
    assert a == b, "PNG bytes must be deterministic for a fixed file + pinned toolchain"
