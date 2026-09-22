# excalidraw_arrowheads.py — exact arrowhead geometry + line options.
# Faithful Python port of:
#   packages/element/src/bounds.ts  getArrowheadSize (L714-732)
#                                   getArrowheadAngle (L734-744)
#                                   getArrowheadPoints (L746-909)
#   packages/element/src/shape.ts   getArrowheadLineOptions (L326-343)
#                                   getArrowheadShapes (L371-576)
# Stdlib-only. P4+P5 of the excalidraw-export parity plan.
import math

import roughjs
from excalidraw_bounds import point_rotate_rads
from excalidraw_shape import get_dash_array_dotted

# ---------------------------------------------------------------------------
# normalizeArrowhead (arrowheads.ts:3-21)
# ---------------------------------------------------------------------------

_LEGACY_ARROWHEAD = {
    "dot": "circle",
    "crowfoot_one": "cardinality_one",
    "crowfoot_many": "cardinality_many",
    "crowfoot_one_or_many": "cardinality_one_or_many",
}


def normalize_arrowhead(arrowhead):
    """Map legacy arrowhead aliases to canonical types.

    Port of normalizeArrowhead, arrowheads.ts:3-21.
    """
    if arrowhead is None:
        return None
    return _LEGACY_ARROWHEAD.get(arrowhead, arrowhead)


# ---------------------------------------------------------------------------
# Constants (bounds.ts L711-712)
# ---------------------------------------------------------------------------

_CARDINALITY_MARKER_SIZE = 20   # bounds.ts L711
_CROWFOOT_ARROWHEAD_SIZE = 15   # bounds.ts L712


# ---------------------------------------------------------------------------
# getArrowheadSize (bounds.ts L714-732)
# ---------------------------------------------------------------------------

def get_arrowhead_size(arrowhead: str) -> int:
    """Return the pixel size for the given arrowhead kind.

    Source: getArrowheadSize, bounds.ts L714-732.
    """
    if arrowhead == "arrow":
        return 25
    if arrowhead in ("diamond", "diamond_outline"):
        return 12
    if arrowhead in ("cardinality_many", "cardinality_one_or_many",
                     "cardinality_zero_or_many"):
        return _CROWFOOT_ARROWHEAD_SIZE  # 15
    if arrowhead in ("cardinality_one", "cardinality_exactly_one",
                     "cardinality_zero_or_one"):
        return _CARDINALITY_MARKER_SIZE  # 20
    return 15  # default


# ---------------------------------------------------------------------------
# getArrowheadAngle (bounds.ts L734-744)
# ---------------------------------------------------------------------------

def get_arrowhead_angle(arrowhead: str) -> float:
    """Return the half-opening angle in degrees for the given arrowhead kind.

    Source: getArrowheadAngle, bounds.ts L734-744.
    """
    if arrowhead == "bar":
        return 90.0
    if arrowhead == "arrow":
        return 20.0
    return 25.0  # default


# ---------------------------------------------------------------------------
# Internal: reversed cubic Bezier evaluation (bounds.ts ~L787-797)
# ---------------------------------------------------------------------------

def _bezier_eq(t, p0, p1, p2, p3, idx):
    """Evaluate the 'reversed' cubic Bezier at parameter t.

    bounds.ts uses:
        eq(t, idx) = (1-t)^3 * p3[idx]
                   + 3t(1-t)^2 * p2[idx]
                   + 3t^2(1-t)  * p1[idx]
                   + t^3        * p0[idx]

    Note: p0 carries the t^3 term (not the standard (1-t)^3 term).
    This matches the TS source exactly.
    """
    return (
        (1 - t) ** 3 * p3[idx]
        + 3 * t * (1 - t) ** 2 * p2[idx]
        + 3 * t ** 2 * (1 - t) * p1[idx]
        + t ** 3 * p0[idx]
    )


# ---------------------------------------------------------------------------
# getArrowheadPoints (bounds.ts L746-909)
# ---------------------------------------------------------------------------

def get_arrowhead_points(el, opset, position: str, arrowhead,
                          offset_multiplier=0):
    """Return arrowhead tip + barb/diamond coords for the given position.

    Parameters
    ----------
    el                : element dict (needs "points", "strokeWidth")
    opset             : roughjs opset dict with "ops" list of op tuples
                        format: ('move',x,y) | ('lineTo',x,y) |
                                ('bcurveTo', cp1x,cp1y, cp2x,cp2y, ex,ey)
    position          : "start" or "end"
    arrowhead         : arrowhead kind string, or None
    offset_multiplier : float, default 0.  Shifts the arrowhead tip along
                        the shaft by ``min_size * offset_multiplier`` pixels,
                        matching the offsetMultiplier parameter used in the
                        cardinality composite branches of shape.ts.

    Returns
    -------
    For "arrow": (tx, ty, x3, y3, x4, y4)
    For "diamond"/"diamond_outline": (tx, ty, x3, y3, ox, oy, x4, y4)
    For "circle"/"circle_outline": (tx, ty, diameter)
    For "bar" and crowfoot/cardinality types: coords per TS source
    None if arrowhead is None or opset is empty.

    Source: getArrowheadPoints, bounds.ts L746-909.
    """
    if arrowhead is None:
        return None

    ops = opset.get("ops", [])
    if not ops:
        return None

    # Gather only bcurveTo ops and the full ops list for prev-op lookup.
    # TS: const ops = getCurvePathOps(shape[0])
    # TS: const index = position === "start" ? 1 : ops.length - 1
    # 'index' is into the full ops list (including move).
    index = 1 if position == "start" else len(ops) - 1

    op = ops[index]
    if op[0] != "bcurveTo":
        return None
    # data = [cp1x, cp1y, cp2x, cp2y, ex, ey]
    data = op[1:]   # (cp1x, cp1y, cp2x, cp2y, ex, ey)
    if len(data) < 6:
        return None

    # p3 = endpoint of this bcurveTo segment
    p3 = (data[4], data[5])
    # p2 = second control point
    p2 = (data[2], data[3])
    # p1 = first control point
    p1 = (data[0], data[1])

    # p0 = start of this bezier segment = end of previous op
    prev_op = ops[index - 1]
    if prev_op[0] == "move":
        p0 = (prev_op[1], prev_op[2])
    elif prev_op[0] == "bcurveTo":
        p0 = (prev_op[5], prev_op[6])
    else:
        p0 = (0.0, 0.0)

    # Tip is the last point of the curve for "end", first point for "start"
    if position == "start":
        x2, y2 = p0
    else:
        x2, y2 = p3

    # Sample B(0.3) for direction (see TS comment: "chosen arbitrarily, works best")
    x1 = _bezier_eq(0.3, p0, p1, p2, p3, 0)
    y1 = _bezier_eq(0.3, p0, p1, p2, p3, 1)

    # Normalized direction vector tip ← sampled point
    distance = math.hypot(x2 - x1, y2 - y1)
    if distance == 0:
        return None
    nx = (x2 - x1) / distance
    ny = (y2 - y1) / distance

    size = get_arrowhead_size(arrowhead)

    # Length = distance of last element segment (bounds.ts L822-833)
    points = el.get("points") or [[0, 0]]
    if position == "end":
        cx, cy = points[-1] if len(points) > 0 else (0, 0)
        px, py = points[-2] if len(points) > 1 else (0, 0)
    else:
        cx, cy = points[0] if len(points) > 0 else (0, 0)
        px, py = points[1] if len(points) > 1 else (0, 0)
    length = math.hypot(cx - px, cy - py)

    # lengthMultiplier: diamond=0.25, others=0.5 (bounds.ts L838-839)
    length_multiplier = (
        0.25 if arrowhead in ("diamond", "diamond_outline") else 0.5
    )
    min_size = min(size, length * length_multiplier)

    # Offset along shaft (offsetMultiplier=0 by default → tx=x2, ty=y2).
    # Cardinality composite branches pass non-zero values to space multiple
    # markers along the shaft (shape.ts L390-566).
    tx = x2 - nx * min_size * offset_multiplier
    ty = y2 - ny * min_size * offset_multiplier

    # Base of arrowhead along shaft
    xs = tx - nx * min_size
    ys = ty - ny * min_size

    # ---- circle / circle_outline ----
    # NOT parity-verified (no golden/corpus case)
    if arrowhead in ("circle", "circle_outline"):
        diameter = math.hypot(ys - ty, xs - tx) + el.get("strokeWidth", 1) - 2
        return (tx, ty, diameter)

    angle_deg = get_arrowhead_angle(arrowhead)
    angle_rad = math.radians(angle_deg)

    # ---- crowfoot many / one_or_many (swap tip and base) ----
    if arrowhead in ("cardinality_many", "cardinality_one_or_many"):
        x3, y3 = point_rotate_rads((tx, ty), (xs, ys), -angle_rad)
        x4, y4 = point_rotate_rads((tx, ty), (xs, ys), angle_rad)
        return (xs, ys, x3, y3, x4, y4)

    # ---- standard barb rotation: rotate (xs,ys) about tip (tx,ty) ----
    x3, y3 = point_rotate_rads((xs, ys), (tx, ty), -angle_rad)
    x4, y4 = point_rotate_rads((xs, ys), (tx, ty), angle_rad)

    # ---- diamond / diamond_outline: add opposite point ----
    if arrowhead in ("diamond", "diamond_outline"):
        if position == "start":
            ppx, ppy = points[1] if len(points) > 1 else (0, 0)
            ox, oy = point_rotate_rads(
                (tx + min_size * 2, ty), (tx, ty),
                math.atan2(ppy - ty, ppx - tx)
            )
        else:
            ppx, ppy = points[-2] if len(points) > 1 else (0, 0)
            ox, oy = point_rotate_rads(
                (tx - min_size * 2, ty), (tx, ty),
                math.atan2(ty - ppy, tx - ppx)
            )
        return (tx, ty, x3, y3, ox, oy, x4, y4)

    # ---- arrow (standard) ----
    return (tx, ty, x3, y3, x4, y4)


# ---------------------------------------------------------------------------
# Circle rendering helper — shared by dot/circle/circle_outline (Task 4)
# and by cardinality zero-circle variants that pass diameter_scale=0.8 (Task 5).
# ---------------------------------------------------------------------------

def _render_circle(tx: float, ty: float, diameter: float,
                   line_opts: dict, diameter_scale: float = 1.0) -> list:
    """Render a rough circle arrowhead centred at (tx, ty).

    Faithful port of generateArrowheadOutlineCircle (shape.ts L345-369):
      generator.circle(tx, ty, diameter*diameterScale,
                       {fillStyle:"solid", roughness: min(0.5, roughness),
                        <no strokeLineDash>})
    rough.js fills a solid circle over its estimatedPoints (ellipse_with_params).

    Returns [fill_set, outline_opset] (two opsets).
    """
    circle_opts = dict(line_opts)
    circle_opts.pop("strokeLineDash", None)
    circle_opts["roughness"] = min(0.5, circle_opts.get("roughness", 0))

    d = diameter * diameter_scale

    circle_opts["randomizer"] = None
    ep = roughjs.generate_ellipse_params(d, d, circle_opts)

    circle_opts["randomizer"] = None
    res = roughjs.ellipse_with_params(tx, ty, circle_opts, ep)

    outline = res["opset"]

    circle_opts["randomizer"] = None
    fill_set = roughjs.solid_fill_polygon([res["estimated_points"]], circle_opts)

    return [fill_set, outline]


# ---------------------------------------------------------------------------
# getArrowheadLineOptions (shape.ts L326-343)
# ---------------------------------------------------------------------------

def get_arrowhead_shapes(el, opset, position: str, arrowhead, rough_options: dict):
    """Return a list of opsets for the given arrowhead type.

    Dispatches on arrowhead:
        "arrow"                → two rough lines (V barbs)
        "triangle"             → fillPath (solid polygon) + path (rough outline)
        "triangle_outline"     → fillPath (solid polygon) + path (rough outline)
        "diamond"              → fillPath (solid polygon) + path
        "diamond_outline"      → fillPath (solid polygon) + path
        "dot"/"circle"/"circle_outline" → fillPath (solid ellipse) + path (rough ellipse)
        "bar"                  → two rough lines at 90°
        crowfoot variants      → lines per geometry

    Both filled and outline variants emit [fill_set, stroke_set]; the rendered
    fill colour is determined by _path_el (el.backgroundColor, transparent for
    arrows) — not by any parameter threaded here.

    Source: getArrowheadShapes, shape.ts L371-576.
    Returns [] if arrowhead is None or geometry unavailable.
    """
    if arrowhead is None:
        return []

    pts = get_arrowhead_points(el, opset, position, arrowhead)
    if pts is None:
        return []

    line_opts = roughjs.resolve_options(**arrowhead_line_options(el, rough_options))

    def _fresh_line(x1, y1, x2, y2):
        """Call roughjs.line with a fresh randomizer each time.

        In rough.js, generator.line() always calls getOptions() which creates a
        new Random(seed) object, so every independent shape call starts from the
        same seed.  In Python we share a single resolved-options dict; clearing
        'randomizer' before each call replicates that reset, ensuring barb2 does
        not consume RNG state left over from barb1.
        """
        line_opts['randomizer'] = None
        return roughjs.line(x1, y1, x2, y2, line_opts)

    # ---- "arrow" type: two line barbs ----
    if arrowhead == "arrow":
        tx, ty, x3, y3, x4, y4 = pts
        return [
            _fresh_line(x3, y3, tx, ty),
            _fresh_line(x4, y4, tx, ty),
        ]

    # ---- bar: same geometry as arrow but angle=90° → two lines to tip ----
    # shape.ts:567-575: bar shares default case with arrow →
    # generateArrowheadLinesToTip = two lines x3→tip, x4→tip (shape.ts:309-323)
    if arrowhead == "bar":
        tx, ty, x3, y3, x4, y4 = pts
        return [
            _fresh_line(x3, y3, tx, ty),
            _fresh_line(x4, y4, tx, ty),
        ]

    # ---- triangle / triangle_outline ----
    # Both variants emit [fill_set, stroke_set].
    # The rendered fill colour is determined by _path_el (el.backgroundColor,
    # transparent for arrows) — not by fill_opts['fill'].
    # Source: shape.ts L404-478.
    if arrowhead in ("triangle", "triangle_outline"):
        tx, ty, x3, y3, x4, y4 = pts
        poly_pts = [[tx, ty], [x3, y3], [x4, y4]]
        fill_opts = dict(line_opts)
        fill_opts['randomizer'] = None
        fill_set = roughjs.solid_fill_polygon([poly_pts], fill_opts)
        line_opts['randomizer'] = None
        stroke_set = roughjs.polygon(poly_pts, line_opts)
        return [fill_set, stroke_set]

    # ---- diamond / diamond_outline ----
    # Both variants emit [fill_set, stroke_set].
    # The rendered fill colour is determined by _path_el (el.backgroundColor,
    # transparent for arrows) — not by fill_opts['fill'].
    # Source: shape.ts L404-478.
    if arrowhead in ("diamond", "diamond_outline"):
        tx, ty, x3, y3, ox, oy, x4, y4 = pts
        poly_pts = [[tx, ty], [x3, y3], [ox, oy], [x4, y4]]
        fill_opts = dict(line_opts)
        fill_opts['randomizer'] = None
        fill_set = roughjs.solid_fill_polygon([poly_pts], fill_opts)
        line_opts['randomizer'] = None
        stroke_set = roughjs.polygon(poly_pts, line_opts)
        return [fill_set, stroke_set]

    # ---- dot / circle / circle_outline ----
    # Faithful port of generateArrowheadOutlineCircle (shape.ts L345-369).
    # generator.circle(tx, ty, diameter*diameterScale, {fillStyle:"solid",
    #   roughness: min(0.5, roughness), <no strokeLineDash>}) centred at (tx,ty).
    # rough.js fills a solid circle over its estimatedPoints.
    if arrowhead in ("dot", "circle", "circle_outline"):
        tx, ty, diameter = pts
        return _render_circle(tx, ty, diameter, line_opts, diameter_scale=1.0)

    # ---- Composition helpers (mirrors shape.ts:295-323) ----
    # _cardinality_one: one perpendicular bar at a given shaft offset.
    #   Port of generateArrowheadCardinalityOne (shape.ts L295-307).
    def _cardinality_one(off):
        p = get_arrowhead_points(el, opset, position, "cardinality_one",
                                 offset_multiplier=off)
        if p is None:
            return []
        _tx, _ty, x3, y3, x4, y4 = p
        return [_fresh_line(x3, y3, x4, y4)]

    # _lines_to_tip: two crow's-foot lines to the shaft tip.
    #   Port of generateArrowheadLinesToTip (shape.ts L309-323).
    def _lines_to_tip(off):
        p = get_arrowhead_points(el, opset, position, "cardinality_many",
                                 offset_multiplier=off)
        if p is None:
            return []
        xs, ys, x3, y3, x4, y4 = p
        return [_fresh_line(x3, y3, xs, ys), _fresh_line(x4, y4, xs, ys)]

    # _zero_circle: outline circle scaled 0.8 at shaft offset 1.5.
    #   Port of generateArrowheadOutlineCircle with diameterScale=0.8 (shape.ts).
    def _zero_circle():
        p = get_arrowhead_points(el, opset, position, "circle_outline",
                                 offset_multiplier=1.5)
        if p is None:
            return []
        _tx, _ty, diameter = p
        return _render_circle(_tx, _ty, diameter, line_opts, diameter_scale=0.8)

    # ---- cardinality_one: single perpendicular bar (offset 0) ----
    # Port of shape.ts case "cardinality_one" (L490-496).
    # Direct implementation — keep output identical to pre-Task-5 (pindown stable).
    if arrowhead == "cardinality_one":
        tx, ty, x3, y3, x4, y4 = pts
        return [_fresh_line(x3, y3, x4, y4)]

    # ---- cardinality_many: two crow's-foot lines to tip (offset 0) ----
    # Port of shape.ts case "cardinality_many" (L497-503).
    # Direct implementation — keep output identical to pre-Task-5 (pindown stable).
    if arrowhead == "cardinality_many":
        xs, ys, x3, y3, x4, y4 = pts
        return [_fresh_line(xs, ys, x3, y3), _fresh_line(xs, ys, x4, y4)]

    # ---- cardinality_exactly_one: two bars at offsets -0.5 and 0 ----
    # Port of shape.ts case "cardinality_exactly_one" (L504-518).
    # Composition: CardinalityOne(off=-0.5) + CardinalityOne(off=0)
    if arrowhead == "cardinality_exactly_one":
        return _cardinality_one(-0.5) + _cardinality_one(0)

    # ---- cardinality_one_or_many: crow's feet + bar ----
    # Port of shape.ts case "cardinality_one_or_many" (L519-533).
    # Composition: LinesToTip(off=0) + CardinalityOne(off=-0.25)
    if arrowhead == "cardinality_one_or_many":
        return _lines_to_tip(0) + _cardinality_one(-0.25)

    # ---- cardinality_zero_or_one: circle + bar ----
    # Port of shape.ts case "cardinality_zero_or_one" (L534-549).
    # Composition: ZeroCircle(off=1.5, scale=0.8) + CardinalityOne(off=-0.5)
    if arrowhead == "cardinality_zero_or_one":
        return _zero_circle() + _cardinality_one(-0.5)

    # ---- cardinality_zero_or_many: crow's feet + circle ----
    # Port of shape.ts case "cardinality_zero_or_many" (L550-565).
    # Composition: LinesToTip(off=0) + ZeroCircle(off=1.5, scale=0.8)
    if arrowhead == "cardinality_zero_or_many":
        return _lines_to_tip(0) + _zero_circle()

    return []


def arrowhead_line_options(el, base_rough_options: dict) -> dict:
    """Return a copy of rough options with dash stripped and roughness capped.

    For dotted strokes: keep a reduced strokeLineDash (smaller gap).
    For solid/dashed: delete strokeLineDash entirely.
    roughness is capped at min(1, roughness).

    Source: getArrowheadLineOptions, shape.ts L326-343.
    """
    line_options = dict(base_rough_options)

    stroke_style = el.get("strokeStyle", "solid")
    sw = el.get("strokeWidth", 1)

    if stroke_style == "dotted":
        # shape.ts: reduce gap by 1 to make dotted caps more legible
        dash = get_dash_array_dotted(sw - 1)
        line_options["strokeLineDash"] = [dash[0], dash[1] - 1]
    else:
        # solid or dashed: solid arrowhead cap
        line_options.pop("strokeLineDash", None)

    line_options["roughness"] = min(1, line_options.get("roughness", 0))

    return line_options
