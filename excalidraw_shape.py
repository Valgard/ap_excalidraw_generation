# excalidraw_shape.py — element → rough options + drawables (stdlib only).
# source: excalidraw packages/element/src/shape.ts + bounds.ts + utils.ts
import math

ROUGHNESS = {"architect": 0, "artist": 1, "cartoonist": 2}
_ROUND_TYPES = {1, 2}  # LEGACY, PROPORTIONAL_RADIUS use x*0.25; 3 = ADAPTIVE

def _is_transparent(c): return c is None or c == "transparent" or c == ""

def get_dash_array_dashed(sw): return [8, 8 + sw]      # shape.ts L168
def get_dash_array_dotted(sw): return [1.5, 6 + sw]    # shape.ts L169

def adjust_roughness(el):                              # shape.ts L172-193
    r = el["roughness"]; w, h = el["width"], el["height"]
    max_s, min_s = max(w, h), min(w, h)
    is_linear = el["type"] in ("line", "arrow")
    can_round = el["type"] in ("rectangle", "diamond")
    if ((min_s >= 20 and max_s >= 50)
        or (min_s >= 15 and el.get("roundness") and can_round)
        or (is_linear and max_s >= 50)):
        return r
    return min(r / (3 if max_s < 10 else 2), 2.5)

def get_corner_radius(x, el):                          # utils.ts L483-504
    roundness = el.get("roundness")
    if not roundness: return 0
    t = roundness.get("type")
    if t in _ROUND_TYPES: return x * 0.25
    if t == 3:
        fixed = roundness.get("value", 32); cutoff = fixed / 0.25
        return x * 0.25 if x <= cutoff else fixed
    return 0

def get_diamond_points(el):                            # bounds.ts L522-535
    w, h = el["width"], el["height"]
    top_x = math.floor(w/2) + 1; right_y = math.floor(h/2) + 1
    return [[top_x, 0], [w, right_y], [top_x, h], [0, right_y]]

def generate_rough_options(el, continuous_path=False):  # shape.ts L195-260
    ss = el["strokeStyle"]; sw = el["strokeWidth"]
    o = {
        "seed": el["seed"],
        "disableMultiStroke": ss != "solid",
        "strokeWidth": sw + 0.5 if ss != "solid" else sw,
        "fillWeight": sw / 2,
        "hachureGap": sw * 4,
        "roughness": adjust_roughness(el),
        "stroke": el["strokeColor"],
        "preserveVertices": continuous_path or adjust_roughness(el) < ROUGHNESS["cartoonist"],
        "curveStepCount": 9, "curveFitting": 0.95, "maxRandomnessOffset": 2,
        "bowing": 1, "curveTightness": 0, "fillShapeRoughnessGain": 0.8,
        "disableMultiStrokeFill": False,
    }
    if ss == "dashed": o["strokeLineDash"] = get_dash_array_dashed(sw)
    elif ss == "dotted": o["strokeLineDash"] = get_dash_array_dotted(sw)
    t = el["type"]
    if t in ("rectangle", "diamond", "ellipse"):
        o["fillStyle"] = el["fillStyle"]
        if not _is_transparent(el["backgroundColor"]): o["fill"] = el["backgroundColor"]
        if t == "ellipse": o["curveFitting"] = 1
    elif t == "line":
        pass  # fill only if loop — handled in generate_element_shape
    return o

# ---------------------------------------------------------------------------
# Task 7 + P5: generate_element_shape + all arrowhead types (both ends)
# source: shape.ts L753-991, bounds.ts L746-909
# ---------------------------------------------------------------------------
import roughjs

def _o(el, continuous=False):
    return roughjs.resolve_options(**generate_rough_options(el, continuous))

def _rounded_rect_d(w, h, r):                          # shape.ts L780-789
    """Build the SVG path d-string for a rounded rectangle (matches Excalidraw exactly)."""
    return (f"M {r} 0 L {w - r} 0 Q {w} 0, {w} {r} L {w} {h - r} "
            f"Q {w} {h}, {w - r} {h} L {r} {h} Q 0 {h}, 0 {h - r} L 0 {r} Q 0 0, {r} 0")


def _rounded_diamond_d(el):                            # shape.ts L822-855
    """Build the SVG path d-string for a rounded diamond (matches Excalidraw exactly)."""
    pts = get_diamond_points(el)
    top_x, top_y   = pts[0]; right_x, right_y = pts[1]
    bot_x, bot_y   = pts[2]; left_x, left_y   = pts[3]
    vr = get_corner_radius(abs(top_x - left_x), el)
    hr = get_corner_radius(abs(right_y - top_y), el)
    return (
        f"M {top_x + vr} {top_y + hr} "
        f"L {right_x - vr} {right_y - hr} "
        f"C {right_x} {right_y}, {right_x} {right_y}, {right_x - vr} {right_y + hr} "
        f"L {bot_x + vr} {bot_y - hr} "
        f"C {bot_x} {bot_y}, {bot_x} {bot_y}, {bot_x - vr} {bot_y - hr} "
        f"L {left_x + vr} {left_y + hr} "
        f"C {left_x} {left_y}, {left_x} {left_y}, {left_x + vr} {left_y - hr} "
        f"L {top_x - vr} {top_y + hr} "
        f"C {top_x} {top_y}, {top_x} {top_y}, {top_x + vr} {top_y + hr}"
    )


def generate_element_shape(el):
    t = el["type"]
    o = _o(el)   # ONE options object per element -> ONE shared randomizer across outline+fill (rough does this)
    if t == "rectangle":
        w, h = el["width"], el["height"]
        if el.get("roundness"):
            # Task 7b: rounded rectangle via generator.path with continuous=True
            o = _o(el, continuous=True)
            r = get_corner_radius(min(w, h), el)
            d = _rounded_rect_d(w, h, r)
            stroke = roughjs.path(d, o)
            return _with_path_fill(el, o, stroke, d, [[0, 0], [w, 0], [w, h], [0, h]])
        stroke = roughjs.rectangle(0, 0, w, h, o)           # rough computes the OUTLINE first (advances RNG)
        return _with_fill(el, o, stroke, [[0, 0], [w, 0], [w, h], [0, h]])
    if t == "diamond":
        if el.get("roundness"):
            # Task 7b: rounded diamond via generator.path with continuous=True
            o = _o(el, continuous=True)
            d = _rounded_diamond_d(el)
            pts = get_diamond_points(el)
            stroke = roughjs.path(d, o)
            return _with_path_fill(el, o, stroke, d, pts)
        pts = get_diamond_points(el)
        stroke = roughjs.polygon([[p[0], p[1]] for p in pts], o)
        return _with_fill(el, o, stroke, pts)
    if t == "ellipse":
        w, h = el["width"], el["height"]
        if not _is_transparent(el["backgroundColor"]):
            ep = roughjs.generate_ellipse_params(w, h, o)
            stroke = roughjs.ellipse_with_params(w / 2, h / 2, o, ep)["opset"]   # 1st call -> stroke
            fill = roughjs.ellipse_with_params(w / 2, h / 2, o, ep)["opset"]     # 2nd call -> fill (rough re-calls)
            return [{"type": "fillPath", "ops": fill["ops"]}, stroke]
        return [roughjs.ellipse(w / 2, h / 2, w, h, o)]
    if t in ("embeddable", "iframe"):
        # staticSvgScene.ts: embeddable/iframe rendered as a rectangle shape
        w, h = el["width"], el["height"]
        if el.get("roundness"):
            o = _o(el, continuous=True)
            r = get_corner_radius(min(w, h), el)
            d = _rounded_rect_d(w, h, r)
            stroke = roughjs.path(d, o)
            return _with_path_fill(el, o, stroke, d, [[0, 0], [w, 0], [w, h], [0, h]])
        stroke = roughjs.rectangle(0, 0, w, h, o)
        return _with_fill(el, o, stroke, [[0, 0], [w, 0], [w, h], [0, h]])
    if t in ("line", "arrow"):
        pts = [[p[0], p[1]] for p in (el.get("points") or [[0, 0]])]
        if el.get("roundness"):
            # Task 7b: curved/rounded line/arrow via roughjs.curve
            stroke = roughjs.curve(pts, o)
        else:
            stroke = roughjs.linear_path(pts, False, o)
        sets = [stroke]
        if t == "arrow":
            # Lazy import to break circular dependency:
            # excalidraw_arrowheads → excalidraw_bounds → excalidraw_shape
            from excalidraw_arrowheads import get_arrowhead_shapes, normalize_arrowhead
            base_opts = generate_rough_options(el)
            start_ah = normalize_arrowhead(el.get("startArrowhead"))  # None by default → no head
            end_ah = normalize_arrowhead(el.get("endArrowhead", "arrow"))  # "arrow" by default
            # Tag arrowhead opsets so the renderer draws them SOLID. Excalidraw applies
            # the shaft's strokeLineDash only to the shaft, never the arrowheads
            # (getArrowheadLineOptions strips it); without this, dashed arrows render
            # broken/faint arrowhead barbs instead of bold solid chevrons.
            for pos, ah in (("start", start_ah), ("end", end_ah)):
                if ah:
                    for op in get_arrowhead_shapes(el, stroke, pos, ah, base_opts):
                        op["_arrowhead"] = True
                        sets.append(op)
        return sets
    return []

def _merged_shape(ops):
    """Strip intermediate move ops (keep only the first), matching rough.js _mergedShape.

    Source: generator.ts _mergedShape — used for solid-fill path opsets so the fill
    renders as a single connected closed curve rather than disconnected segments.
    """
    return [op for i, op in enumerate(ops) if i == 0 or op[0] != "move"]


def _with_path_fill(el, o, stroke, d, polygon_pts=None):
    """Return [fill_opset, stroke_opset] for a path-based shape with solid fill.

    For rounded rectangles and diamonds, Excalidraw uses generator.path() for
    the fill too (not solidFillPolygon).  The fill is svgPath(d, {
        disableMultiStroke: true,
        roughness: roughness + fillShapeRoughnessGain
    }) with intermediate move ops stripped (_mergedShape).

    The fill is computed AFTER the stroke so both calls share the same randomizer
    in sequence — the fill call uses RNG state continuing from where the stroke
    left off.  This matches rough.js generator.path() which calls svgPath(d, o)
    for the stroke first, then svgPath(d, {...o, ...}) for the fill.

    Source: generator.ts path() L169-195 (solid-fill single-contour branch).
    Falls back to fill_polygon with polygon_pts for non-solid fill styles.

    polygon_pts: list of [x, y] corner points for the bounding polygon used by
    hachure/cross-hatch fill (rectangle corners or diamond vertices).  Required
    when fillStyle is not "solid" and backgroundColor is non-transparent.
    """
    if _is_transparent(el.get("backgroundColor")):
        return [stroke]
    fill_style = el.get("fillStyle", "hachure")
    if fill_style == "solid":
        # o already has its randomizer in the post-stroke state — reuse it for the
        # fill call (same shared-randomizer approach as rough.js generator.path).
        o_fill = dict(o)   # shallow copy; shares the same randomizer object
        o_fill["disableMultiStroke"] = True
        # Mirrors rough.js generator.ts: roughness ? roughness+gain : 0
        # When roughness=0 (falsy), fill roughness stays 0 (no gain applied).
        base_r = o_fill.get("roughness") or 0
        o_fill["roughness"] = (base_r + o_fill.get("fillShapeRoughnessGain", 0.8)) if base_r else 0
        # NOTE: do NOT reset o_fill["randomizer"] — continue from post-stroke RNG state
        fill_path = roughjs.path(d, o_fill)
        merged = _merged_shape(fill_path["ops"])
        fill_opset = {"type": "fillPath", "ops": merged}
        return [fill_opset, stroke]
    # hachure / cross-hatch: delegate to polygon-based fill using real polygon corners
    pts = polygon_pts or []
    return [roughjs.fill_polygon([[[p[0], p[1]] for p in pts]], o), stroke]


def _with_fill(el, o, stroke, polygon_pts):
    if _is_transparent(el["backgroundColor"]):
        return [stroke]
    fill = roughjs.fill_polygon([[[p[0], p[1]] for p in polygon_pts]], o)  # dispatches by fillStyle
    return [fill, stroke]
