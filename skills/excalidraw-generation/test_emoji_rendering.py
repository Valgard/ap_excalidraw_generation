# test_emoji_rendering.py — TDD tests for VS16 emoji rendering via Noto tspan
# ⚠️ = U+26A0 U+FE0F (text-default with VS16 selector) must render via Noto Color Emoji.
# Non-emoji lines must be byte-identical to the current single-<text> output.
import excalidraw_svg
import fonts


def _make_text_doc(text: str, font_family: int = 5) -> dict:
    """Minimal single-element text doc for SVG rendering tests."""
    return {
        "elements": [
            {
                "id": "t1",
                "type": "text",
                "x": 10,
                "y": 10,
                "width": 200,
                "height": 30,
                "angle": 0,
                "strokeColor": "#1e1e1e",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 1,
                "strokeStyle": "solid",
                "roughness": 1,
                "opacity": 100,
                "text": text,
                "fontSize": 20,
                "fontFamily": font_family,
                "textAlign": "left",
                "verticalAlign": "top",
                "lineHeight": 1.25,
                "isDeleted": False,
                "boundElements": [],
                "updated": 0,
                "link": None,
                "locked": False,
                "containerId": None,
                "originalText": text,
                "index": "a1",
                "version": 1,
                "versionNonce": 1,
                "seed": 1,
                "groupIds": [],
                "frameId": None,
            }
        ],
        "appState": {"viewBackgroundColor": "#ffffff"},
        "files": {},
    }


# ---------------------------------------------------------------------------
# Test 1: VS16 emoji variation selector is dropped from output
# ---------------------------------------------------------------------------


def test_vs16_emoji_fe0f_not_in_output():
    """U+FE0F variation selector must be stripped from SVG output."""
    text = "⚠️"
    doc = _make_text_doc(text)
    svg = excalidraw_svg.to_svg(doc)
    assert "️" not in svg, "VS16 selector must be dropped"
    assert "&#xFE0F;" not in svg and "&#65039;" not in svg, "VS16 selector entity must be dropped"


# ---------------------------------------------------------------------------
# Test 2: Non-emoji text produces NO tspan (byte-identical to current output)
# ---------------------------------------------------------------------------

def test_non_emoji_text_has_no_tspan():
    """A text element with no emoji must produce NO <tspan> elements.

    This is the CRITICAL byte-identity guarantee: non-emoji lines must be
    handled by the exact same single-<text> path as before the fix.
    """
    text = "Hello World"
    doc = _make_text_doc(text)
    svg = excalidraw_svg.to_svg(doc)

    assert "<tspan" not in svg, (
        f"Non-emoji text must not produce any <tspan> elements, got:\n{svg}"
    )


def test_non_emoji_text_single_text_element():
    """Non-emoji text must produce a single <text ...>content</text> per line."""
    text = "Hello World"
    doc = _make_text_doc(text)
    svg = excalidraw_svg.to_svg(doc)

    # Must have exactly one <text element
    assert svg.count("<text") == 1, (
        f"Expected 1 <text element for single-line non-emoji text, got {svg.count('<text')}"
    )
    # Content must be inline (no tspan wrappers)
    assert "Hello World" in svg, "Text content must appear directly in SVG"


def test_non_emoji_multiline_no_tspan():
    """Multi-line non-emoji text must still produce no <tspan> elements."""
    text = "Line one\nLine two"
    doc = _make_text_doc(text)
    svg = excalidraw_svg.to_svg(doc)

    assert "<tspan" not in svg, (
        "Multi-line non-emoji text must not produce any <tspan> elements"
    )
    assert svg.count("<text") == 2, (
        f"Expected 2 <text elements for 2-line non-emoji text"
    )


# ---------------------------------------------------------------------------
# Test 3: Apple Color Emoji renders COLORED via resvg (sbix colored pixels)
# ---------------------------------------------------------------------------

def test_apple_emoji_renders_colored_via_resvg():
    """(b) An Apple Color Emoji tspan must render COLORED pixels via resvg.

    We render a tiny SVG with a 🧠 emoji (U+1F9E0, in Apple's cmap), then check
    that the resulting PNG has at least one non-grey colored pixel, confirming
    Apple sbix rendering is active.
    """
    try:
        import resvg_py
        from PIL import Image
        import io
        import numpy as np
        import fonts as _fonts
    except ImportError as e:
        import pytest
        pytest.skip(f"resvg_py/PIL/numpy not installed: {e}")
    if not (_fonts._DIR / "AppleColorEmoji.ttf").exists():
        import pytest
        pytest.skip("AppleColorEmoji.ttf not extracted (proprietary, not in the repository; "
                    "macOS: uv run --with fonttools python tools/build_fonts.py --apple-emoji)")

    # Build a minimal SVG with the 🧠 emoji in an Apple tspan
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
        '<text x="4" y="48" font-size="48" font-family="Virgil, Segoe UI Emoji">'
        '<tspan font-family="&quot;Apple Color Emoji&quot;">🧠</tspan>'
        '</text></svg>'
    )
    png_bytes = resvg_py.svg_to_bytes(
        svg_string=svg,
        zoom=1.0,
        font_files=_fonts.font_file_paths(),
        skip_system_fonts=True,
    )
    img = Image.open(io.BytesIO(bytes(png_bytes))).convert("RGBA")
    arr = np.array(img)

    # Check for colored (non-grey) pixels: a colored pixel has R != G or G != B
    # with alpha > 0
    alpha = arr[:, :, 3]
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    visible = alpha > 64
    colored = visible & (np.abs(r.astype(int) - g.astype(int)) > 10)
    colored_count = int(colored.sum())

    assert colored_count > 0, (
        f"Expected colored pixels from Apple Color Emoji sbix rendering, "
        f"got 0 colored pixels (total visible: {int(visible.sum())}). "
        "Apple emoji may not be rendering as colored."
    )
