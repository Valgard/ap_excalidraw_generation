# freehand.py — stdlib-only port of perfect-freehand (steveruizok/perfect-freehand)
# + Excalidraw's getFreeDrawSvgPath / getSvgPathFromStroke (packages/element/src/shape.ts)
#
# Sources:
#   perfect-freehand src/getStroke.ts, getStrokePoints.ts, getStrokeOutlinePoints.ts,
#                    vec.ts, constants.ts, getStrokeRadius.ts, simulatePressure.ts
#   Excalidraw packages/element/src/shape.ts (getFreeDrawSvgPath, getSvgPathFromStroke,
#                    getVariableWidthFreedrawOutline, VARIABLE_WIDTH_FREEDRAW constants)
#   Excalidraw packages/common/src/constants.ts (DEFAULT_STROKE_STREAMLINE = 0.5)
#
# All floating-point arithmetic is identical to the TypeScript original.
# No external dependencies — stdlib only.

import math
import re

# ---------------------------------------------------------------------------
# Constants (from constants.ts)
# ---------------------------------------------------------------------------

RATE_OF_PRESSURE_CHANGE = 0.275
FIXED_PI = math.pi + 0.0001
START_CAP_SEGMENTS = 13
END_CAP_SEGMENTS = 29
CORNER_CAP_SEGMENTS = 13
END_NOISE_THRESHOLD = 3
MIN_STREAMLINE_T = 0.15
STREAMLINE_T_RANGE = 0.85
MIN_RADIUS = 0.01
DEFAULT_FIRST_PRESSURE = 0.25
DEFAULT_PRESSURE = 0.5
UNIT_OFFSET = [1.0, 1.0]

# Excalidraw constants (from packages/common/src/constants.ts)
DEFAULT_STROKE_STREAMLINE = 0.5

# Excalidraw VARIABLE_WIDTH_FREEDRAW tuning (from packages/element/src/shape.ts)
_SIZE_FACTOR = 4.25
_THINNING = 0.6
_SMOOTHING = 0.5


# ---------------------------------------------------------------------------
# Vector math (from vec.ts)
# ---------------------------------------------------------------------------

def _neg(a):        return [-a[0], -a[1]]
def _add(a, b):     return [a[0]+b[0], a[1]+b[1]]
def _sub(a, b):     return [a[0]-b[0], a[1]-b[1]]
def _mul(a, n):     return [a[0]*n, a[1]*n]
def _div(a, n):     return [a[0]/n, a[1]/n]
def _per(a):        return [a[1], -a[0]]
def _dpr(a, b):     return a[0]*b[0] + a[1]*b[1]
def _len(a):        return math.hypot(a[0], a[1])
def _len2(a):       return a[0]*a[0] + a[1]*a[1]
def _dist2(a, b):   dx=a[0]-b[0]; dy=a[1]-b[1]; return dx*dx+dy*dy
def _dist(a, b):    return math.hypot(a[1]-b[1], a[0]-b[0])
def _uni(a):        return _div(a, _len(a))
def _is_equal(a, b): return a[0]==b[0] and a[1]==b[1]
def _med(a, b):     return _mul(_add(a, b), 0.5)
def _prj(a, b, c):  return _add(a, _mul(b, c))
def _lrp(a, b, t):  return _add(a, _mul(_sub(b, a), t))


def _rot_around(a, c, r):
    s = math.sin(r); cc = math.cos(r)
    px = a[0]-c[0]; py = a[1]-c[1]
    nx = px*cc - py*s; ny = px*s + py*cc
    return [nx+c[0], ny+c[1]]


# ---------------------------------------------------------------------------
# getStrokeRadius (from getStrokeRadius.ts)
# ---------------------------------------------------------------------------

def _get_stroke_radius(size, thinning, pressure, easing=None):
    if easing is None:
        easing = lambda t: t
    return size * easing(0.5 - thinning * (0.5 - pressure))


# ---------------------------------------------------------------------------
# simulatePressure (from simulatePressure.ts)
# ---------------------------------------------------------------------------

def _simulate_pressure(prev_pressure, distance, size):
    sp = min(1.0, distance / size)
    rp = min(1.0, 1.0 - sp)
    return min(1.0, prev_pressure + (rp - prev_pressure) * (sp * RATE_OF_PRESSURE_CHANGE))


# ---------------------------------------------------------------------------
# getStrokePoints (from getStrokePoints.ts)
# ---------------------------------------------------------------------------

def _get_stroke_points(points, streamline=0.5, size=16, last=False):
    """Convert raw input points to enriched StrokePoint dicts.

    Each StrokePoint has: point, pressure, vector, distance, running_length.
    """
    if not points:
        return []

    t = MIN_STREAMLINE_T + (1 - streamline) * STREAMLINE_T_RANGE

    # Normalise to [[x, y, pressure?], ...]
    pts = [list(p) for p in points]

    # If exactly two points, interpolate extras to help tapering (check BEFORE 1-pt)
    if len(pts) == 2:
        last_pt = pts[1]
        pts = pts[:1]
        for i in range(1, 5):
            interp = _lrp(pts[0][:2], last_pt[:2], i / 4)
            if len(last_pt) > 2 and len(pts[0]) > 2:
                interp.append(pts[0][2] + (last_pt[2] - pts[0][2]) * (i / 4))
            elif len(last_pt) > 2:
                interp.append(last_pt[2])
            pts.append(interp)

    # If only one point, add a 1-pt offset copy
    elif len(pts) == 1:
        extra = [pts[0][0] + UNIT_OFFSET[0], pts[0][1] + UNIT_OFFSET[1]]
        if len(pts[0]) > 2:
            extra.append(pts[0][2])
        pts = [pts[0], extra]

    stroke_points = [{
        "point": [pts[0][0], pts[0][1]],
        "pressure": pts[0][2] if len(pts[0]) > 2 and pts[0][2] is not None and pts[0][2] >= 0
                    else DEFAULT_FIRST_PRESSURE,
        "vector": list(UNIT_OFFSET),
        "distance": 0.0,
        "running_length": 0.0,
    }]

    has_reached_min = False
    running_length = 0.0
    prev = stroke_points[0]
    max_i = len(pts) - 1

    for i in range(1, len(pts)):
        is_complete = last and i == max_i
        if is_complete:
            point = [pts[i][0], pts[i][1]]
        else:
            point = _lrp(prev["point"], pts[i][:2], t)

        if _is_equal(prev["point"], point):
            continue

        distance = _dist(point, prev["point"])
        running_length += distance

        if i < max_i and not has_reached_min:
            if running_length < size:
                continue
            has_reached_min = True

        diff = _sub(prev["point"], point)
        sp = {
            "point": point,
            "pressure": pts[i][2] if len(pts[i]) > 2 and pts[i][2] is not None and pts[i][2] >= 0
                        else DEFAULT_PRESSURE,
            "vector": _uni(diff),
            "distance": distance,
            "running_length": running_length,
        }
        stroke_points.append(sp)
        prev = sp

    # Fix first point's vector
    if len(stroke_points) > 1:
        stroke_points[0]["vector"] = stroke_points[1]["vector"]
    else:
        stroke_points[0]["vector"] = [0.0, 0.0]

    return stroke_points


# ---------------------------------------------------------------------------
# Cap helpers (from getStrokeOutlinePoints.ts)
# ---------------------------------------------------------------------------

def _draw_dot(center, radius):
    offset_point = _add(center, [1.0, 1.0])
    start = _prj(center, _uni(_per(_sub(center, offset_point))), -radius)
    dot_pts = []
    step = 1.0 / START_CAP_SEGMENTS
    t = step
    while t <= 1.0:
        dot_pts.append(_rot_around(start, center, FIXED_PI * 2 * t))
        t += step
    return dot_pts


def _draw_round_start_cap(center, right_point, segments):
    cap = []
    step = 1.0 / segments
    t = step
    while t <= 1.0:
        cap.append(_rot_around(right_point, center, FIXED_PI * t))
        t += step
    return cap


def _draw_flat_start_cap(center, left_point, right_point):
    corners = _sub(left_point, right_point)
    oa = _mul(corners, 0.5)
    ob = _mul(corners, 0.51)
    return [_sub(center, oa), _sub(center, ob), _add(center, ob), _add(center, oa)]


def _draw_round_end_cap(center, direction, radius, segments):
    cap = []
    start = _prj(center, direction, radius)
    step = 1.0 / segments
    t = step
    while t < 1.0:
        cap.append(_rot_around(start, center, FIXED_PI * 3 * t))
        t += step
    return cap


def _draw_flat_end_cap(center, direction, radius):
    return [
        _add(center, _mul(direction, radius)),
        _add(center, _mul(direction, radius * 0.99)),
        _sub(center, _mul(direction, radius * 0.99)),
        _sub(center, _mul(direction, radius)),
    ]


def _compute_taper_distance(taper, size, total_length):
    if taper is False or taper is None:
        return 0.0
    if taper is True:
        return max(size, total_length)
    return float(taper)


def _compute_initial_pressure(points, should_simulate, size):
    acc = points[0]["pressure"]
    for sp in points[:10]:
        pressure = sp["pressure"]
        if should_simulate:
            pressure = _simulate_pressure(acc, sp["distance"], size)
        acc = (acc + pressure) / 2
    return acc


# ---------------------------------------------------------------------------
# getStrokeOutlinePoints (from getStrokeOutlinePoints.ts)
# ---------------------------------------------------------------------------

def _get_stroke_outline_points(
    points,
    size=16,
    smoothing=0.5,
    thinning=0.5,
    simulate_pressure=True,
    easing=None,
    start=None,
    end=None,
    last=False,
):
    if easing is None:
        easing = lambda t: t
    if start is None:
        start = {}
    if end is None:
        end = {}

    cap_start = start.get("cap", True)
    taper_start_ease = start.get("easing", lambda t: t * (2 - t))
    cap_end = end.get("cap", True)
    taper_end_ease = end.get("easing", lambda t: (t - 1) ** 3 + 1)  # --r*r*r+1

    if not points or size <= 0:
        return []

    total_length = points[-1]["running_length"]
    taper_start = _compute_taper_distance(start.get("taper", False), size, total_length)
    taper_end = _compute_taper_distance(end.get("taper", False), size, total_length)
    min_distance = (size * smoothing) ** 2

    left_pts = []
    right_pts = []

    prev_pressure = _compute_initial_pressure(points, simulate_pressure, size)
    radius = _get_stroke_radius(size, thinning, points[-1]["pressure"], easing)
    first_radius = None
    prev_vector = points[0]["vector"]
    prev_left_point = points[0]["point"][:]
    prev_right_point = prev_left_point[:]
    temp_left_point = prev_left_point[:]
    temp_right_point = prev_right_point[:]
    is_prev_sharp = False

    for i, sp in enumerate(points):
        pressure = sp["pressure"]
        point = sp["point"]
        vector = sp["vector"]
        distance = sp["distance"]
        running_length = sp["running_length"]
        is_last_point = i == len(points) - 1

        # Skip noise at end
        if not is_last_point and total_length - running_length < END_NOISE_THRESHOLD:
            continue

        if thinning:
            if simulate_pressure:
                pressure = _simulate_pressure(prev_pressure, distance, size)
            radius = _get_stroke_radius(size, thinning, pressure, easing)
        else:
            radius = size / 2

        if first_radius is None:
            first_radius = radius

        # Taper
        taper_start_strength = (
            taper_start_ease(running_length / taper_start)
            if running_length < taper_start else 1.0
        )
        taper_end_strength = (
            taper_end_ease((total_length - running_length) / taper_end)
            if total_length - running_length < taper_end else 1.0
        )
        radius = max(MIN_RADIUS, radius * min(taper_start_strength, taper_end_strength))

        # Sharp corners
        next_sp = points[i + 1] if not is_last_point else points[i]
        next_vector = next_sp["vector"]
        next_dpr_val = _dpr(vector, next_vector) if not is_last_point else 1.0
        prev_dpr_val = _dpr(vector, prev_vector)

        is_sharp = prev_dpr_val < 0 and not is_prev_sharp
        is_next_sharp = next_dpr_val is not None and next_dpr_val < 0

        if is_sharp or is_next_sharp:
            offset = _mul(_per(prev_vector), radius)
            step = 1.0 / CORNER_CAP_SEGMENTS
            t = 0.0
            while t <= 1.0:
                tl = _rot_around(_sub(point, offset), point, FIXED_PI * t)
                temp_left_point = [tl[0], tl[1]]
                left_pts.append(temp_left_point)
                tr = _rot_around(_add(point, offset), point, FIXED_PI * -t)
                temp_right_point = [tr[0], tr[1]]
                right_pts.append(temp_right_point)
                t += step
            prev_left_point = temp_left_point
            prev_right_point = temp_right_point
            if is_next_sharp:
                is_prev_sharp = True
            continue

        is_prev_sharp = False

        if is_last_point:
            offset = _mul(_per(vector), radius)
            left_pts.append(_sub(point, offset))
            right_pts.append(_add(point, offset))
            continue

        # Regular point
        offset = _mul(_per(_lrp(next_vector, vector, next_dpr_val)), radius)
        tl = _sub(point, offset)
        temp_left_point = [tl[0], tl[1]]
        if i <= 1 or _dist2(prev_left_point, temp_left_point) > min_distance:
            left_pts.append(temp_left_point)
            prev_left_point = temp_left_point

        tr = _add(point, offset)
        temp_right_point = [tr[0], tr[1]]
        if i <= 1 or _dist2(prev_right_point, temp_right_point) > min_distance:
            right_pts.append(temp_right_point)
            prev_right_point = temp_right_point

        prev_pressure = pressure
        prev_vector = vector

    # Caps
    first_point = points[0]["point"][:]
    last_point = (points[-1]["point"][:] if len(points) > 1
                  else _add(points[0]["point"], [1.0, 1.0]))
    start_cap = []
    end_cap = []

    if len(points) == 1:
        if not (taper_start or taper_end) or last:
            return _draw_dot(first_point, first_radius or radius)
    else:
        if taper_start or (taper_end and len(points) == 1):
            pass  # tapered start — no cap
        elif cap_start:
            start_cap.extend(_draw_round_start_cap(first_point, right_pts[0] if right_pts else first_point, START_CAP_SEGMENTS))
        else:
            start_cap.extend(_draw_flat_start_cap(first_point,
                                                   left_pts[0] if left_pts else first_point,
                                                   right_pts[0] if right_pts else first_point))

        direction = _per(_neg(points[-1]["vector"]))
        if taper_end or (taper_start and len(points) == 1):
            end_cap.append(last_point)
        elif cap_end:
            end_cap.extend(_draw_round_end_cap(last_point, direction, radius, END_CAP_SEGMENTS))
        else:
            end_cap.extend(_draw_flat_end_cap(last_point, direction, radius))

    return left_pts + end_cap + list(reversed(right_pts)) + start_cap


# ---------------------------------------------------------------------------
# getStroke — public entry point (from getStroke.ts)
# ---------------------------------------------------------------------------

def get_stroke(
    points,
    *,
    size=16,
    thinning=0.5,
    smoothing=0.5,
    streamline=0.5,
    easing=None,
    simulate_pressure=True,
    start=None,
    end=None,
    last=False,
):
    """Port of perfect-freehand getStroke.

    Args:
        points: list of [x, y] or [x, y, pressure] (pressure in [0,1]).
        size: base stroke diameter.
        thinning: pressure→width effect (0=uniform, 1=max thinning).
        smoothing: edge smoothing.
        streamline: input point streamlining (0–1).
        easing: pressure easing function (callable float→float).
        simulate_pressure: derive pressure from velocity instead of input.
        start / end: dicts with keys cap (bool), taper (bool|float), easing (callable).
        last: treat as a completed stroke (exact last point).

    Returns:
        list of [x, y] outline points.
    """
    if start is None:
        start = {}
    if end is None:
        end = {}
    stroke_pts = _get_stroke_points(points, streamline=streamline, size=size, last=last)
    return _get_stroke_outline_points(
        stroke_pts,
        size=size,
        smoothing=smoothing,
        thinning=thinning,
        simulate_pressure=simulate_pressure,
        easing=easing,
        start=start,
        end=end,
        last=last,
    )


# ---------------------------------------------------------------------------
# getSvgPathFromStroke (from packages/element/src/shape.ts)
# ---------------------------------------------------------------------------

# Trim SVG path data to ≤2 decimal places (matches Excalidraw's regex)
_TO_FIXED_PRECISION = re.compile(
    r'(\s?[A-Z]?,?-?[0-9]*\.[0-9]{0,2})(([0-9]|e|-)*)'
)


def get_svg_path_from_stroke(points):
    """Port of Excalidraw getSvgPathFromStroke.

    Converts a list of [x,y] outline points into a smooth SVG path d-string
    using midpoint quadratic Bézier segments (the 'med' smoothing technique).

    Returns:
        str: SVG path d attribute value (starts with 'M', ends with 'Z').
    """
    if not points:
        return ""

    max_i = len(points) - 1
    parts = ["M", points[0], "Q"]

    for i, point in enumerate(points):
        if i == max_i:
            parts.extend([point, _med(point, points[0]), "L", points[0], "Z"])
        else:
            parts.extend([point, _med(point, points[i + 1])])

    # Serialise to string
    tokens = []
    for p in parts:
        if isinstance(p, str):
            tokens.append(p)
        else:
            tokens.append(f"{p[0]:.6f},{p[1]:.6f}")

    raw = " ".join(tokens)
    # Trim to ≤2 decimal places (Excalidraw regex: keep only first 2 decimal digits)
    trimmed = _TO_FIXED_PRECISION.sub(r'\1', raw)
    return trimmed


# ---------------------------------------------------------------------------
# get_freedraw_svg_path — Excalidraw's getFreeDrawSvgPath (shape.ts)
# ---------------------------------------------------------------------------

def _easing_out_sine(t):
    """easeOutSine: Math.sin((t * Math.PI) / 2) — Excalidraw's freedraw easing."""
    return math.sin((t * math.pi) / 2)


def get_freedraw_svg_path(element):
    """Port of Excalidraw getFreeDrawSvgPath.

    Renders a freedraw element as a filled SVG path d-string.

    Args:
        element: Excalidraw element dict with fields:
            strokeWidth (int/float),
            simulatePressure (bool),
            points (list of [x,y]),
            pressures (list of float, optional),
            strokeOptions (dict, optional — may include 'streamline').

    Returns:
        str: SVG path d-string (to use as fill="#strokeColor" path, no stroke).
    """
    simulate_pressure = element.get("simulatePressure", True)
    stroke_width = element.get("strokeWidth", 2)
    pts = element.get("points", [])
    pressures = element.get("pressures", [])

    # Build input points: [x, y] or [x, y, pressure]
    if simulate_pressure:
        input_points = [[p[0], p[1]] for p in pts]
    else:
        if pts and pressures and len(pressures) >= len(pts):
            input_points = [[p[0], p[1], pressures[i]] for i, p in enumerate(pts)]
        elif pts and pressures:
            # Pressure array shorter than points — pad with DEFAULT_PRESSURE
            input_points = [
                [p[0], p[1], pressures[i] if i < len(pressures) else DEFAULT_PRESSURE]
                for i, p in enumerate(pts)
            ]
        else:
            # No pressures — fall back to simulate
            input_points = [[p[0], p[1]] for p in pts]
            simulate_pressure = True

    if not input_points:
        input_points = [[0, 0, 0.5]]

    # Streamline from strokeOptions (default = DEFAULT_STROKE_STREAMLINE = 0.5)
    stroke_options = element.get("strokeOptions") or {}
    streamline = stroke_options.get("streamline", DEFAULT_STROKE_STREAMLINE)

    outline = get_stroke(
        input_points,
        simulate_pressure=simulate_pressure,
        size=stroke_width * _SIZE_FACTOR,
        thinning=_THINNING,
        smoothing=_SMOOTHING,
        streamline=streamline,
        easing=_easing_out_sine,
        last=True,
    )

    return get_svg_path_from_stroke(outline)
