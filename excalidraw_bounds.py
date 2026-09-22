# excalidraw_bounds.py — faithful Python port of bounds.ts element/scene bounds.
# Source: excalidraw/excalidraw packages/element/src/bounds.ts
# Stdlib-only. Produces axis-aligned bounding boxes (AABBs) with rotation support.
#
# Op tuple format (from roughjs.py): ('move',x,y) | ('lineTo',x,y) | ('bcurveTo',x1,y1,x2,y2,x3,y3)
# where for bcurveTo: P1=(x1,y1) ctrl1, P2=(x2,y2) ctrl2, P3=(x3,y3) endpoint;
# current position is P0 (the implicit start from a preceding move/bcurveTo).

import math
from excalidraw_shape import generate_element_shape


# ---------------------------------------------------------------------------
# get_bounds_from_points (from getBoundsFromPoints ~L680)
# ---------------------------------------------------------------------------

def get_bounds_from_points(points):
    """Min/max over a list of [x, y] or (x, y) points.

    Returns (min_x, min_y, max_x, max_y).
    """
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for p in points:
        x, y = p[0], p[1]
        if x < min_x: min_x = x
        if y < min_y: min_y = y
        if x > max_x: max_x = x
        if y > max_y: max_y = y
    return (min_x, min_y, max_x, max_y)


# ---------------------------------------------------------------------------
# point_rotate_rads (from pointRotateRads in @excalidraw/math)
# ---------------------------------------------------------------------------

def point_rotate_rads(point, center, angle):
    """Rotate `point` around `center` by `angle` radians.

    Returns (rx, ry).
    """
    x, y = point[0], point[1]
    cx, cy = center[0], center[1]
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    dx, dy = x - cx, y - cy
    return (
        cx + dx * cos_a - dy * sin_a,
        cy + dx * sin_a + dy * cos_a,
    )


# ---------------------------------------------------------------------------
# Cubic bezier helpers (from getCubicBezierCurveBound ~L599, solveQuadratic ~L554)
# ---------------------------------------------------------------------------

def _bezier_value_at_t(t, p0, p1, p2, p3):
    """Evaluate cubic bezier (scalar) at parameter t."""
    u = 1 - t
    return u**3 * p0 + 3 * u**2 * t * p1 + 3 * u * t**2 * p2 + t**3 * p3


def _solve_quadratic(p0, p1, p2, p3):
    """Find t ∈ [0,1] where the cubic bezier derivative is zero.

    Returns a list of (possibly None) values at critical t.
    Matches solveQuadratic in bounds.ts ~L554.
    """
    i = p1 - p0
    j = p2 - p1
    k = p3 - p2
    a = 3 * i - 6 * j + 3 * k
    b = 6 * j - 6 * i
    c = 3 * i
    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return []
    results = []
    if a == 0:
        if b == 0:
            return []
        t_vals = [-c / b]
    else:
        sqrt_d = math.sqrt(discriminant)
        t_vals = [(-b + sqrt_d) / (2 * a), (-b - sqrt_d) / (2 * a)]
    for t in t_vals:
        if 0 <= t <= 1:
            results.append(_bezier_value_at_t(t, p0, p1, p2, p3))
    return results


def _cubic_bezier_curve_bound(p0, p1, p2, p3):
    """Tight AABB for one cubic bezier segment (analytical, from getCubicBezierCurveBound ~L599).

    All args are (x, y) pairs. Returns (min_x, min_y, max_x, max_y).
    """
    # Start with endpoints
    min_x = min(p0[0], p3[0]); max_x = max(p0[0], p3[0])
    min_y = min(p0[1], p3[1]); max_y = max(p0[1], p3[1])
    # Extend by analytic extrema
    for v in _solve_quadratic(p0[0], p1[0], p2[0], p3[0]):
        if v < min_x: min_x = v
        if v > max_x: max_x = v
    for v in _solve_quadratic(p0[1], p1[1], p2[1], p3[1]):
        if v < min_y: min_y = v
        if v > max_y: max_y = v
    return (min_x, min_y, max_x, max_y)


# ---------------------------------------------------------------------------
# curve_ops_bbox (from getMinMaxXYFromCurvePathOps ~L627)
# ---------------------------------------------------------------------------

def curve_ops_bbox(ops, transform_xy=None):
    """Walk roughjs op tuples and return the tight AABB.

    ops: list of ('move',x,y) | ('lineTo',x,y) | ('bcurveTo',x1,y1,x2,y2,x3,y3)
    transform_xy: optional callable (x, y) -> (x, y) applied to every point.

    Returns (min_x, min_y, max_x, max_y).
    Matches getMinMaxXYFromCurvePathOps ~L627 in bounds.ts.
    """
    min_x = max_x = min_y = max_y = None  # sentinel — initialised on first point

    def _expand(x, y):
        nonlocal min_x, max_x, min_y, max_y
        if transform_xy:
            x, y = transform_xy(x, y)
        if min_x is None or x < min_x: min_x = x
        if max_x is None or x > max_x: max_x = x
        if min_y is None or y < min_y: min_y = y
        if max_y is None or y > max_y: max_y = y

    cur_x = cur_y = 0.0
    for op in ops:
        kind = op[0]
        if kind == 'move':
            cur_x, cur_y = op[1], op[2]
            # move does not draw, but anchors the current point
        elif kind == 'lineTo':
            lx, ly = op[1], op[2]
            _expand(cur_x, cur_y)
            _expand(lx, ly)
            cur_x, cur_y = lx, ly
        elif kind == 'bcurveTo':
            # op = ('bcurveTo', cp1x, cp1y, cp2x, cp2y, ex, ey)
            p0 = (cur_x, cur_y)
            p1 = (op[1], op[2])
            p2 = (op[3], op[4])
            p3 = (op[5], op[6])
            bx1, by1, bx2, by2 = _cubic_bezier_curve_bound(p0, p1, p2, p3)
            _expand(bx1, by1)
            _expand(bx2, by2)
            cur_x, cur_y = p3

    if min_x is None:
        return (0, 0, 0, 0)
    return (min_x, min_y, max_x, max_y)


# ---------------------------------------------------------------------------
# get_element_absolute_coords (from getElementAbsoluteCoords ~L247)
# ---------------------------------------------------------------------------

def get_element_absolute_coords(element):
    """Return (x1, y1, x2, y2, cx, cy) — non-rotated tight bounds in scene coords.

    For linear elements the bounds are computed from the rough curve ops so that
    bezier bulge is captured (matches getElementAbsoluteCoords + LinearElementEditor
    behaviour in bounds.ts).
    """
    t = element["type"]
    ex, ey = element["x"], element["y"]

    if t == "freedraw":
        # getBoundsFromPoints over local points, offset to scene coords
        pts = element.get("points") or [[0, 0]]
        lx1, ly1, lx2, ly2 = get_bounds_from_points(pts)
        x1 = lx1 + ex; y1 = ly1 + ey
        x2 = lx2 + ex; y2 = ly2 + ey
        return (x1, y1, x2, y2, (x1 + x2) / 2, (y1 + y2) / 2)

    if t in ("line", "arrow"):
        pts = element.get("points") or [[0, 0]]
        if len(pts) < 2:
            # Degenerate: single point
            x1 = ex + pts[0][0]; y1 = ey + pts[0][1]
            return (x1, y1, x1, y1, x1, y1)

        # Generate the rough drawable and walk its curve ops for a tight bbox.
        # This mirrors generateLinearElementShape + getMinMaxXYFromCurvePathOps
        # (see getLinearElementRotatedBounds ~L934, but here without rotation).
        shapes = generate_element_shape(element)
        # First opset is always the stroke outline
        if shapes:
            ops = shapes[0].get("ops", [])
            # transform: local (element-relative) → scene coords
            def to_scene(x, y): return (ex + x, ey + y)
            x1, y1, x2, y2 = curve_ops_bbox(ops, transform_xy=to_scene)
        else:
            # Fallback to point bbox
            x1, y1, x2, y2 = get_bounds_from_points(
                [[ex + p[0], ey + p[1]] for p in pts]
            )
        return (x1, y1, x2, y2, (x1 + x2) / 2, (y1 + y2) / 2)

    # All other types (rectangle, diamond, ellipse, text, image, frame, …)
    x1 = ex; y1 = ey
    x2 = ex + element["width"]; y2 = ey + element["height"]
    return (x1, y1, x2, y2, (x1 + x2) / 2, (y1 + y2) / 2)


# ---------------------------------------------------------------------------
# get_element_bounds (from ElementBounds.calculateBounds ~L148-240)
# ---------------------------------------------------------------------------

def get_element_bounds(element):
    """Compute axis-aligned rotated bounding box for `element`.

    Applies element["angle"] (radians) around the element centre.
    Returns (x1, y1, x2, y2).

    Matches ElementBounds.calculateBounds in bounds.ts:
    - Ellipse: closed-form half-extents (hypot, ~L203-210).
    - FreeDrawElement: rotate individual points.
    - Linear elements: rotate the curve-ops bbox corners.
    - Other shapes (rectangle, diamond, …): rotate 4 corners of unrotated bbox.
    """
    t = element["type"]
    angle = element.get("angle", 0)
    x1, y1, x2, y2, cx, cy = get_element_absolute_coords(element)

    if angle == 0:
        return (x1, y1, x2, y2)

    if t == "freedraw":
        # Rotate each local point around (cx - ex, cy - ey) then shift
        ex, ey = element["x"], element["y"]
        lcx = cx - ex; lcy = cy - ey
        pts = element.get("points") or [[0, 0]]
        rotated = [point_rotate_rads((p[0], p[1]), (lcx, lcy), angle) for p in pts]
        min_x, min_y, max_x, max_y = get_bounds_from_points(rotated)
        return (min_x + ex, min_y + ey, max_x + ex, max_y + ey)

    if t == "ellipse":
        # Closed-form half-extents for rotated ellipse (bounds.ts ~L203-210)
        # a = semi-major (x), b = semi-minor (y)
        a = (x2 - x1) / 2
        b = (y2 - y1) / 2
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        hw = math.hypot(a * cos_a, b * sin_a)
        hh = math.hypot(b * cos_a, a * sin_a)
        return (cx - hw, cy - hh, cx + hw, cy + hh)

    # General case (rectangle, diamond, linear, text, image, frame, …):
    # rotate all 4 corners of the unrotated bbox around (cx, cy).
    # Diamond is NOT special-cased: Excalidraw's bounds.ts calculateBounds
    # rotates the 4 enclosing-box corners for all non-ellipse/non-linear types.
    corners = [(x1, y1), (x1, y2), (x2, y2), (x2, y1)]
    rotated = [point_rotate_rads(c, (cx, cy), angle) for c in corners]
    rxs = [p[0] for p in rotated]; rys = [p[1] for p in rotated]
    return (min(rxs), min(rys), max(rxs), max(rys))


# ---------------------------------------------------------------------------
# get_common_bounds (from getCommonBounds ~L1005)
# ---------------------------------------------------------------------------

def get_common_bounds(elements):
    """Return the AABB covering all elements.

    Returns (min_x, min_y, max_x, max_y).
    """
    if not elements:
        return (0, 0, 0, 0)
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for el in elements:
        bx1, by1, bx2, by2 = get_element_bounds(el)
        if bx1 < min_x: min_x = bx1
        if by1 < min_y: min_y = by1
        if bx2 > max_x: max_x = bx2
        if by2 > max_y: max_y = by2
    return (min_x, min_y, max_x, max_y)
