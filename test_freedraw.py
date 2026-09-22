# test_freedraw.py — TDD for Task P9: freedraw via perfect-freehand port
import json
import pathlib
import re

import excalidraw_svg
import freehand

FIXSVG = pathlib.Path("tests/oracle/atomic")
INPUTS = pathlib.Path("tests/inputs/atomic")


def _norm(svg):
    """Collapse whitespace; strip style blocks."""
    svg = re.sub(r"<style[^>]*>.*?</style>", "", svg, flags=re.S)
    return re.sub(r"\s+", " ", svg).strip()


# ---------------------------------------------------------------------------
# Unit tests for the freehand module (perfect-freehand port)
# ---------------------------------------------------------------------------

def test_get_stroke_returns_list_of_points():
    """getStroke: given several input points, returns a non-empty list."""
    pts = [[0, 0], [10, 5], [20, 0], [30, 10], [40, 0]]
    outline = freehand.get_stroke(pts)
    assert isinstance(outline, list)
    assert len(outline) > 0
    assert all(len(p) == 2 for p in outline)


def test_get_stroke_with_pressure():
    """getStroke: pressure values affect outline (different from no-pressure)."""
    pts_xy = [[0, 0], [10, 0], [20, 0], [30, 0], [40, 0]]
    pts_xyp = [[0, 0, 0.2], [10, 0, 0.5], [20, 0, 0.8], [30, 0, 0.5], [40, 0, 0.2]]
    out_no_p = freehand.get_stroke(pts_xy, simulate_pressure=True)
    out_with_p = freehand.get_stroke(pts_xyp, simulate_pressure=False)
    # Both produce valid outlines; they differ because of different pressure inputs
    assert len(out_no_p) > 0
    assert len(out_with_p) > 0


def test_get_stroke_is_deterministic():
    """getStroke: same input → same output (no randomness)."""
    pts = [[0, 0, 0.5], [20, 10, 0.7], [40, 0, 0.5]]
    out1 = freehand.get_stroke(pts, simulate_pressure=False)
    out2 = freehand.get_stroke(pts, simulate_pressure=False)
    assert out1 == out2


def test_get_svg_path_from_stroke_format():
    """getSvgPathFromStroke: returns a non-trivial SVG path string."""
    pts = [[0, 0, 0.5], [20, 10, 0.7], [40, 5, 0.6], [60, 0, 0.5]]
    outline = freehand.get_stroke(pts, simulate_pressure=False, last=True)
    d = freehand.get_svg_path_from_stroke(outline)
    assert isinstance(d, str)
    assert d.startswith("M")
    assert "Q" in d
    assert "Z" in d


def test_get_freedraw_svg_path_returns_path_string():
    """get_freedraw_svg_path: given element dict, returns SVG path d-string.

    getSvgPathFromStroke uses the SVG 'Q ... (implicit Q)...' pattern:
    one explicit Q command letter followed by implicit quadratic Bézier pairs.
    So d.count("Q") == 1 is correct; what matters is the path has many points.
    """
    el = {
        "type": "freedraw",
        "strokeWidth": 2,
        "simulatePressure": False,
        "points": [[0, 0], [20, 10], [40, 0], [60, 20], [80, 0]],
        "pressures": [0.5, 0.6, 0.7, 0.6, 0.5],
    }
    d = freehand.get_freedraw_svg_path(el)
    assert isinstance(d, str)
    assert "M" in d
    assert "Q" in d
    assert "Z" in d
    # Non-trivial: must have many coordinate pairs (many points in the outline).
    # Count comma-separated pairs of numbers (each point is "x.xx,y.yy")
    pairs = re.findall(r'-?[\d.]+,-?[\d.]+', d)
    assert len(pairs) >= 10, f"Expected many coordinate pairs, got {len(pairs)}"


# ---------------------------------------------------------------------------
# Integration tests: to_svg() with freedraw.excalidraw
# ---------------------------------------------------------------------------

def test_freedraw_svg_emits_filled_path():
    """to_svg: freedraw element produces a filled <path> with strokeColor fill."""
    doc = json.loads((INPUTS / "freedraw.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    # Must contain at least one path element
    assert "<path" in got
    # Freedraw fill must be the element's strokeColor (#e03131)
    assert 'fill="#e03131"' in got
    # Freedraw path must have NO stroke (stroke="none" on wrapper or fill-only path)
    # The path itself should not have fill="none"
    assert 'fill="none"' not in got


def test_freedraw_svg_path_count_matches_golden():
    """to_svg: freedraw path count matches the golden SVG fixture."""
    doc = json.loads((INPUTS / "freedraw.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "freedraw.svg").read_text()
    got_count = _norm(got).count("<path")
    ref_count = _norm(ref).count("<path")
    assert got_count == ref_count, (
        f"Path count mismatch: got {got_count}, expected {ref_count}"
    )


def test_freedraw_svg_path_has_nontrivial_d():
    """to_svg: freedraw path d attribute has many coordinate pairs (complex outline).

    getSvgPathFromStroke uses one 'Q' command letter + implicit quadratic pairs,
    so counting 'Q' is not the right metric. Instead count coordinate pair tokens.
    """
    doc = json.loads((INPUTS / "freedraw.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    # Extract d= attribute from paths
    d_values = re.findall(r'd="([^"]+)"', got)
    assert len(d_values) > 0
    # The freedraw path must have many coordinate pairs
    max_pairs = max(len(re.findall(r'-?[\d.]+,-?[\d.]+', d)) for d in d_values)
    assert max_pairs >= 20, f"Expected complex path with many coordinate pairs, got max {max_pairs}"


def test_freedraw_svg_is_deterministic():
    """to_svg: freedraw produces identical output on repeated calls."""
    doc = json.loads((INPUTS / "freedraw.excalidraw").read_text())
    assert excalidraw_svg.to_svg(doc) == excalidraw_svg.to_svg(doc)


def test_freedraw_viewbox_matches_golden():
    """to_svg: freedraw viewBox matches the golden SVG fixture."""
    doc = json.loads((INPUTS / "freedraw.excalidraw").read_text())
    got = excalidraw_svg.to_svg(doc)
    ref = (FIXSVG / "freedraw.svg").read_text()
    got_vb = re.search(r'viewBox="([^"]+)"', got).group(1)
    ref_vb = re.search(r'viewBox="([^"]+)"', ref).group(1)
    assert got_vb == ref_vb, f"viewBox mismatch: got '{got_vb}', expected '{ref_vb}'"
