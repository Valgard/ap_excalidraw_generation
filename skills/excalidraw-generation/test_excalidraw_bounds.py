# test_excalidraw_bounds.py — TDD tests for excalidraw_bounds.py
# Port of bounds.ts behaviour from excalidraw/excalidraw
import math
import pytest
import excalidraw_bounds as B


# ---------------------------------------------------------------------------
# get_bounds_from_points
# ---------------------------------------------------------------------------

def test_bounds_from_points_basic():
    pts = [[0, 0], [10, 5], [3, 8]]
    x1, y1, x2, y2 = B.get_bounds_from_points(pts)
    assert x1 == 0 and y1 == 0 and x2 == 10 and y2 == 8


def test_bounds_from_points_negative():
    pts = [[-3, -5], [7, 2], [0, -1]]
    x1, y1, x2, y2 = B.get_bounds_from_points(pts)
    assert x1 == -3 and y1 == -5 and x2 == 7 and y2 == 2


def test_bounds_from_points_single():
    pts = [[5, 7]]
    x1, y1, x2, y2 = B.get_bounds_from_points(pts)
    assert x1 == x2 == 5 and y1 == y2 == 7


# ---------------------------------------------------------------------------
# point_rotate_rads
# ---------------------------------------------------------------------------

def test_point_rotate_rads_90():
    # Rotate (1, 0) around (0, 0) by π/2 → should be ≈ (0, 1)
    rx, ry = B.point_rotate_rads((1, 0), (0, 0), math.pi / 2)
    assert abs(rx) < 1e-10 and abs(ry - 1) < 1e-10


def test_point_rotate_rads_180():
    rx, ry = B.point_rotate_rads((3, 0), (0, 0), math.pi)
    assert abs(rx - (-3)) < 1e-10 and abs(ry) < 1e-10


def test_point_rotate_rads_around_non_origin():
    # Rotate (2, 1) around (1, 1) by π/2 → should be ≈ (1, 2)
    rx, ry = B.point_rotate_rads((2, 1), (1, 1), math.pi / 2)
    assert abs(rx - 1) < 1e-10 and abs(ry - 2) < 1e-10


# ---------------------------------------------------------------------------
# get_element_absolute_coords — plain (non-rotated) shapes
# ---------------------------------------------------------------------------

def test_absolute_coords_rectangle():
    el = {"type": "rectangle", "x": 10, "y": 20, "width": 100, "height": 40,
          "angle": 0}
    x1, y1, x2, y2, cx, cy = B.get_element_absolute_coords(el)
    assert x1 == 10 and y1 == 20 and x2 == 110 and y2 == 60
    assert cx == 60 and cy == 40


def test_absolute_coords_ellipse():
    el = {"type": "ellipse", "x": 0, "y": 0, "width": 80, "height": 60,
          "angle": 0}
    x1, y1, x2, y2, cx, cy = B.get_element_absolute_coords(el)
    assert x1 == 0 and y1 == 0 and x2 == 80 and y2 == 60
    assert cx == 40 and cy == 30


def test_absolute_coords_freedraw():
    el = {"type": "freedraw", "x": 5, "y": 10,
          "points": [[0, 0], [3, 4], [1, 2]],
          "angle": 0}
    x1, y1, x2, y2, cx, cy = B.get_element_absolute_coords(el)
    # points are local coords offset by x,y
    assert x1 == 5 and y1 == 10 and x2 == 8 and y2 == 14


# ---------------------------------------------------------------------------
# get_element_absolute_coords — linear elements (arrow/line with curve ops)
# ---------------------------------------------------------------------------

def _base_arrow(points, roundness=None):
    return {
        "type": "arrow",
        "x": 0,
        "y": 0,
        "width": 100,
        "height": 0,
        "angle": 0,
        "points": points,
        "strokeColor": "#000000",
        "backgroundColor": "transparent",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "seed": 42,
        "roundness": roundness,
        "endArrowhead": None,
    }


def test_absolute_coords_linear_straight():
    """A straight horizontal arrow: bbox should be approximately [0,y1, 100,y2]."""
    el = _base_arrow([[0, 0], [100, 0]])
    x1, y1, x2, y2, cx, cy = B.get_element_absolute_coords(el)
    assert x1 <= 0 and x2 >= 100
    # straight: y bounds near 0
    assert abs(y1) < 5 and abs(y2) < 5


def test_upward_curved_arrow_bbox_from_curve_not_points():
    """Arrow whose middle point is above the endpoints — curve bulge captured."""
    el = {
        "type": "arrow",
        "x": 0,
        "y": 100,
        "width": 100,
        "height": 0,
        "roundness": {"type": 2},
        "points": [[0, 0], [50, -40], [100, 0]],
        "strokeColor": "#000",
        "backgroundColor": "transparent",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "seed": 1,
        "endArrowhead": None,
    }
    x1, y1, x2, y2, cx, cy = B.get_element_absolute_coords(el)
    # top of bbox should be well above element.y + 0 = 100, i.e. y1 <= 60
    assert y1 <= 60, f"Expected y1 <= 60, got {y1}"


# ---------------------------------------------------------------------------
# get_element_bounds — with rotation applied
# ---------------------------------------------------------------------------

def test_rotated_rect_expands_bbox():
    """100x40 rect rotated ~90° should have width≈40 height≈100 (within 2px tolerance)."""
    el = {
        "type": "rectangle",
        "x": 0,
        "y": 0,
        "width": 100,
        "height": 40,
        "angle": math.pi / 2,
        "strokeColor": "#000",
        "backgroundColor": "transparent",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "seed": 1,
    }
    x1, y1, x2, y2 = B.get_element_bounds(el)
    w = x2 - x1
    h = y2 - y1
    assert abs(w - 40) <= 2, f"Expected width≈40 got {w}"
    assert abs(h - 100) <= 2, f"Expected height≈100 got {h}"


def test_rotated_ellipse_closed_form():
    """80x40 ellipse at 45°: half-extents via hypot formula."""
    el = {
        "type": "ellipse",
        "x": 0,
        "y": 0,
        "width": 80,
        "height": 40,
        "angle": math.pi / 4,
        "strokeColor": "#000",
        "backgroundColor": "transparent",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "seed": 1,
    }
    x1, y1, x2, y2 = B.get_element_bounds(el)
    cx, cy = 40, 20
    # closed form: a=40, b=20, angle=π/4
    a, b = 40, 20
    cos45 = math.cos(math.pi / 4)
    sin45 = math.sin(math.pi / 4)
    expected_hw = math.hypot(a * cos45, b * sin45)
    expected_hh = math.hypot(b * cos45, a * sin45)
    assert abs(x1 - (cx - expected_hw)) < 1e-6
    assert abs(y1 - (cy - expected_hh)) < 1e-6
    assert abs(x2 - (cx + expected_hw)) < 1e-6
    assert abs(y2 - (cy + expected_hh)) < 1e-6


def test_rotated_circle_aabb_is_rotation_invariant():
    """A circle (width==height==80) must have the same AABB at any angle.

    A circle's AABB is rotation-invariant: width and height stay 80 regardless
    of angle. This independently validates the ellipse closed-form path without
    re-deriving the same hypot formula used in the implementation.
    """
    el_base = {
        "type": "ellipse",
        "x": 0,
        "y": 0,
        "width": 80,
        "height": 80,
        "strokeColor": "#000",
        "backgroundColor": "transparent",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "seed": 1,
    }
    eps = 1e-9
    for angle in (0.0, 0.7, math.pi / 4, math.pi / 2, math.pi):
        el = {**el_base, "angle": angle}
        x1, y1, x2, y2 = B.get_element_bounds(el)
        w = x2 - x1
        h = y2 - y1
        assert abs(w - 80) < eps, f"Circle width={w} != 80 at angle={angle}"
        assert abs(h - 80) < eps, f"Circle height={h} != 80 at angle={angle}"


def test_unrotated_rect_bounds_unchanged():
    """A rect with angle=0 should have bounds equal to its position+dimensions."""
    el = {
        "type": "rectangle",
        "x": 10,
        "y": 20,
        "width": 50,
        "height": 30,
        "angle": 0,
        "strokeColor": "#000",
        "backgroundColor": "transparent",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "seed": 1,
    }
    x1, y1, x2, y2 = B.get_element_bounds(el)
    assert x1 == 10 and y1 == 20 and x2 == 60 and y2 == 50


# ---------------------------------------------------------------------------
# get_common_bounds
# ---------------------------------------------------------------------------

def test_common_bounds_two_rects():
    els = [
        {"type": "rectangle", "x": 0, "y": 0, "width": 50, "height": 30, "angle": 0,
         "strokeColor": "#000", "backgroundColor": "transparent",
         "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "seed": 1},
        {"type": "rectangle", "x": 60, "y": -10, "width": 20, "height": 20, "angle": 0,
         "strokeColor": "#000", "backgroundColor": "transparent",
         "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "seed": 2},
    ]
    x1, y1, x2, y2 = B.get_common_bounds(els)
    assert x1 == 0 and y1 == -10 and x2 == 80 and y2 == 30


def test_common_bounds_empty():
    assert B.get_common_bounds([]) == (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# curve_ops_bbox — direct test of the bezier op walker
# ---------------------------------------------------------------------------

def test_curve_ops_bbox_straight_line():
    """A straight line from (0,0) to (10,0) as a bcurveTo op."""
    ops = [
        ('move', 0, 0),
        ('bcurveTo', 3, 0, 7, 0, 10, 0),
    ]
    x1, y1, x2, y2 = B.curve_ops_bbox(ops)
    assert x1 == pytest.approx(0, abs=0.1) and x2 == pytest.approx(10, abs=0.1)
    assert y1 == pytest.approx(0, abs=0.1) and y2 == pytest.approx(0, abs=0.1)


def test_curve_ops_bbox_upward_arch():
    """A bezier arching above y=0: control points at y=-10."""
    ops = [
        ('move', 0, 0),
        ('bcurveTo', 5, -10, 15, -10, 20, 0),
    ]
    x1, y1, x2, y2 = B.curve_ops_bbox(ops)
    # The arch goes above y=0 (negative y direction), so y1 < 0
    assert y1 < -3, f"Expected arch above 0, got y1={y1}"
    assert x1 <= 0 and x2 >= 20
