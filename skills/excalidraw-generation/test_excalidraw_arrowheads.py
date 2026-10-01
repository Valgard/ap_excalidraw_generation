# test_excalidraw_arrowheads.py — TDD acceptance tests for P4.
# Tests: size/angle tables, get_arrowhead_points for a synthetic straight arrow,
#        and arrowhead_line_options stripping dash + capping roughness.
import math
import re
import pytest
import excalidraw_svg
from excalidraw_arrowheads import (
    get_arrowhead_size,
    get_arrowhead_angle,
    get_arrowhead_points,
    arrowhead_line_options,
)


def test_dashed_arrow_dashes_shaft_not_arrowheads():
    """A dashed arrow with arrowheads: only the shaft carries stroke-dasharray;
    the arrowhead barb paths render SOLID. Dashing the short barbs makes them
    render as broken/faint fragments instead of bold solid chevrons."""
    el = {
        "type": "arrow", "id": "a1", "x": 50, "y": 50, "width": 200, "height": 0,
        "angle": 0, "strokeColor": "#000000", "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "dashed", "roughness": 1,
        "opacity": 100, "groupIds": [], "seed": 12345, "version": 1, "versionNonce": 1,
        "isDeleted": False, "boundElements": None, "points": [[0, 0], [200, 0]],
        "startArrowhead": "arrow", "endArrowhead": "arrow",
        "startBinding": None, "endBinding": None, "lastCommittedPoint": None,
    }
    paths = re.findall(r"<path[^>]*>", excalidraw_svg._render_element(el))
    dashed = [p for p in paths if "stroke-dasharray" in p]
    assert len(paths) == 5, f"expected shaft + 4 barbs, got {len(paths)}"
    assert len(dashed) == 1, f"only the shaft should be dashed, got {len(dashed)}"


# ---------------------------------------------------------------------------
# Size table (bounds.ts L714-732)
# ---------------------------------------------------------------------------

def test_size_arrow():
    assert get_arrowhead_size("arrow") == 25

def test_size_diamond():
    assert get_arrowhead_size("diamond") == 12
    assert get_arrowhead_size("diamond_outline") == 12

def test_size_crowfoot_variants():
    assert get_arrowhead_size("cardinality_many") == 15
    assert get_arrowhead_size("cardinality_one_or_many") == 15
    assert get_arrowhead_size("cardinality_zero_or_many") == 15

def test_size_cardinality_marker_variants():
    assert get_arrowhead_size("cardinality_one") == 20
    assert get_arrowhead_size("cardinality_exactly_one") == 20
    assert get_arrowhead_size("cardinality_zero_or_one") == 20

def test_size_default():
    assert get_arrowhead_size("bar") == 15
    assert get_arrowhead_size("unknown_type") == 15


# ---------------------------------------------------------------------------
# Angle table (bounds.ts L734-744)
# ---------------------------------------------------------------------------

def test_angle_bar():
    assert get_arrowhead_angle("bar") == pytest.approx(90.0)

def test_angle_arrow():
    assert get_arrowhead_angle("arrow") == pytest.approx(20.0)

def test_angle_default():
    assert get_arrowhead_angle("diamond") == pytest.approx(25.0)
    assert get_arrowhead_angle("unknown") == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# get_arrowhead_points — straight horizontal arrow, position="end"
# bounds.ts L746-909
#
# Synthetic opset for a straight line 0→200 on x-axis:
#   ops = [('move', 0.0, 0.0), ('bcurveTo', 66.0, 0.0, 133.0, 0.0, 200.0, 0.0)]
#
# Expected values (closed-form):
#   tip   = (200.0, 0.0)               # p3
#   B(0.3) sample via reversed bezier  = (139.727, 0)   → nx=1, ny=0
#   minSize = min(25, 200*0.5) = 25
#   xs = 200 - 1*25 = 175, ys = 0
#   barb1 = rotate (175,0) about (200,0) by -20° → (176.507684, 8.550504)
#   barb2 = rotate (175,0) about (200,0) by +20° → (176.507684, -8.550504)
# ---------------------------------------------------------------------------

EPS = 1e-4

def _make_straight_opset():
    """Minimal synthetic opset for a straight 200px horizontal arrow."""
    return {
        "ops": [
            ("move", 0.0, 0.0),
            ("bcurveTo", 66.0, 0.0, 133.0, 0.0, 200.0, 0.0),
        ]
    }

def _make_arrow_el():
    return {
        "type": "arrow",
        "x": 0, "y": 0,
        "width": 200, "height": 0,
        "points": [[0, 0], [200, 0]],
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "seed": 1,
    }


def test_arrowhead_points_end_tip():
    el = _make_arrow_el()
    ops = _make_straight_opset()
    result = get_arrowhead_points(el, ops, "end", "arrow")
    assert result is not None
    tx, ty = result[0], result[1]
    assert abs(tx - 200.0) < EPS
    assert abs(ty - 0.0) < EPS


def test_arrowhead_points_end_barbs():
    el = _make_arrow_el()
    ops = _make_straight_opset()
    result = get_arrowhead_points(el, ops, "end", "arrow")
    assert result is not None and len(result) == 6
    tx, ty, x3, y3, x4, y4 = result
    # barb1 rotated -20°
    assert abs(x3 - 176.507684) < EPS, f"x3={x3}"
    assert abs(y3 - 8.550504) < EPS, f"y3={y3}"
    # barb2 rotated +20°
    assert abs(x4 - 176.507684) < EPS, f"x4={x4}"
    assert abs(y4 - (-8.550504)) < EPS, f"y4={y4}"


def test_arrowhead_points_null_arrowhead():
    el = _make_arrow_el()
    ops = _make_straight_opset()
    assert get_arrowhead_points(el, ops, "end", None) is None


def test_arrowhead_points_empty_opset():
    el = _make_arrow_el()
    assert get_arrowhead_points(el, {"ops": []}, "end", "arrow") is None


def test_arrowhead_points_start_tip():
    """For position='start', tip = p0 (the move point)."""
    el = _make_arrow_el()
    ops = _make_straight_opset()
    result = get_arrowhead_points(el, ops, "start", "arrow")
    assert result is not None
    tx, ty = result[0], result[1]
    # For start: tip = p0 = (0, 0); barbs point back toward x=200
    assert abs(tx - 0.0) < EPS
    assert abs(ty - 0.0) < EPS


# ---------------------------------------------------------------------------
# arrowhead_line_options (shape.ts L326-343)
# ---------------------------------------------------------------------------

def _base_options(roughness=1.5, stroke_style="solid"):
    opts = {
        "roughness": roughness,
        "strokeLineDash": [8, 10],
        "strokeWidth": 2,
        "stroke": "#000",
    }
    return opts


def test_line_options_solid_removes_dash():
    el = {**_make_arrow_el(), "strokeStyle": "solid", "strokeWidth": 2}
    base = _base_options(roughness=1.5, stroke_style="solid")
    result = arrowhead_line_options(el, base)
    assert "strokeLineDash" not in result


def test_line_options_dashed_removes_dash():
    el = {**_make_arrow_el(), "strokeStyle": "dashed", "strokeWidth": 2}
    base = _base_options(roughness=1.5)
    result = arrowhead_line_options(el, base)
    assert "strokeLineDash" not in result


def test_line_options_dotted_reduces_gap():
    el = {**_make_arrow_el(), "strokeStyle": "dotted", "strokeWidth": 2}
    base = _base_options(roughness=1.5)
    result = arrowhead_line_options(el, base)
    # dotted: should have a dash but with reduced gap
    assert "strokeLineDash" in result
    assert result["strokeLineDash"][1] < 10  # reduced from original 10


def test_line_options_caps_roughness_at_1():
    el = {**_make_arrow_el(), "strokeStyle": "solid", "strokeWidth": 2}
    base = _base_options(roughness=1.5)
    result = arrowhead_line_options(el, base)
    assert result["roughness"] == pytest.approx(1.0)


def test_line_options_low_roughness_unchanged():
    el = {**_make_arrow_el(), "strokeStyle": "solid", "strokeWidth": 2}
    base = _base_options(roughness=0.5)
    result = arrowhead_line_options(el, base)
    assert result["roughness"] == pytest.approx(0.5)


def test_line_options_does_not_mutate_input():
    el = {**_make_arrow_el(), "strokeStyle": "solid", "strokeWidth": 2}
    base = _base_options(roughness=2.0)
    original_roughness = base["roughness"]
    arrowhead_line_options(el, base)
    assert base["roughness"] == original_roughness  # original not mutated
    assert "strokeLineDash" in base                 # original dash not removed


# ---------------------------------------------------------------------------
# TDD RED/GREEN: dashed + roundness:2 arrowhead geometry
# Task 5: arrowhead barbs must each reset the randomizer so barb2 does not
# consume RNG state left by barb1 (both must start from the same seed).
# ---------------------------------------------------------------------------

import json
import pathlib
import sys as _sys

_sys.path.insert(0, str(pathlib.Path(__file__).parent / "tools"))
import excalidraw_svg
import svg_compare


def test_dashed_arrow_arrowhead_matches_reference():
    # memgpt-tiers-de has dashed arrows with roundness:2; its arrowhead paths must match.
    inp = "tests/inputs/integration/memgpt-tiers-de.excalidraw"
    ref = pathlib.Path("tests/oracle/integration/memgpt-tiers-de.svg").read_text()
    ours = excalidraw_svg.to_svg(json.loads(pathlib.Path(inp).read_text()))
    d = svg_compare.diff(ours, ref)
    assert d["path_count_ok"], d["first_divergence"]
    assert d["first_divergence"] is None, d["first_divergence"]


def test_atkinson_dashed_curved_arrow_matches_reference():
    inp = "tests/inputs/integration/atkinson-shiffrin-de.excalidraw"
    ref = pathlib.Path("tests/oracle/integration/atkinson-shiffrin-de.svg").read_text()
    ours = excalidraw_svg.to_svg(json.loads(pathlib.Path(inp).read_text()))
    assert svg_compare.diff(ours, ref)["first_divergence"] is None
