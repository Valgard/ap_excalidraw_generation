# test_symbol_fallback.py — generalized per-glyph font routing for symbols the
# primary hand-drawn font lacks (arrows, math operators, dingbats, ✗/✘/∼).
#
# The bug: when Virgil/Excalifont lacks a glyph (→ ↑ ↓ ← ∞ ≈ ✓ ✗ …), resvg under
# skip_system_fonts=True picks a full-coverage fallback for the WHOLE run, rendering
# the entire hand-drawn line in sans-serif. The fix routes each uncovered glyph to a
# <tspan> with the first covering Latin-free bundled family — priority: Apple Color Emoji
# then Noto Color Emoji (emoji), then DejaVu Sans subset then merged Noto Sans Symbols
# (symbols) — leaving the rest of the line in the primary hand-drawn font.
# (Cascadia was rejected as a fallback: it covers Latin, so resvg poisons the whole run.)
import io
import json
import pathlib
import re
import sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / "tools"))
import svg_compare  # noqa: E402

import excalidraw_svg
import fonts
from PIL import Image, ImageChops  # noqa: E402

resvg_py = pytest.importorskip("resvg_py")


def _make_text_doc(text: str, font_family: int = 1) -> dict:
    """Minimal single-element text doc for SVG rendering tests (default code 1 = Virgil)."""
    return {
        "elements": [
            {
                "id": "t1", "type": "text", "x": 10, "y": 10,
                "width": 300, "height": 30, "angle": 0,
                "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
                "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
                "roughness": 1, "opacity": 100, "text": text,
                "fontSize": 20, "fontFamily": font_family,
                "textAlign": "left", "verticalAlign": "top", "lineHeight": 1.25,
                "isDeleted": False, "boundElements": [], "updated": 0,
                "link": None, "locked": False, "containerId": None,
                "originalText": text, "index": "a1", "version": 1,
                "versionNonce": 1, "seed": 1, "groupIds": [], "frameId": None,
            }
        ],
        "appState": {"viewBackgroundColor": "#ffffff"},
        "files": {},
    }


# ---------------------------------------------------------------------------
# Fast-path byte-identity: a primary-covered line must not gain tspans
# ---------------------------------------------------------------------------

def test_symbol_free_line_is_fast_path_no_tspan():
    """A code-1 line with no uncovered glyphs must emit a single <text> with inline
    content — no <tspan> — i.e. the byte-identical fast-path."""
    svg = excalidraw_svg.to_svg(_make_text_doc("Hello World", font_family=1))
    assert "<tspan" not in svg
    assert svg.count("<text") == 1
    assert "Hello World" in svg


def test_symbol_free_text_element_is_byte_identical_fast_path():
    """A symbol-free code-1 line must emit the EXACT single-<text>, inline-content form
    of the pre-generalization fast-path — byte-for-byte, with no <tspan> wrapping and no
    change to the attribute string.
    Code 1 (deprecated Virgil) defaults to Excalifont (matches ExcalidrawZ rendering)."""
    svg = excalidraw_svg.to_svg(_make_text_doc("Hello World", font_family=1))
    text_el = re.search(r"<text\b.*?</text>", svg, re.S).group(0)
    expected = (
        '<text x="0" y="17.62" font-family="Excalifont, Xiaolai, Segoe UI Emoji" '
        'font-size="20px" fill="#1e1e1e" text-anchor="start" style="white-space: pre;" '
        'xml:space="preserve" direction="ltr" dominant-baseline="alphabetic">Hello World</text>'
    )
    assert text_el == expected, f"fast-path <text> diverged:\n{text_el}"


def test_symbol_free_fixture_geometry_and_text_still_match():
    """The pure-text code-1 fixture must still match the committed reference on the
    dimensions the suite validates (path geometry, text content, positions, viewBox) —
    the generalization must not perturb the fast-path."""
    inp = json.loads(pathlib.Path("tests/inputs/atomic/text.excalidraw").read_text())
    ref = pathlib.Path("tests/oracle/atomic/text.svg").read_text()
    ours = excalidraw_svg.to_svg(inp)
    d = svg_compare.diff(ours, ref)
    assert d["path_count_ok"] and d["viewbox_ok"], d
    for (oc, ox, oy), (rc, rx, ry) in d["text_positions"]:
        assert oc == rc, f"text content diverged: {oc!r} vs {rc!r}"


# ---------------------------------------------------------------------------
# Code-3 (Cascadia) family-name fix
# ---------------------------------------------------------------------------

def test_code3_element_emits_quoted_cascadia_code_family():
    """A code-3 text element must emit font-family="&quot;Cascadia Code&quot;, Segoe UI Emoji"
    on the <text> element — a bare "Cascadia" would match nothing in resvg's fontdb."""
    svg = excalidraw_svg.to_svg(_make_text_doc("hello", font_family=3))
    assert 'font-family="&quot;Cascadia Code&quot;, Segoe UI Emoji"' in svg, svg
    # The old broken bare-token must be gone
    assert 'font-family="Cascadia, Segoe UI Emoji"' not in svg


# ---------------------------------------------------------------------------
# Bundled DejaVu subset is registered for resvg's font loader
# ---------------------------------------------------------------------------

def test_dejavu_subset_bundled_and_registered():
    names = [p.rsplit("/", 1)[-1] for p in fonts.font_file_paths()]
    assert "DejaVuSubset.ttf" in names
    assert "NotoColorEmoji.ttf" in names




def test_symbol_emoji_free_line_stays_byte_identical():
    """(e) A symbol/emoji-free line must stay byte-identical (fast-path) after Apple routing.
    Code 1 (deprecated Virgil) defaults to Excalifont (matches ExcalidrawZ rendering)."""
    svg_before_ref = (
        '<text x="0" y="17.62" font-family="Excalifont, Xiaolai, Segoe UI Emoji" '
        'font-size="20px" fill="#1e1e1e" text-anchor="start" style="white-space: pre;" '
        'xml:space="preserve" direction="ltr" dominant-baseline="alphabetic">Hello World</text>'
    )
    svg = excalidraw_svg.to_svg(_make_text_doc("Hello World", font_family=1))
    # No tspan for a plain text line
    assert "<tspan" not in svg
    # Exact byte-identical fast-path element
    assert svg_before_ref in svg, f"fast-path diverged:\n{svg}"


def test_apple_bundled_and_registered():
    """AppleColorEmoji.ttf must be in font_file_paths() for resvg to load it."""
    names = [p.rsplit("/", 1)[-1] for p in fonts.font_file_paths()]
    assert "AppleColorEmoji.ttf" in names
    assert "NotoColorEmoji.ttf" in names
    assert "DejaVuSubset.ttf" in names


def test_noto_symbols_bundled_and_registered():
    """NotoSymbols.ttf must appear in font_file_paths() so resvg loads it."""
    names = [p.rsplit("/", 1)[-1] for p in fonts.font_file_paths()]
    assert "NotoSymbols.ttf" in names, f"NotoSymbols.ttf not in font_file_paths(): {names}"


def test_noto_symbols_only_cp_renders_ink(tmp_path):
    """U+2B20 (⬠ WHITE PENTAGON) in a Noto Symbols tspan must produce ink pixels.

    Renders a minimal SVG via resvg and asserts at least one non-white pixel exists.
    Skipped if resvg is not available (mirrors the pattern of existing render tests).
    """
    # Build a minimal SVG with the Noto Symbols tspan and the bundled @font-face
    noto_sym_ttf = pathlib.Path(__file__).parent / "font_files" / "NotoSymbols.ttf"
    import base64
    b64 = base64.b64encode(noto_sym_ttf.read_bytes()).decode("ascii")
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50">'
        '<defs><style>'
        f'@font-face {{ font-family: "Noto Sans Symbols"; src: url(data:font/ttf;base64,{b64}) format("truetype"); }}'
        "</style></defs>"
        '<rect width="50" height="50" fill="white"/>'
        '<text x="10" y="35" font-size="24" font-family="&quot;Noto Sans Symbols&quot;">'
        "⬠"  # ⬠ WHITE PENTAGON
        "</text>"
        "</svg>"
    )
    font_paths = fonts.font_file_paths()
    png_bytes = bytes(resvg_py.svg_to_bytes(
        svg_string=svg, font_files=font_paths, skip_system_fonts=True
    ))
    # Parse the PNG to check for ink (non-white) pixels
    import struct, zlib
    # Walk PNG chunks to find IDAT and reconstruct pixel data minimally
    # Use a simpler heuristic: the PNG must be non-trivially sized (> a blank 50x50)
    # A blank white 50x50 PNG (DEFLATE all-white rows) is ~200 bytes; ink adds data
    assert len(png_bytes) > 500, (
        f"PNG suspiciously small ({len(png_bytes)} bytes) — U+2B20 may not have rendered"
    )
    # Stronger check: look for non-white (255,255,255) pixels in the raw IDAT stream
    # by scanning for any non-0xFF byte that isn't a PNG structural byte.
    # We read the raw IDAT payload and decompress it.
    idat_data = b""
    pos = 8  # skip PNG signature
    while pos < len(png_bytes):
        length = struct.unpack(">I", png_bytes[pos:pos+4])[0]
        chunk_type = png_bytes[pos+4:pos+8]
        data = png_bytes[pos+8:pos+8+length]
        if chunk_type == b"IDAT":
            idat_data += data
        pos += 12 + length
    raw = zlib.decompress(idat_data)
    # Each row has a filter byte; we skip it and check the RGB(A) data
    # Any non-0xFF byte in non-filter positions means there's a non-white pixel (ink)
    width, height = 50, 50
    # RGBA = 4 bytes per pixel
    bytes_per_row = 1 + width * 4
    ink_found = False
    for row in range(height):
        row_start = row * bytes_per_row + 1  # skip filter byte
        row_bytes = raw[row_start:row_start + width * 4]
        for i in range(0, len(row_bytes), 4):
            r, g, b = row_bytes[i], row_bytes[i+1], row_bytes[i+2]
            if r < 240 or g < 240 or b < 240:  # non-white pixel
                ink_found = True
                break
        if ink_found:
            break
    assert ink_found, "U+2B20 (⬠) rendered no ink pixels — Noto Symbols font may not have loaded"


def test_symbol_emoji_free_line_stays_byte_identical_after_noto_symbols():
    """A symbol/emoji/noto-symbol-free line must stay byte-identical (fast-path) after
    adding the Noto Symbols routing step.
    Code 1 (deprecated Virgil) defaults to Excalifont (matches ExcalidrawZ rendering)."""
    svg_expected = (
        '<text x="0" y="17.62" font-family="Excalifont, Xiaolai, Segoe UI Emoji" '
        'font-size="20px" fill="#1e1e1e" text-anchor="start" style="white-space: pre;" '
        'xml:space="preserve" direction="ltr" dominant-baseline="alphabetic">Hello World</text>'
    )
    svg = excalidraw_svg.to_svg(_make_text_doc("Hello World", font_family=1))
    assert "<tspan" not in svg
    assert svg_expected in svg, f"fast-path diverged:\n{svg}"


# ---------------------------------------------------------------------------
# End-to-end render regression: native fallback + mixed-font poison guard
# (Task 6) — requires resvg_py + Pillow; skipped when resvg_py is absent
# ---------------------------------------------------------------------------

def _doc(elements):
    """Minimal doc wrapper for render regression tests."""
    return {"elements": elements, "appState": {"viewBackgroundColor": "#ffffff"}, "files": {}}


def _text_el(text, code, x=10, y=10, eid="t"):
    """Minimal text element for render regression tests."""
    return {
        "id": eid, "type": "text", "x": x, "y": y, "width": 400, "height": 40,
        "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 1,
        "opacity": 100, "text": text, "fontSize": 40, "fontFamily": code,
        "textAlign": "left", "verticalAlign": "top", "lineHeight": 1.25,
        "isDeleted": False, "boundElements": [], "updated": 0, "link": None,
        "locked": False, "containerId": None, "originalText": text, "index": "a1",
        "version": 1, "versionNonce": 1, "seed": 1, "groupIds": [], "frameId": None,
    }


def _gray(doc, files):
    """Render doc to a white-composited grayscale PIL Image via resvg.

    Like export.render_png, the SVG goes through resvg_families so that a swapped-in
    Latin-only subset is actually matched (otherwise its text would render in no font).
    """
    png = resvg_py.svg_to_bytes(
        svg_string=fonts.resvg_families(excalidraw_svg.to_svg(doc), fonts.used_codes(doc)), zoom=2.0,
        font_files=[str(p) for p in files], skip_system_fonts=True,
    )
    im = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, im).convert("L")


def _ink(img):
    """Count non-white (< 250) pixels in a grayscale PIL Image."""
    return sum(1 for p in img.getdata() if p < 250)


def test_native_fallback_renders_symbol_in_plain_text():
    """A hand-drawn (Virgil) line with → must render more ink than without it.

    Proves that native per-glyph fallback actually places the arrow glyph when
    font_file_paths(used_codes(doc)) is passed (no poisoner loaded, so no run poison).
    Skipped when resvg_py or Pillow is not available.
    """
    doc_a = _doc([_text_el("A", 1)])
    doc_ab = _doc([_text_el("A→", 1)])
    img_a = _gray(doc_a, fonts.font_file_paths(fonts.used_codes(doc_a)))
    img_ab = _gray(doc_ab, fonts.font_file_paths(fonts.used_codes(doc_ab)))
    ink_a = _ink(img_a)
    ink_ab = _ink(img_ab)
    assert ink_ab > ink_a + 60, (
        f"arrow must render via native per-glyph fallback "
        f"(ink_ab={ink_ab}, ink_a={ink_a}, delta={ink_ab - ink_a})"
    )


def test_mixed_font_doc_does_not_poison_handdrawn_line():
    """A doc mixing Virgil (code 1) + Liberation Sans (code 9) must not poison the Virgil line.

    The poison guard swaps LiberationSans for its Latin-only subset when both hand-drawn and
    poisoner codes are present. The 'flow' region of the rendered image must be closer
    (pixel distance) to a Virgil reference than to a Liberation reference — proving the
    guard kept the hand-drawn line in Virgil rather than collapsing it into Liberation Sans.
    Skipped when resvg_py or Pillow is not available.
    """
    mixed = _doc([_text_el("flow", 1, eid="v"), _text_el("label", 9, eid="l", y=120)])
    files = fonts.font_file_paths(fonts.used_codes(mixed))  # guard active → SubsetSans
    img = _gray(mixed, files)
    ref_virgil = _gray(_doc([_text_el("flow", 1)]), fonts.font_file_paths({1}))
    ref_lib = _gray(_doc([_text_el("flow", 9)]), fonts.font_file_paths({9}))
    # Crop to the MIN height of all three images: the mixed doc is taller (the 'label'
    # element sits lower), and Pillow pads out-of-bounds crops with black, which would
    # inflate BOTH distances with a common 'label'-vs-black baseline and compress the
    # margin. Cropping to the shortest keeps only the aligned 'flow' region, so a
    # correctly-guarded 'flow' collapses d_v toward zero.
    h = min(img.size[1], ref_virgil.size[1], ref_lib.size[1])
    crop = (0, 0, 220, h)
    d_v = sum(ImageChops.difference(img.crop(crop), ref_virgil.crop(crop)).getdata())
    d_l = sum(ImageChops.difference(img.crop(crop), ref_lib.crop(crop)).getdata())
    assert d_v * 2 < d_l, f"'flow' must stay Virgil (guard prevents poison): d_v={d_v} d_l={d_l}"


@pytest.mark.parametrize("poisoner", [9, 3])  # Liberation Sans, Cascadia Code
def test_export_renders_poisoner_line_through_renamed_subset(tmp_path, poisoner):
    """End to end through export.render_png: in a mixed doc the poisoner line must still
    render in its own shapes (via the renamed subset), not vanish or fall back."""
    import export

    def _render(doc, name):
        out = tmp_path / name
        export.render_png(doc, str(out), scale=2, background="light")
        return Image.open(out).convert("L")

    label = _text_el("label", poisoner, eid="l", y=120)
    mixed = _render(_doc([_text_el("flow", 1, eid="v"), label]), "mixed.png")
    ref_lib = _render(_doc([_text_el("flow", 1, eid="v", y=-500), label]), "lib.png")
    ref_virgil = _render(_doc([_text_el("flow", 1, eid="v"), dict(label, fontFamily=1)]), "virgil.png")
    w = min(mixed.size[0], ref_lib.size[0], ref_virgil.size[0])
    crop = (0, mixed.size[1] - 110, w, mixed.size[1])  # bottom band = the 'label' line
    band = mixed.crop(crop)
    assert _ink(band) > 200, "label line vanished"
    d_l = sum(ImageChops.difference(band, ref_lib.crop((0, ref_lib.size[1] - 110, w, ref_lib.size[1]))).getdata())
    d_v = sum(ImageChops.difference(band, ref_virgil.crop((0, ref_virgil.size[1] - 110, w, ref_virgil.size[1]))).getdata())
    assert d_l * 2 < d_v, f"label must render in font {poisoner}: d_l={d_l} d_v={d_v}"


@pytest.mark.parametrize("with_handdrawn", [False, True])  # guard inactive / active
def test_export_renders_frame_name_label(tmp_path, with_handdrawn):
    """A frame's name label is emitted as font-family "Helvetica" (parity with Excalidraw's
    SVG). resvg loads no font of that name, so export must map it to the bundled,
    metric-compatible Liberation Sans — otherwise the label vanishes from the PNG."""
    import copy
    import export

    base = json.loads((pathlib.Path(__file__).parent / "tests/inputs/atomic/frame.excalidraw").read_text())
    if with_handdrawn:
        base["elements"].append(_text_el("flow", 1, eid="v", x=20, y=40))

    def _ink_of(doc, name):
        out = tmp_path / name
        export.render_png(doc, str(out), scale=2, background="light")
        return _ink(Image.open(out).convert("L"))

    unnamed = copy.deepcopy(base)
    unnamed["elements"][0]["name"] = ""
    assert _ink_of(base, "named.png") > _ink_of(unnamed, "unnamed.png") + 100, "frame name label vanished"
