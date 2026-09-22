# test_excalidraw_svg.py — structural SVG parity tests for excalidraw_svg.to_svg()
import json
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent / "tools"))
import svg_compare  # noqa: E402 (must be after sys.path insert)

import excalidraw_svg
import export_options

FIXSVG = pathlib.Path("tests/oracle/atomic")
INPUTS = pathlib.Path("tests/inputs/atomic")


def test_arrow_label_midpoint_uses_middle_point_not_arc_length():
    """Bound-label anchor follows Excalidraw getBoundTextElementPosition: odd point
    count → middle CONTROL point; even → middle-segment midpoint. NOT 50% arc length
    (which sits ~16px off the control point for odd-count curved arrows, ghosting the label)."""
    # odd (3 pts, curved): middle control point points[1], not the arc-length midpoint
    assert excalidraw_svg._get_arrow_midpoint([[0, 0], [116.79, 227.73], [30.35, 430.69]]) == (116.79, 227.73)
    # odd (5 pts): points[2]
    assert excalidraw_svg._get_arrow_midpoint([[0, 0], [1, 1], [5, 9], [8, 3], [10, 0]]) == (5, 9)
    # even (2 pts): straight midpoint (unchanged)
    assert excalidraw_svg._get_arrow_midpoint([[0, 0], [100, 40]]) == (50.0, 20.0)
    # even (4 pts): midpoint of the middle segment points[1]..points[2]
    assert excalidraw_svg._get_arrow_midpoint([[0, 0], [10, 10], [30, 10], [40, 0]]) == (20.0, 10.0)


def _norm(svg):
    """Collapse whitespace; drop the <defs> font blob (fixture embeds differently)."""
    svg = re.sub(r"<style[^>]*>.*?</style>", "", svg, flags=re.S)
    return re.sub(r"\s+", " ", svg).strip()


def test_diamond_svg_matches_golden_structure():
    doc = json.loads((INPUTS / "diamond.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "diamond.svg").read_text()
    # viewBox parity
    assert re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', got).groups() == \
           re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', ref).groups()
    # path count parity
    assert _norm(got).count("<path") == _norm(ref).count("<path")


def test_text_svg_uses_alphabetic_baseline_and_per_line_y():
    doc = json.loads((INPUTS / "text.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert 'dominant-baseline="alphabetic"' in got
    assert got.count("<text") == 2   # two lines


def test_export_is_byte_deterministic():
    doc = json.loads((INPUTS / "diamond.excalidraw").read_text())
    assert excalidraw_svg.to_svg(doc) == excalidraw_svg.to_svg(doc)



def test_ellipse_dashed_has_stroke_dasharray():
    """Structural check: dashed ellipse produces stroke-dasharray attribute."""
    doc = json.loads((INPUTS / "ellipse-dashed.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert "stroke-dasharray" in got


def test_text_viewbox_matches_golden():
    doc = json.loads((INPUTS / "text.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "text.svg").read_text()
    assert re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', got).groups() == \
           re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', ref).groups()


def test_svg_has_background_rect():
    doc = json.loads((INPUTS / "diamond.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert '<rect x="0" y="0"' in got
    assert 'fill="#ffffff"' in got


def test_svg_omits_background_when_none():
    doc = json.loads((INPUTS / "diamond.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc, background=None)
    # No background rect — only the element group rect references remain
    assert got.count('<rect x="0" y="0"') == 0


def test_svg_contains_defs_style():
    doc = json.loads((INPUTS / "diamond.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert "<defs>" in got
    assert '<style class="style-fonts">' in got







def test_curved_arrow_viewbox_matches_golden():
    """Curved arrow: scene bounds must use curve-ops bbox (faithful bounds)."""
    doc = json.loads((INPUTS / "curved-arrow.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "curved-arrow.svg").read_text()
    assert re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', got).groups() == \
           re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', ref).groups()


# Task P5 — all arrowhead types + both ends
def test_double_head_svg_path_count_matches_golden():
    """Arrow with startArrowhead='arrow' and endArrowhead='arrow': path count == golden (5)."""
    doc = json.loads((INPUTS / "double-head.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "double-head.svg").read_text()
    got_n = _norm(got).count("<path")
    ref_n = _norm(ref).count("<path")
    assert got_n == ref_n, f"double-head: got {got_n} paths, golden has {ref_n}"


def test_triangle_head_svg_path_count_matches_golden():
    """Arrow with endArrowhead='triangle': path count == golden (3)."""
    doc = json.loads((INPUTS / "triangle-head.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "triangle-head.svg").read_text()
    got_n = _norm(got).count("<path")
    ref_n = _norm(ref).count("<path")
    assert got_n == ref_n, f"triangle-head: got {got_n} paths, golden has {ref_n}"



# Task P7 — bound-text container-aware positioning + no mask for filled containers
def test_bound_text_group_translate_derived_from_container_not_stored_xy():
    """Bound text with a wrong stored x/y must be repositioned to container-center.

    This verifies that to_svg() computes the bound-text translate from the
    CONTAINER geometry (getBoundTextElementPosition) rather than trusting the
    text element's raw stored x/y.  The stored x=999, y=999 are intentionally
    wrong; the expected translate is the container-centered value.
    """
    # Container: x=0, y=0, w=200, h=80 (center-y = (80-40)/2 = 20 => scene y=20)
    # Text:      center-align, middle-vertical, w=160, h=40 => x=(200-160)/2=20, y=20
    # With PAD=10 and min_x=0, min_y=0: off_x=off_y=10
    # Expected group translate: (20+10, 20+10) = (30, 30)
    container_id = "c1"
    doc = {
        "elements": [
            {
                "id": container_id, "type": "rectangle",
                "x": 0, "y": 0, "width": 200, "height": 80,
                "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
                "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
                "roughness": 1, "roundness": None, "opacity": 100,
                "groupIds": [], "frameId": None,
                "boundElements": [{"id": "t1", "type": "text"}],
                "updated": 0, "link": None, "locked": False,
                "seed": 1, "version": 1, "versionNonce": 1,
                "isDeleted": False, "index": "a1",
            },
            {
                "id": "t1", "type": "text",
                "x": 999, "y": 999,          # deliberately wrong stored position
                "width": 160, "height": 40,
                "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
                "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
                "roughness": 1, "roundness": None, "opacity": 100,
                "groupIds": [], "frameId": None, "boundElements": None,
                "updated": 0, "link": None, "locked": False,
                "seed": 2, "version": 1, "versionNonce": 2,
                "isDeleted": False, "index": "a2",
                "text": "Center", "originalText": "Center",
                "containerId": container_id,
                "fontFamily": 1, "fontSize": 20,
                "textAlign": "center", "verticalAlign": "middle",
                "lineHeight": 1.25, "autoResize": None,
            },
        ]
    }
    got = excalidraw_svg.to_svg(doc)
    transforms = re.findall(r'<g transform="([^"]+)"', got)
    # Find the text group translate (second group after the background rect group)
    text_transform = next(
        (t for t in transforms if "translate" in t and
         # The container translate will be at (0+10, 0+10) = (10, 10)
         # The text translate must NOT be at (999+10, 999+10)
         "999" not in t and "translate(10 10)" not in t),
        None,
    )
    assert text_transform is not None, (
        f"Expected a text group at container-centered position, got transforms: {transforms}"
    )
    # Extract the translate values
    m = re.match(r'translate\(([\d.]+) ([\d.]+)\)', text_transform)
    assert m, f"Unexpected transform format: {text_transform}"
    tx, ty = float(m.group(1)), float(m.group(2))
    # Expected: container.x + (container.width - text.width) / 2 + off_x = 0 + 20 + 10 = 30
    #           container.y + (container.height - text.height) / 2 + off_y = 0 + 20 + 10 = 30
    assert abs(tx - 30.0) < 0.01, f"Bound-text translate x: expected 30, got {tx}"
    assert abs(ty - 30.0) < 0.01, f"Bound-text translate y: expected 30, got {ty}"


def test_rotated_container_bound_text_matches_oracle():
    """Rotated container + bound text: rotation, mask and text count vs the oracle.

    Closes the gap left by the retired `rotated-box` bundle — no other atomic
    input pairs rotation with container binding.

    The scene carries the angle on BOTH elements, which is what Excalidraw's
    rotateSingleElement writes when a labelled shape is rotated (it mutates the
    bound text with the container's angle) and what label() now mirrors. The
    oracle confirms container and label turn together.
    """
    doc = json.loads((INPUTS / "boundtext-rotated.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "boundtext-rotated.svg").read_text()

    assert "<mask" not in ref, "Oracle unexpectedly contains a <mask> — update test"
    assert "<mask" not in got, "SVG emitted a <mask> for shape-bound text (should not)"
    assert got.count("<text") == ref.count("<text") == 1

    ours = [float(a) for a in re.findall(r"rotate\(([-\d.]+)", got)]
    theirs = [float(a) for a in re.findall(r"rotate\(([-\d.]+)", ref)]
    assert len(ours) == len(theirs), f"rotate() count differs: {ours} vs {theirs}"
    for o, t in zip(ours, theirs):
        assert abs(o - t) < 0.01, f"rotation differs: ours={o} oracle={t}"


def test_shape_bound_text_no_mask_emitted():
    """Shape-bound text (rect container): Excalidraw emits NO <mask> — confirm we match.

    Ported from the retired `rect-fill` bundle onto the atomic `boundtext-shape`
    input. Guards the shape path (_get_bound_text_position), which is distinct
    from the arrow-label path covered by the arrow-label mask tests.

    The rotated variant lives in test_rotated_container_bound_text_matches_oracle.
    """
    doc = json.loads((INPUTS / "boundtext-shape.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "boundtext-shape.svg").read_text()
    assert "<mask" not in ref, "Golden unexpectedly contains a <mask> — update test"
    assert "<mask" not in got, "SVG emitted a <mask> for shape-bound text (should not)"
    assert got.count("<text") == 1, f"Expected 1 text element, got {got.count('<text')}"




# Task P6 — text uses element.lineHeight
def test_multiline_lineheight_uses_element_lineheight():
    """Text with lineHeight=1.5 renders per-line y values using the element's lineHeight, not family default."""
    doc = json.loads((INPUTS / "multiline-lineheight.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "multiline-lineheight.svg").read_text()
    # Extract all <text y="..."> values from both
    got_y_values = [float(m) for m in re.findall(r'<text[^>]*y="([\d.]+)"', got)]
    ref_y_values = [float(m) for m in re.findall(r'<text[^>]*y="([\d.]+)"', ref)]
    assert len(got_y_values) == 3, f"Expected 3 lines, got {len(got_y_values)}"
    assert len(ref_y_values) == 3, f"Golden has {len(ref_y_values)} lines, expected 3"
    # Check parity: each line's y-value should match
    for i, (got_y, ref_y) in enumerate(zip(got_y_values, ref_y_values)):
        assert abs(got_y - ref_y) < 0.01, f"Line {i}: got y={got_y}, golden y={ref_y}"


# Task P8 — z-order (fractional index) sort
def test_elements_render_in_fractional_index_order():
    """Elements given out of index order must render in sorted index order.

    Creates two overlapping rectangles with indices out of order in the array,
    and verifies that the SVG <g> groups appear in sorted index order by checking
    the stroke colors (distinct markers per element).
    """
    # Array order: [elem_a2, elem_a1]
    # Index order: [elem_a1, elem_a2]
    doc = {
        "elements": [
            # First in array but second in index order (red stroke)
            {
                "id": "a2", "type": "rectangle",
                "x": 10, "y": 10, "width": 100, "height": 100,
                "angle": 0, "strokeColor": "#ff0000", "backgroundColor": "transparent",
                "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
                "roughness": 1, "roundness": None, "opacity": 100,
                "groupIds": [], "frameId": None,
                "boundElements": None,
                "updated": 0, "link": None, "locked": False,
                "seed": 1, "version": 1, "versionNonce": 1,
                "isDeleted": False, "index": "a2",
            },
            # Second in array but first in index order (blue stroke)
            {
                "id": "a1", "type": "rectangle",
                "x": 50, "y": 50, "width": 100, "height": 100,
                "angle": 0, "strokeColor": "#0000ff", "backgroundColor": "transparent",
                "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
                "roughness": 1, "roundness": None, "opacity": 100,
                "groupIds": [], "frameId": None,
                "boundElements": None,
                "updated": 0, "link": None, "locked": False,
                "seed": 2, "version": 1, "versionNonce": 2,
                "isDeleted": False, "index": "a1",
            },
        ]
    }
    got = excalidraw_svg.to_svg(doc)

    # Find positions of red and blue stroke colors in the SVG.
    # If elements render in index order, blue (#0000ff) should appear before red (#ff0000).
    red_pos = got.find('stroke="#ff0000"')
    blue_pos = got.find('stroke="#0000ff"')

    assert red_pos != -1, "Red stroke (#ff0000) not found in SVG"
    assert blue_pos != -1, "Blue stroke (#0000ff) not found in SVG"
    assert blue_pos < red_pos, (
        f"Elements not in index order: blue (a1) at {blue_pos}, "
        f"red (a2) at {red_pos} — expected blue before red"
    )


# Task P10 — image elements via embedded data URLs
def test_image_svg_has_image_with_data_href():
    """Image element: SVG must contain <image href='data:image/...'> matching golden structure."""
    doc = json.loads((INPUTS / "image.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "image.svg").read_text()
    # Must contain an <image tag
    assert "<image" in got, "Expected <image element in SVG output"
    # Must contain a data: URI
    assert "data:image/" in got, "Expected data:image/ href in SVG output"
    # Must use symbol+use pattern like the golden
    assert "<symbol" in got, "Expected <symbol definition in SVG output"
    assert "<use" in got, "Expected <use reference in SVG output"
    # viewBox parity
    assert re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', got).groups() == \
           re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', ref).groups()


def test_image_svg_symbol_references_file_id():
    """Image element: symbol id must incorporate the fileId from the document."""
    doc = json.loads((INPUTS / "image.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    file_id = "test-image-file-id"
    assert f'id="image-{file_id}"' in got, (
        f"Expected symbol id containing fileId '{file_id}'"
    )
    assert f'href="#image-{file_id}"' in got, (
        f"Expected <use href referencing symbol '#image-{file_id}'"
    )


def test_image_svg_matches_golden_structure():
    """Image element: full structural parity with golden (symbol+use, preserveAspectRatio, opacity)."""
    doc = json.loads((INPUTS / "image.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "image.svg").read_text()
    # Golden uses preserveAspectRatio="none" inside the <image>
    assert 'preserveAspectRatio="none"' in got, "Expected preserveAspectRatio='none'"
    # Golden uses width/height="100%" inside the symbol's <image>
    assert 'width="100%"' in got
    assert 'height="100%"' in got
    # Golden uses opacity attribute on <use>
    assert "opacity=" in got, "Expected opacity attribute on <use>"
    # Exact data URL must be present
    data_url = doc["files"]["test-image-file-id"]["dataURL"]
    assert data_url in got, "Expected full dataURL embedded in SVG"


# Task P11 — frame / embeddable / iframe rendering

def test_embeddable_svg_viewbox_matches_golden():
    """Embeddable: viewBox must match the golden."""
    doc = json.loads((INPUTS / "embeddable.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "embeddable.svg").read_text()
    assert re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', got).groups() == \
           re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', ref).groups()


def test_embeddable_svg_has_link_wrapper():
    """Embeddable with link: SVG must wrap the group in an <a href='...'> element."""
    doc = json.loads((INPUTS / "embeddable.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    link = doc["elements"][0]["link"]
    assert f'href="{link}"' in got, f"Expected href='{link}' in SVG"
    assert "<a " in got, "Expected <a> anchor tag in SVG"


def test_embeddable_svg_has_stroke_linecap_round():
    """Embeddable: outer <g> must have stroke-linecap='round' (staticSvgScene.ts port)."""
    doc = json.loads((INPUTS / "embeddable.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert 'stroke-linecap="round"' in got, "Expected stroke-linecap='round' on embeddable group"


def test_embeddable_svg_path_count_matches_golden():
    """Embeddable: path count (rough rect) must match golden."""
    doc = json.loads((INPUTS / "embeddable.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "embeddable.svg").read_text()
    got_n = _norm(got).count("<path")
    ref_n = _norm(ref).count("<path")
    assert got_n == ref_n, f"embeddable: got {got_n} paths, golden has {ref_n}"


def test_frame_svg_viewbox_matches_golden():
    """Frame: viewBox must match the golden (includes name-label height above frame)."""
    doc = json.loads((INPUTS / "frame.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "frame.svg").read_text()
    assert re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', got).groups() == \
           re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', ref).groups()


def test_frame_svg_has_outline_rect():
    """Frame: SVG must contain a <rect> with ZA stroke color (#bbb), no fill, rx/ry=8."""
    doc = json.loads((INPUTS / "frame.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert 'fill="none"' in got, "Expected fill='none' on frame rect"
    assert 'stroke="#bbb"' in got, "Expected stroke='#bbb' (ZA.strokeColor) on frame rect"
    assert 'rx="8"' in got, "Expected rx='8' (ZA.radius) on frame rect"
    assert 'ry="8"' in got, "Expected ry='8' (ZA.radius) on frame rect"
    assert 'stroke-width="2"' in got, "Expected stroke-width='2' (ZA.strokeWidth)"


def test_frame_svg_has_name_label():
    """Frame: SVG must contain a <text> element with the frame name."""
    doc = json.loads((INPUTS / "frame.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert "Frame 1" in got, "Expected frame name label in SVG"
    assert 'fill="#999999"' in got, "Expected ZA.nameColorLightTheme (#999999) for name label"
    assert 'font-size="14px"' in got, "Expected ZA.nameFontSize=14 for name label"
    assert "Helvetica" in got, "Expected Helvetica font family for name label"


def test_frame_svg_has_clip_path_in_defs():
    """Frame: SVG must contain a <clipPath> in <defs> with the frame element id."""
    doc = json.loads((INPUTS / "frame.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    frame_id = doc["elements"][0]["id"]
    assert f'<clipPath id="{frame_id}">' in got, \
        f"Expected <clipPath id='{frame_id}'> in SVG defs"


def test_frame_svg_is_byte_deterministic():
    """Frame: to_svg() must return the same bytes on repeated calls."""
    doc = json.loads((INPUTS / "frame.excalidraw").read_text())
    assert excalidraw_svg.to_svg(doc) == excalidraw_svg.to_svg(doc)


def test_embeddable_svg_is_byte_deterministic():
    """Embeddable: to_svg() must return the same bytes on repeated calls."""
    doc = json.loads((INPUTS / "embeddable.excalidraw").read_text())
    assert excalidraw_svg.to_svg(doc) == excalidraw_svg.to_svg(doc)


def test_frame_svg_name_label_y_uses_helvetica_metrics():
    """Frame name label y-value must use Helvetica font metrics (not Virgil/Excalifont)."""
    doc = json.loads((INPUTS / "frame.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    # Expected y = vertical_offset(Helvetica, 14, 14*1.25) = 12.5302734375
    assert 'y="12.5302734375"' in got, \
        "Expected Helvetica vertical offset y=12.5302734375 in frame name label"


# Task P12 — RTL text direction + anchor
def test_rtl_text_emits_direction_rtl_and_text_anchor_end():
    """RTL text (Arabic): direction="rtl" and text-anchor="end" must appear in SVG output."""
    doc = json.loads((INPUTS / "rtl-text.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert 'direction="rtl"' in got, "Expected direction='rtl' for Arabic RTL text"
    assert 'text-anchor="end"' in got, "Expected text-anchor='end' for RTL text"


def test_ltr_text_emits_direction_ltr():
    """LTR text: direction="ltr" must appear in SVG output (parity with golden)."""
    doc = json.loads((INPUTS / "text.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert 'direction="ltr"' in got, "Expected direction='ltr' for LTR text"


# Security — C1: attribute-injection / SVG-XSS prevention
# ---------------------------------------------------------------------------

def _make_embeddable_doc(link):
    """Return a minimal one-element embeddable doc with the given link."""
    return {
        "elements": [{
            "id": "sec-test-1",
            "type": "embeddable",
            "x": 0, "y": 0,
            "width": 100, "height": 100,
            "angle": 0,
            "strokeColor": "#000000",
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 1,
            "strokeStyle": "solid",
            "roughness": 1,
            "opacity": 100,
            "roundness": None,
            "seed": 1,
            "version": 1,
            "versionNonce": 1,
            "isDeleted": False,
            "index": "a0",
            "link": link,
            "locked": False,
            "boundElements": None,
            "updated": 0,
            "groupIds": [],
        }],
        "appState": {"viewBackgroundColor": "#ffffff"},
        "files": {},
    }


def test_embeddable_link_attribute_injection_is_escaped():
    """C1 security: a link containing a quote + event-handler payload must NOT break out
    of the href attribute (attribute-injection / SVG-XSS prevention).

    The raw value  http://x" onload="alert(1)  must appear escaped in the SVG so that
    the literal string '" onload="' does NOT appear verbatim in the output.
    """
    malicious_link = 'http://x" onload="alert(1)'
    doc = _make_embeddable_doc(malicious_link)
    got = excalidraw_svg.to_svg(doc)
    # The raw breakout sequence must NOT appear in the output.
    assert '" onload="' not in got, (
        "Attribute injection not escaped: raw quote+event-handler found in SVG output"
    )
    # The escaped form must be present (href value is sanitized and attr-escaped).
    assert "&quot;" in got or "http://x" not in got, (
        "Expected escaped attribute value in SVG output"
    )


def test_embeddable_link_javascript_scheme_becomes_about_blank():
    """C1 security: javascript: links must be replaced with about:blank (protocol whitelist)."""
    doc = _make_embeddable_doc("javascript:alert(1)")
    got = excalidraw_svg.to_svg(doc)
    assert "javascript:" not in got, "javascript: scheme must not appear in SVG output"
    assert 'href="about:blank"' in got, "Expected href='about:blank' for javascript: link"


def test_embeddable_link_data_scheme_becomes_about_blank():
    """C1 security: data: links (e.g. data:text/html,<script>) must become about:blank."""
    doc = _make_embeddable_doc("data:text/html,<script>alert(1)</script>")
    got = excalidraw_svg.to_svg(doc)
    assert "data:text/html" not in got, "data: scheme must not appear in SVG href"
    assert 'href="about:blank"' in got, "Expected href='about:blank' for data: link"


def test_embeddable_link_https_passes_through():
    """C1 security: https: links must pass through the whitelist unchanged (modulo escaping)."""
    doc = _make_embeddable_doc("https://example.com/path?q=1")
    got = excalidraw_svg.to_svg(doc)
    assert 'href="https://example.com/path?q=1"' in got, (
        "Expected safe https: link to appear in SVG href"
    )


def test_embeddable_link_mailto_passes_through():
    """C1 security: mailto: links must pass through the whitelist."""
    doc = _make_embeddable_doc("mailto:user@example.com")
    got = excalidraw_svg.to_svg(doc)
    assert 'href="mailto:user@example.com"' in got, (
        "Expected mailto: link to appear in SVG href"
    )


def test_rtl_text_golden_direction_attr_placement():
    """RTL text: direction='rtl' appears between style and dominant-baseline, matching golden attr order."""
    doc = json.loads((INPUTS / "rtl-text.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "rtl-text.svg").read_text()
    # Both must have the same attribute ordering: style + direction + dominant-baseline
    snippet_got = re.search(r'style="white-space: pre;"(?: xml:space="preserve")? direction="([^"]+)" dominant-baseline', got)
    snippet_ref = re.search(r'style="white-space: pre;"(?: xml:space="preserve")? direction="([^"]+)" dominant-baseline', ref)
    assert snippet_ref is not None, "Golden does not have expected attribute layout — update test"
    assert snippet_got is not None, "SVG output missing expected attribute layout"
    assert snippet_got.group(1) == "rtl", f"Expected direction='rtl', got '{snippet_got.group(1)}'"
    assert snippet_ref.group(1) == "rtl", "Golden direction must be 'rtl'"


# Task P13 — SVG scaffolding cosmetics for Excalidraw parity
def test_svg_scaffolding_has_source_comment():
    """to_svg() must emit the <!-- svg-source:excalidraw --> comment immediately after <svg ...>."""
    doc = json.loads((INPUTS / "diamond.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert "<!-- svg-source:excalidraw -->" in got, (
        "Expected '<!-- svg-source:excalidraw -->' comment in SVG output"
    )


def test_svg_scaffolding_has_metadata_element():
    """to_svg() must emit an empty <metadata></metadata> element inside <svg>."""
    doc = json.loads((INPUTS / "diamond.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert "<metadata></metadata>" in got, (
        "Expected '<metadata></metadata>' in SVG output"
    )


def test_svg_scaffolding_style_has_class_style_fonts():
    """to_svg() must emit <style class=\"style-fonts\"> matching real Excalidraw's exportToSvg."""
    doc = json.loads((INPUTS / "diamond.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert 'class="style-fonts"' in got, (
        "Expected class='style-fonts' on <style> element in SVG output"
    )


def test_svg_scaffolding_golden_wrapper_sequence():
    """Golden wrapper sequence: comment → metadata → defs(style) appear in correct order."""
    doc = json.loads((INPUTS / "diamond.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    pos_comment = got.find("<!-- svg-source:excalidraw -->")
    pos_metadata = got.find("<metadata></metadata>")
    pos_defs = got.find("<defs>")
    assert pos_comment != -1, "svg-source comment missing"
    assert pos_metadata != -1, "<metadata></metadata> missing"
    assert pos_defs != -1, "<defs> missing"
    assert pos_comment < pos_metadata, "comment must precede <metadata>"
    assert pos_metadata < pos_defs, "<metadata> must precede <defs>"


def test_ltr_text_golden_direction_attr_placement():
    """LTR text: direction='ltr' appears between style and dominant-baseline, matching golden attr order."""
    doc = json.loads((INPUTS / "text.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "text.svg").read_text()
    # Both must have the same attribute ordering
    snippet_got = re.search(r'style="white-space: pre;"(?: xml:space="preserve")? direction="([^"]+)" dominant-baseline', got)
    snippet_ref = re.search(r'style="white-space: pre;"(?: xml:space="preserve")? direction="([^"]+)" dominant-baseline', ref)
    assert snippet_ref is not None, "Golden does not have expected attribute layout — update test"
    assert snippet_got is not None, "SVG output missing expected attribute layout"
    assert snippet_got.group(1) == "ltr", f"Expected direction='ltr', got '{snippet_got.group(1)}'"
    assert snippet_ref.group(1) == "ltr", "Golden direction must be 'ltr'"


# Task P7 / fix-arrow-labels-v2 — arrow/line-bound labels must use PATH MIDPOINT, NOT stored x/y
def test_arrow_bound_label_uses_path_midpoint_not_stored_xy():
    """Arrow-bound text must be rendered at the PATH MIDPOINT (50% of cumulative segment
    length), NOT at the text element's stored x/y and NOT at the arrow's bbox center.

    Port of LinearElementEditor.getBoundTextElementPosition in Excalidraw source.
    The stored x/y for arrow labels may be stale; real Excalidraw always recomputes.

    Synthetic doc:
      - Arrow: x=0, y=0, points=[[0,0],[200,0]]  (horizontal, 200px long)
      - Path midpoint (local): (100, 0) → absolute: (100, 0)
      - Label: w=60, h=20 → top-left = (100-30, 0-10) = (70, -10)
      - Stored label x=90, y=-15 (intentionally different from midpoint result)
      - Arrow bbox center (wrong) = (100, 0) → label at (70, -10)  [same as midpoint here]
      - Midpoint label top-left = (70, -10)
      - off_x from scene bounds, off_y from scene bounds
      - The invariant: label translate x - arrow translate x = 70 - 0 = 70 (midpoint-derived)
        NOT label_stored_x - arrow.x = 90 (stored x)
    """
    arrow_id = "arr1"
    label_stored_x = 90.0   # intentionally different from midpoint result (70)
    label_stored_y = -15.0  # intentionally different from midpoint result (-10)
    label_w = 60.0
    label_h = 20.0
    doc = {
        "elements": [
            {
                "id": arrow_id, "type": "arrow",
                "x": 0, "y": 0, "width": 200, "height": 0,
                "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
                "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
                "roughness": 1, "roundness": {"type": 2}, "opacity": 100,
                "groupIds": [], "frameId": None,
                "boundElements": [{"id": "lbl1", "type": "text"}],
                "updated": 0, "link": None, "locked": False,
                "seed": 1, "version": 1, "versionNonce": 1,
                "isDeleted": False, "index": "a1",
                "startBinding": None, "endBinding": None,
                "lastCommittedPoint": None,
                "startArrowhead": None, "endArrowhead": "arrow",
                "points": [[0, 0], [200, 0]],
                "elbowed": False,
            },
            {
                "id": "lbl1", "type": "text",
                "x": label_stored_x, "y": label_stored_y,
                "width": label_w, "height": label_h,
                "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
                "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
                "roughness": 1, "roundness": None, "opacity": 100,
                "groupIds": [], "frameId": None, "boundElements": None,
                "updated": 0, "link": None, "locked": False,
                "seed": 2, "version": 1, "versionNonce": 2,
                "isDeleted": False, "index": "a2",
                "text": "Label", "originalText": "Label",
                "containerId": arrow_id,
                "fontFamily": 1, "fontSize": 16,
                "textAlign": "center", "verticalAlign": "middle",
                "lineHeight": 1.25, "autoResize": None,
            },
        ]
    }
    got = excalidraw_svg.to_svg(doc)
    transforms = re.findall(r'<g transform="([^"]+)"', got)

    # Extract all translate(tx ty) values
    translates = []
    for t in transforms:
        m = re.match(r'translate\(([-\d.]+) ([-\d.]+)\)', t)
        if m:
            translates.append((float(m.group(1)), float(m.group(2))))

    # Arrow at x=0, y=0 → its group translate = (off_x, off_y).
    # The arrow is rendered first so translates[0] is the arrow group.
    # Label midpoint-based position: top-left = (70, -10) in scene coords.
    # Label translate = (70 + off_x, -10 + off_y).
    # Label stored-based position: top-left = (90, -15) — we assert this is NOT used.
    #
    # Invariant: label_translate_x - arrow_translate_x should equal 70 (midpoint) not 90 (stored).
    assert len(translates) >= 2, f"Expected ≥2 translates, got: {translates}"
    arrow_tx, arrow_ty = translates[0]   # arrow rendered first
    off_x = arrow_tx   # arrow.x = 0, so off_x = arrow_tx
    off_y = arrow_ty   # arrow.y = 0, so off_y = arrow_ty

    # Find the label translate
    expected_midpoint_tx = 70.0 + off_x   # midpoint: (100-30)+off_x = 70+off_x
    expected_midpoint_ty = -10.0 + off_y  # midpoint: (0-10)+off_y = -10+off_y
    expected_stored_tx = label_stored_x + off_x   # stored x=90
    expected_stored_ty = label_stored_y + off_y   # stored y=-15

    label_tx, label_ty = None, None
    for tx, ty in translates[1:]:
        # Look for the label translate (not the arrow's)
        if abs(tx - expected_midpoint_tx) < 1.0 and abs(ty - expected_midpoint_ty) < 1.0:
            label_tx, label_ty = tx, ty
            break

    assert label_tx is not None, (
        f"Label not at midpoint position ({expected_midpoint_tx:.2f}, {expected_midpoint_ty:.2f}). "
        f"All translates: {translates}. "
        f"Stored position would be ({expected_stored_tx:.2f}, {expected_stored_ty:.2f}). "
        "Arrow-bound label must use path midpoint, not stored x/y."
    )
    # Confirm stored x/y was NOT used
    assert abs(label_tx - expected_stored_tx) > 0.5 or abs(label_ty - expected_stored_ty) > 0.5, (
        f"Label translate ({label_tx}, {label_ty}) matches stored position — midpoint fix not applied."
    )


# fix-arrow-labels-v2 — arrow-label golden fixture tests
def test_arrow_label_viewbox_matches_golden():
    """Arrow with bound label: viewBox must match golden (midpoint positioning + mask)."""
    doc = json.loads((INPUTS / "arrow-label.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "arrow-label.svg").read_text()
    assert re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', got).groups() == \
           re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', ref).groups()


def test_arrow_label_mask_emitted():
    """Arrow with bound label: a <mask> element must be present in SVG output.

    Real Excalidraw emits a mask to punch a gap in the arrow stroke behind the label.
    Mask id follows the pattern 'mask-{arrow_id}'.
    """
    doc = json.loads((INPUTS / "arrow-label.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "arrow-label.svg").read_text()
    assert "<mask" in ref, "Golden unexpectedly missing <mask> — update test"
    assert "<mask" in got, "SVG did not emit a <mask> for arrow with bound label"
    assert 'id="mask-arrow1"' in got, "Expected mask id 'mask-arrow1' in SVG"
    assert 'mask="url(#mask-arrow1)"' in got, "Expected mask reference on arrow group"


def test_arrow_label_midpoint_translate_matches_golden():
    """Arrow with bound label: label translate must match midpoint-based position.

    Arrow: x=50, y=100, points=[[0,0],[200,0]].
    Path midpoint (local): (100, 0) → absolute: (150, 100).
    Label: w=60, h=24 → scene top-left: (150-30, 100-12) = (120, 88).
    With off_x=-40, off_y=-78: label translate = (80, 10).
    Golden: translate(80 10).
    """
    doc = json.loads((INPUTS / "arrow-label.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "arrow-label.svg").read_text()
    # Extract label translate from golden
    ref_translates = re.findall(r'translate\(([-\d.]+) ([-\d.]+)\)', ref)
    got_translates = re.findall(r'translate\(([-\d.]+) ([-\d.]+)\)', got)
    # Golden label transform: translate(80 10) (last translate in the SVG)
    # Find the label translate in our output: should be near (80, 10)
    label_found = any(
        abs(float(tx) - 80.0) < 1.0 and abs(float(ty) - 10.0) < 1.0
        for tx, ty in got_translates
    )
    assert label_found, (
        f"Label translate not near (80, 10) — midpoint position mismatch. "
        f"Got translates: {got_translates}"
    )


def test_arrow_label_mask_black_rect_matches_label_position():
    """Arrow mask: the black rect (stroke gap) must align with the label position.

    The mask's black rect must be at the label's SVG-root coordinate position (80, 10)
    with the label's dimensions (w=60, h=24), matching the real Excalidraw golden.
    """
    doc = json.loads((INPUTS / "arrow-label.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    # The mask black rect should have x=80, y=10, w=60, h=24 (label in SVG root coords)
    # Allow small rounding tolerance
    m = re.search(
        r'<rect x="([-\d.]+)" y="([-\d.]+)" fill="#000" width="([\d.]+)" height="([\d.]+)"',
        got
    )
    assert m is not None, "Expected black fill rect in mask, not found"
    bx, by, bw, bh = float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4))
    assert abs(bx - 80.0) < 1.0, f"Mask black rect x={bx}, expected ≈80"
    assert abs(by - 10.0) < 1.0, f"Mask black rect y={by}, expected ≈10"
    assert abs(bw - 60.0) < 1.0, f"Mask black rect width={bw}, expected 60"
    assert abs(bh - 24.0) < 1.0, f"Mask black rect height={bh}, expected 24"



# fix-bounds-mask — Fix 1: arrow-label stale x/y feeds scene bounds correctly
def test_arrow_bound_label_stale_xy_does_not_inflate_viewbox():
    """Fix 1: Arrow-bound label with stale stored x/y must not inflate the viewBox.

    Synthetic doc: arrow from (0,0) to (200,0); label w=60 h=20 but stored at
    x=500 y=0 (far off-screen right).  The recomputed midpoint position is (70, -10).
    The correct scene bounds must be based on the midpoint position, not x=500.

    Without Fix 1 the viewBox width would be ~510 (dominated by stale stored x).
    With Fix 1 the viewBox width must be ≤ 220 (from arrow + midpoint-based label).
    """
    arrow_id = "bounds-test-arrow"
    doc = {
        "elements": [
            {
                "id": arrow_id, "type": "arrow",
                "x": 0, "y": 0, "width": 200, "height": 0,
                "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
                "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
                "roughness": 1, "roundness": {"type": 2}, "opacity": 100,
                "groupIds": [], "frameId": None,
                "boundElements": [{"id": "bounds-test-lbl", "type": "text"}],
                "updated": 0, "link": None, "locked": False,
                "seed": 1, "version": 1, "versionNonce": 1,
                "isDeleted": False, "index": "a1",
                "startBinding": None, "endBinding": None,
                "lastCommittedPoint": None,
                "startArrowhead": None, "endArrowhead": "arrow",
                "points": [[0, 0], [200, 0]],
                "elbowed": False,
            },
            {
                "id": "bounds-test-lbl", "type": "text",
                "x": 500, "y": 0,          # stale: far right, should NOT contribute to bounds
                "width": 60, "height": 20,
                "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
                "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
                "roughness": 1, "roundness": None, "opacity": 100,
                "groupIds": [], "frameId": None, "boundElements": None,
                "updated": 0, "link": None, "locked": False,
                "seed": 2, "version": 1, "versionNonce": 2,
                "isDeleted": False, "index": "a2",
                "text": "Mid", "originalText": "Mid",
                "containerId": arrow_id,
                "fontFamily": 1, "fontSize": 16,
                "textAlign": "center", "verticalAlign": "middle",
                "lineHeight": 1.25, "autoResize": None,
            },
        ]
    }
    got = excalidraw_svg.to_svg(doc)
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', got)
    assert m is not None, "SVG missing viewBox"
    vb_width = float(m.group(1))
    # Stale stored x=500 would inflate width to ~510+padding; midpoint x≈70 gives ~220+padding.
    # Assert the viewBox is NOT inflated by the stale position.
    assert vb_width <= 230, (
        f"viewBox width={vb_width} suggests stale stored x=500 was used for bounds "
        f"(should be ≤230 based on arrow length + midpoint-positioned label)"
    )


# fix-bounds-mask — Fix 2: unlabeled arrow emits empty <mask></mask>
def test_unlabeled_arrow_emits_empty_mask():
    """Fix 2: Arrow without a bound label must emit an empty <mask></mask> element.

    Real Excalidraw unconditionally emits a mask element after every arrow/line
    group regardless of whether it carries a bound label. The empty mask has no
    visual effect but must be present for structural parity.
    """
    doc = {
        "elements": [
            {
                "id": "bare-arrow", "type": "arrow",
                "x": 0, "y": 0, "width": 100, "height": 0,
                "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
                "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
                "roughness": 1, "roundness": {"type": 2}, "opacity": 100,
                "groupIds": [], "frameId": None,
                "boundElements": [],   # no bound text
                "updated": 0, "link": None, "locked": False,
                "seed": 1, "version": 1, "versionNonce": 1,
                "isDeleted": False, "index": "a1",
                "startBinding": None, "endBinding": None,
                "lastCommittedPoint": None,
                "startArrowhead": None, "endArrowhead": "arrow",
                "points": [[0, 0], [100, 0]],
                "elbowed": False,
            },
        ]
    }
    got = excalidraw_svg.to_svg(doc)
    # Must have exactly one <mask></mask> (the empty mask for the unlabeled arrow)
    assert "<mask></mask>" in got, (
        "Expected '<mask></mask>' for unlabeled arrow (Fix 2: structural parity)"
    )
    # Must NOT have a filled mask (no label → no id, no white/black rects)
    assert 'id="mask-bare-arrow"' not in got, (
        "Unlabeled arrow must not emit a filled mask — only an empty <mask></mask>"
    )
    assert 'mask="url(#mask-bare-arrow)"' not in got, (
        "Unlabeled arrow group must not reference a mask"
    )
    # The arrow group must still have stroke-linecap="round"
    assert 'stroke-linecap="round"' in got, (
        "Arrow group must carry stroke-linecap='round' even without a label"
    )


# Task 6 — free/container text position alignment (class B)
def test_free_text_positions_match_reference():
    """Text <text> x/y must be within 0.5px of the @excalidraw/utils reference.

    Covers:
    - atkinson-shiffrin-de: free text (KI-Parallelen:) + container-bound text with
      null stored lineHeight — lineHeight must be recovered from element.height /
      lineCount / fontSize (Excalidraw Ua() port), not from the font-metrics default.
    - user-segmentation-de: container-bound text with explicit lineHeight=1.25
      (regression guard: Task 2 emoji fix must not have broken these).
    """
    for stem in ("atkinson-shiffrin-de", "user-segmentation-de"):
        inp = f"tests/inputs/integration/{stem}.excalidraw"
        ref = pathlib.Path(f"tests/oracle/integration/{stem}.svg").read_text()
        ours = excalidraw_svg.to_svg(json.loads(pathlib.Path(inp).read_text()))
        for (oc, ox, oy), (rc, rx, ry) in svg_compare.diff(ours, ref)["text_positions"]:
            if oc == rc and ox is not None and rx is not None:
                assert abs(float(ox) - float(rx)) < 0.5, (
                    f"{stem} x {oc!r}: ours={ox} ref={rx}"
                )
                assert abs(float(oy) - float(ry)) < 0.5, (
                    f"{stem} y {oc!r}: ours={oy} ref={ry}"
                )


# hachure-fill bug fix — fillSketch opsets must use fill colour + fillWeight, not stroke colour/width
def test_hachure_fill_lines_use_fill_colour_and_fill_weight():
    """fillSketch opsets (hachure/cross-hatch) must be rendered with the FILL colour (backgroundColor)
    at fillWeight, NOT the stroke colour/width, and must not be dashed.

    rough.js renders hachure fill lines in the fill colour at fillWeight; applying the
    element strokeColor/strokeWidth to these opsets is a rendering bug.

    Rectangle: fillStyle='hachure', backgroundColor='#dee2e6', strokeColor='#495057',
               strokeWidth=2, fillWeight=1 (default).
    Expected SVG: a <path> with stroke='#dee2e6' and stroke-width='1' for the fillSketch opset.
    The shape OUTLINE path must still use stroke='#495057' with stroke-width='2'.
    """
    fill_colour = "#dee2e6"
    stroke_colour = "#495057"
    doc = {
        "elements": [
            {
                "id": "hachure-test-rect",
                "type": "rectangle",
                "x": 0, "y": 0, "width": 100, "height": 80,
                "angle": 0,
                "strokeColor": stroke_colour,
                "backgroundColor": fill_colour,
                "fillStyle": "hachure",
                "strokeWidth": 2,
                "strokeStyle": "solid",
                "roughness": 1,
                "roundness": None,
                "opacity": 100,
                "groupIds": [], "frameId": None,
                "boundElements": None,
                "updated": 0, "link": None, "locked": False,
                "seed": 12345,
                "version": 1, "versionNonce": 1,
                "isDeleted": False, "index": "a1",
            }
        ],
        "appState": {"viewBackgroundColor": "#ffffff"},
        "files": {},
    }
    got = excalidraw_svg.to_svg(doc)

    # Extract all <path ...> elements
    path_tags = re.findall(r'<path [^/]*/>', got)
    assert len(path_tags) >= 2, f"Expected ≥2 <path> elements (fillSketch + outline), got {len(path_tags)}"

    # Check that at least one path uses the fill colour (backgroundColor) for its stroke —
    # this is the fillSketch hachure fill line path.
    fill_colour_paths = [p for p in path_tags if f'stroke="{fill_colour}"' in p]
    assert len(fill_colour_paths) >= 1, (
        f"No <path> with stroke='{fill_colour}' (fill colour) found. "
        f"fillSketch hachure lines must use backgroundColor as stroke colour.\n"
        f"Paths found:\n" + "\n".join(path_tags)
    )

    # fillSketch hachure path must NOT use strokeWidth=2 (that is the outline width)
    for p in fill_colour_paths:
        assert 'stroke-width="2"' not in p, (
            f"fillSketch path uses strokeWidth=2 (outline width) — must use fillWeight instead.\n"
            f"Path: {p}"
        )
        # Must have stroke-width (fillWeight = 1 by default)
        assert 'stroke-width="1"' in p, (
            f"fillSketch path must have stroke-width='1' (fillWeight default).\nPath: {p}"
        )
        # Must NOT be dashed
        assert "stroke-dasharray" not in p, (
            f"fillSketch path must not have stroke-dasharray (no dash on fill lines).\nPath: {p}"
        )

    # Check that the outline path still uses strokeColor
    outline_paths = [p for p in path_tags if f'stroke="{stroke_colour}"' in p]
    assert len(outline_paths) >= 1, (
        f"No <path> with stroke='{stroke_colour}' (stroke colour) found. "
        f"The shape outline must still use strokeColor.\n"
        f"Paths found:\n" + "\n".join(path_tags)
    )
    # Outline path must use strokeWidth=2
    for p in outline_paths:
        assert 'stroke-width="2"' in p, (
            f"Outline path must have stroke-width='2' (strokeWidth).\nPath: {p}"
        )


# fix-element-opacity — element opacity applied as stroke/fill-opacity on root group
# ---------------------------------------------------------------------------
# Oracle: real @excalidraw/utils exportToSvg places stroke-opacity/fill-opacity on the
# ROOT group of every element when element.opacity / 100 != 1.
# Attribute order (discovered from minted golden fixtures):
#   - rect/ellipse/diamond: stroke-opacity fill-opacity stroke-linecap="round" transform
#   - text:                 stroke-opacity fill-opacity transform  (no stroke-linecap)
#   - arrow/line:           outer <g stroke-linecap="round"> unchanged;
#                           inner <g stroke-opacity fill-opacity transform>

def test_rect_opacity_attrs_on_root_group():
    """Rectangle with opacity=20: stroke-opacity='0.2' and fill-opacity='0.2' appear on
    the root element <g> alongside stroke-linecap='round'."""
    doc = json.loads((INPUTS / "opacity-rect.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    # The root element group must carry both opacity attrs and stroke-linecap
    assert 'stroke-opacity="0.2"' in got, "Expected stroke-opacity='0.2' for opacity=20 rect"
    assert 'fill-opacity="0.2"' in got, "Expected fill-opacity='0.2' for opacity=20 rect"
    # Oracle: stroke-linecap="round" is present on the same group as the opacity attrs
    m = re.search(
        r'<g stroke-opacity="0\.2" fill-opacity="0\.2" stroke-linecap="round" transform="',
        got,
    )
    assert m is not None, (
        "Expected '<g stroke-opacity=\"0.2\" fill-opacity=\"0.2\" stroke-linecap=\"round\" "
        "transform=\"...' for opacity=20 rect — oracle attr order not matched"
    )


def test_ellipse_opacity_attrs_on_root_group():
    """Ellipse with opacity=20: stroke/fill-opacity on root group with stroke-linecap."""
    doc = json.loads((INPUTS / "opacity-ellipse.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert 'stroke-opacity="0.2"' in got
    assert 'fill-opacity="0.2"' in got
    m = re.search(
        r'<g stroke-opacity="0\.2" fill-opacity="0\.2" stroke-linecap="round" transform="',
        got,
    )
    assert m is not None, (
        "Ellipse opacity=20: expected stroke-opacity/fill-opacity/stroke-linecap on root group"
    )


def test_diamond_opacity_attrs_on_root_group():
    """Diamond with opacity=20: stroke/fill-opacity on root group with stroke-linecap."""
    doc = json.loads((INPUTS / "opacity-diamond.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert 'stroke-opacity="0.2"' in got
    assert 'fill-opacity="0.2"' in got
    m = re.search(
        r'<g stroke-opacity="0\.2" fill-opacity="0\.2" stroke-linecap="round" transform="',
        got,
    )
    assert m is not None, (
        "Diamond opacity=20: expected stroke-opacity/fill-opacity/stroke-linecap on root group"
    )


def test_text_opacity_attrs_on_root_group_no_stroke_linecap():
    """Text with opacity=20: stroke/fill-opacity on root <g>, NO stroke-linecap='round'
    (oracle: text elements do not carry stroke-linecap on the element root group)."""
    doc = json.loads((INPUTS / "opacity-text.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert 'stroke-opacity="0.2"' in got
    assert 'fill-opacity="0.2"' in got
    # Must have opacity attrs directly on the transform group (no stroke-linecap)
    m = re.search(
        r'<g stroke-opacity="0\.2" fill-opacity="0\.2" transform="',
        got,
    )
    assert m is not None, (
        "Text opacity=20: expected stroke-opacity/fill-opacity directly before transform "
        "(no stroke-linecap for text)"
    )
    # The opacity group must NOT carry stroke-linecap
    assert 'stroke-opacity="0.2" fill-opacity="0.2" stroke-linecap' not in got, (
        "Text root group must NOT have stroke-linecap='round'"
    )


def test_arrow_opacity_attrs_on_inner_group():
    """Arrow with opacity=20: stroke/fill-opacity on the INNER <g transform=...> group,
    NOT on the outer <g stroke-linecap='round'> wrapper.

    Oracle: outer group retains stroke-linecap='round' unchanged;
            inner per-path groups carry stroke-opacity/fill-opacity."""
    doc = json.loads((INPUTS / "opacity-arrow.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    assert 'stroke-opacity="0.2"' in got, "Expected stroke-opacity='0.2' for opacity=20 arrow"
    assert 'fill-opacity="0.2"' in got, "Expected fill-opacity='0.2' for opacity=20 arrow"
    # Inner group: stroke-opacity comes before transform, NOT on the outer stroke-linecap group
    m = re.search(
        r'<g stroke-opacity="0\.2" fill-opacity="0\.2" transform="',
        got,
    )
    assert m is not None, (
        "Arrow opacity=20: inner group must have stroke-opacity/fill-opacity before transform"
    )
    # Outer group must be the plain stroke-linecap wrapper (no opacity attrs there)
    assert '<g stroke-linecap="round"><g stroke-opacity' in got or \
           '<g stroke-linecap="round">' in got, (
        "Arrow must have outer <g stroke-linecap='round'> wrapper"
    )
    # Outer stroke-linecap group must NOT carry opacity attrs
    assert '<g stroke-linecap="round" stroke-opacity' not in got and \
           '<g stroke-opacity' not in got.split('<g stroke-linecap="round">')[0], (
        "Opacity attrs must be on inner group, not the outer stroke-linecap wrapper"
    )



def test_opacity_rect_golden_viewbox_matches():
    """Opacity rect: viewBox must match golden (opacity does not affect layout)."""
    doc = json.loads((INPUTS / "opacity-rect.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "opacity-rect.svg").read_text()
    assert re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', got).groups() == \
           re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', ref).groups()


def test_opacity_text_golden_viewbox_matches():
    """Opacity text: viewBox must match golden."""
    doc = json.loads((INPUTS / "opacity-text.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "opacity-text.svg").read_text()
    assert re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', got).groups() == \
           re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', ref).groups()


def test_opacity_arrow_golden_viewbox_matches():
    """Opacity arrow: viewBox must match golden (approximately — float precision may differ)."""
    doc = json.loads((INPUTS / "opacity-arrow.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "opacity-arrow.svg").read_text()
    got_m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', got)
    ref_m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', ref)
    assert got_m is not None and ref_m is not None, "Missing viewBox in one of the SVGs"
    # Allow small float tolerance (rough.js geometry may differ slightly)
    assert abs(float(got_m.group(1)) - float(ref_m.group(1))) < 2.0, (
        f"Opacity arrow viewBox width mismatch: ours={got_m.group(1)}, oracle={ref_m.group(1)}"
    )
    assert abs(float(got_m.group(2)) - float(ref_m.group(2))) < 2.0, (
        f"Opacity arrow viewBox height mismatch: ours={got_m.group(2)}, oracle={ref_m.group(2)}"
    )


# scene_layout — single source of truth for the scene→pixel transform.
# The font-render detector (tools/font_diff.py) needs off_x/off_y/width/height/scale
# to place a text element's scene bbox onto the exported PNG. These MUST equal what
# to_svg() actually emits, or the detector measures the wrong pixels. The consistency
# test below runs over the whole input corpus (incl. the tricky arrow-label / frame
# paths) so any drift between scene_layout and to_svg fails immediately.

def test_scene_layout_width_height_match_to_svg_viewbox():
    for src in sorted(INPUTS.glob("*.excalidraw")):
        doc = json.loads(src.read_text())
        opts = export_options.resolve(doc)
        layout = excalidraw_svg.scene_layout(doc, opts)
        svg = excalidraw_svg.to_svg(doc, options=opts)
        m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        assert (layout.width, layout.height) == pytest.approx(
            (float(m.group(1)), float(m.group(2)))
        ), f"scene_layout drifted from to_svg viewBox on {src.name}"


def test_scene_layout_offsets_place_min_corner_at_padding():
    doc = json.loads((INPUTS / "arrow-label.excalidraw").read_text())
    opts = export_options.resolve(doc)
    layout = excalidraw_svg.scene_layout(doc, opts)
    # off maps the scene min-corner to (padding, padding).
    assert layout.off_x + layout.min_x == pytest.approx(opts.export_padding)
    assert layout.off_y + layout.min_y == pytest.approx(opts.export_padding)


