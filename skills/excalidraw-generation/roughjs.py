# roughjs.py — faithful Python 3 (stdlib-only) port of a subset of rough.js 4.6.x.
# Source: rough-stuff/rough @ master — src/{math,renderer,generator}.ts
# Op tuples: ('move',x,y) | ('lineTo',x,y) | ('bcurveTo',x1,y1,x2,y2,x,y)
# OpSet = {'type': 'path'|'fillPath', 'ops': [op, ...]}
# CRITICAL: order of Random.next() calls is byte-load-bearing for seeded output.
import math

DEFAULT_OPTIONS = {                       # source: generator.ts L14-35
    'maxRandomnessOffset': 2, 'roughness': 1, 'bowing': 1,
    'curveTightness': 0, 'curveFitting': 0.95, 'curveStepCount': 9,
    'fillStyle': 'hachure', 'fillWeight': -1, 'hachureAngle': -41, 'hachureGap': -1,
    'strokeWidth': 1,
    'seed': 0, 'disableMultiStroke': False, 'disableMultiStrokeFill': False,
    'preserveVertices': False, 'fillShapeRoughnessGain': 0.8,
}

def resolve_options(**overrides):
    o = dict(DEFAULT_OPTIONS); o.update(overrides); return o

_UINT32 = 0xFFFFFFFF
def _imul(a, b):                          # Math.imul: signed 32-bit multiply
    prod = ((a & _UINT32) * (b & _UINT32)) & _UINT32
    return prod - 0x100000000 if prod >= 0x80000000 else prod

class Random:                             # source: math.ts L5-19
    def __init__(self, seed): self.seed = seed
    def next(self):
        if self.seed:
            self.seed = _imul(48271, self.seed)
            return ((2**31 - 1) & (self.seed & _UINT32)) / 2**31
        import random as _r; return _r.random()

def random(o):                            # source: renderer.ts L267-272
    if not o.get('randomizer'):
        o['randomizer'] = Random(o.get('seed') or 0)
    return o['randomizer'].next()

def _offset(mn, mx, o, gain=1):           # source: renderer.ts L274-276
    return o['roughness'] * gain * ((random(o) * (mx - mn)) + mn)
def _offset_opt(x, o, gain=1):            # source: renderer.ts L278-280
    return _offset(-x, x, o, gain)

def _fmt(v, decimals):
    s = f"{round(float(v), decimals):.{decimals}f}".rstrip('0').rstrip('.')
    return s if s not in ('', '-0') else '0'

def ops_to_path(opset, decimals=2):       # source: rough.js svg.ts opsToPath
    out = []
    for op in opset['ops']:
        kind, *d = op
        f = [_fmt(v, decimals) for v in d]
        if kind == 'move':      out.append(f"M{f[0]} {f[1]}")
        elif kind == 'lineTo':  out.append(f"L{f[0]} {f[1]}")
        elif kind == 'bcurveTo':out.append(f"C{f[0]} {f[1]}, {f[2]} {f[3]}, {f[4]} {f[5]}")
    return " ".join(out)

def _line(x1, y1, x2, y2, o, move, overlay):        # source: renderer.ts L292-361
    length_sq = (x1 - x2)**2 + (y1 - y2)**2
    length = math.sqrt(length_sq)
    gain = 1 if length < 200 else 0.4 if length > 500 else (-0.0016668)*length + 1.233334
    offset = o['maxRandomnessOffset'] or 0
    if (offset*offset*100) > length_sq: offset = length/10
    half = offset/2
    diverge = 0.2 + random(o)*0.2
    mdx = _offset_opt(o['bowing']*o['maxRandomnessOffset']*(y2-y1)/200, o, gain)
    mdy = _offset_opt(o['bowing']*o['maxRandomnessOffset']*(x1-x2)/200, o, gain)
    ops = []; preserve = o['preserveVertices']
    rh = lambda: _offset_opt(half, o, gain)
    rf = lambda: _offset_opt(offset, o, gain)
    r = rh if overlay else rf
    if move:
        ops.append(('move', x1 + (0 if preserve else r()), y1 + (0 if preserve else r())))
    ops.append(('bcurveTo',
        mdx + x1 + (x2-x1)*diverge + r(),        mdy + y1 + (y2-y1)*diverge + r(),
        mdx + x1 + 2*(x2-x1)*diverge + r(),      mdy + y1 + 2*(y2-y1)*diverge + r(),
        x2 + (0 if preserve else r()),           y2 + (0 if preserve else r())))
    return ops

def _double_line(x1, y1, x2, y2, o, filling=False):  # source: renderer.ts L282-290
    single = o['disableMultiStrokeFill'] if filling else o['disableMultiStroke']
    o1 = _line(x1, y1, x2, y2, o, True, False)
    return o1 if single else o1 + _line(x1, y1, x2, y2, o, True, True)

def line(x1, y1, x2, y2, o):                          # source: renderer.ts L21-23
    return {'type': 'path', 'ops': _double_line(x1, y1, x2, y2, o)}

def linear_path(points, close, o):                    # source: renderer.ts L25-40
    n = len(points)
    if n > 2:
        ops = []
        for i in range(n-1):
            ops += _double_line(points[i][0], points[i][1], points[i+1][0], points[i+1][1], o)
        if close:
            ops += _double_line(points[n-1][0], points[n-1][1], points[0][0], points[0][1], o)
        return {'type': 'path', 'ops': ops}
    if n == 2:
        return line(points[0][0], points[0][1], points[1][0], points[1][1], o)
    return {'type': 'path', 'ops': []}

def polygon(points, o):                               # source: renderer.ts L42-44
    return linear_path(points, True, o)

def rectangle(x, y, w, h, o):                         # source: renderer.ts L46-54 (4-pt polygon)
    return polygon([[x, y], [x+w, y], [x+w, y+h], [x, y+h]], o)

def _curve(points, close_point, o):                   # source: renderer.ts L391-424
    n = len(points); ops = []
    if n > 3:
        s = 1 - o['curveTightness']
        ops.append(('move', points[1][0], points[1][1]))
        i = 1
        while (i + 2) < n:
            b1 = (points[i][0] + (s*points[i+1][0] - s*points[i-1][0])/6,
                  points[i][1] + (s*points[i+1][1] - s*points[i-1][1])/6)
            b2 = (points[i+1][0] + (s*points[i][0] - s*points[i+2][0])/6,
                  points[i+1][1] + (s*points[i][1] - s*points[i+2][1])/6)
            ops.append(('bcurveTo', b1[0], b1[1], b2[0], b2[1], points[i+1][0], points[i+1][1]))
            i += 1
        if close_point and len(close_point) == 2:
            ro = o['maxRandomnessOffset']
            ops.append(('lineTo', close_point[0] + _offset_opt(ro, o),
                                  close_point[1] + _offset_opt(ro, o)))
    elif n == 3:
        ops.append(('move', points[1][0], points[1][1]))
        ops.append(('bcurveTo', points[1][0], points[1][1], points[2][0], points[2][1],
                                points[2][0], points[2][1]))
    elif n == 2:
        ops += _line(points[0][0], points[0][1], points[1][0], points[1][1], o, True, True)
    return ops

def _compute_ellipse_points(inc, cx, cy, rx, ry, offset, overlap, o):  # renderer.ts L426-484
    core, allp = [], []
    if o['roughness'] == 0:
        inc = inc/4
        allp.append([cx + rx*math.cos(-inc), cy + ry*math.sin(-inc)])
        a = 0.0
        while a <= math.pi*2:
            p = [cx + rx*math.cos(a), cy + ry*math.sin(a)]; core.append(p); allp.append(p); a += inc
        allp.append([cx + rx, cy]); allp.append([cx + rx*math.cos(inc), cy + ry*math.sin(inc)])
    else:
        rad = _offset_opt(0.5, o) - math.pi/2                    # call
        p0x = _offset_opt(offset, o) + cx + 0.9*rx*math.cos(rad - inc)   # call (X first)
        p0y = _offset_opt(offset, o) + cy + 0.9*ry*math.sin(rad - inc)   # call (Y second)
        allp.append([p0x, p0y])
        end = math.pi*2 + rad - 0.01; a = rad
        while a < end:
            px = _offset_opt(offset, o) + cx + rx*math.cos(a)    # call (X first)
            py = _offset_opt(offset, o) + cy + ry*math.sin(a)    # call (Y second)
            p = [px, py]; core.append(p); allp.append(p); a += inc
        for (fx, fa) in ((1.0, math.pi*2 + overlap*0.5), (0.98, overlap), (0.9, overlap*0.5)):
            ex = _offset_opt(offset, o) + cx + fx*rx*math.cos(rad + fa)  # call (X first)
            ey = _offset_opt(offset, o) + cy + fx*ry*math.sin(rad + fa)  # call (Y second)
            allp.append([ex, ey])
    return allp, core

def generate_ellipse_params(w, h, o):                 # source: renderer.ts L97-107
    psq = math.sqrt(math.pi*2*math.sqrt((((w/2)**2 + (h/2)**2)/2)))
    step = math.ceil(max(o['curveStepCount'], (o['curveStepCount']/math.sqrt(200))*psq))
    inc = (math.pi*2)/step
    rx, ry = abs(w/2), abs(h/2); cfr = 1 - o['curveFitting']
    rx += _offset_opt(rx*cfr, o)                        # call
    ry += _offset_opt(ry*cfr, o)                        # call
    return {'increment': inc, 'rx': rx, 'ry': ry}

def ellipse_with_params(x, y, o, ep):                 # source: renderer.ts L109-121
    inner = _offset(0.4, 1, o)                          # call #1 (inner arg evaluated first)
    overlap = ep['increment'] * _offset(0.1, inner, o)  # call #2
    ap1, cp1 = _compute_ellipse_points(ep['increment'], x, y, ep['rx'], ep['ry'], 1, overlap, o)
    ops = _curve(ap1, None, o)
    if (not o['disableMultiStroke']) and o['roughness'] != 0:
        ap2, _ = _compute_ellipse_points(ep['increment'], x, y, ep['rx'], ep['ry'], 1.5, 0, o)
        ops = ops + _curve(ap2, None, o)
    return {'estimated_points': cp1, 'opset': {'type': 'path', 'ops': ops}}

def ellipse(x, y, w, h, o):                           # source: renderer.ts L92-95
    return ellipse_with_params(x, y, o, generate_ellipse_params(w, h, o))['opset']

# ---------------------------------------------------------------------------
# Hachure fill — port of hachure-fill/bin/hachure.js + scan-line-hachure.js
# ---------------------------------------------------------------------------
import functools as _functools

def _rotate_points(points, center, degrees):
    if not points:
        return
    cx, cy = center
    a = (math.pi / 180) * degrees
    cos_a, sin_a = math.cos(a), math.sin(a)
    for p in points:
        x, y = p[0], p[1]
        p[0] = (x - cx) * cos_a - (y - cy) * sin_a + cx
        p[1] = (x - cx) * sin_a + (y - cy) * cos_a + cy

def _rotate_lines(lines, center, degrees):
    pts = []
    for ln in lines:
        pts.extend(ln)
    _rotate_points(pts, center, degrees)

def _same_pt(p1, p2):
    return p1[0] == p2[0] and p1[1] == p2[1]

def _straight_hachure_lines(polygons, gap, step):
    vertex_array = []
    for polygon in polygons:
        v = [list(p) for p in polygon]
        if len(v) < 2: continue                     # guard: skip degenerate polygons
        if not _same_pt(v[0], v[-1]):
            v.append([v[0][0], v[0][1]])
        if len(v) > 2:
            vertex_array.append(v)
    lines = []
    gap = max(gap, 0.1)
    edges = []
    for v in vertex_array:
        for i in range(len(v) - 1):
            p1, p2 = v[i], v[i + 1]
            if p1[1] != p2[1]:
                ymin = min(p1[1], p2[1])
                edges.append({
                    "ymin": ymin, "ymax": max(p1[1], p2[1]),
                    "x": p1[0] if ymin == p1[1] else p2[0],
                    "islope": (p2[0] - p1[0]) / (p2[1] - p1[1]),
                })
    def _cmp(e1, e2):
        if e1["ymin"] != e2["ymin"]:
            return -1 if e1["ymin"] < e2["ymin"] else 1
        if e1["x"] != e2["x"]:
            return -1 if e1["x"] < e2["x"] else 1
        if e1["ymax"] == e2["ymax"]:
            return 0
        return -1 if e1["ymax"] < e2["ymax"] else 1
    edges.sort(key=_functools.cmp_to_key(_cmp))
    if not edges:
        return lines
    active = []
    y = edges[0]["ymin"]
    it = 0
    while active or edges:
        if edges:
            ix = -1
            for i in range(len(edges)):
                if edges[i]["ymin"] > y:
                    break
                ix = i
            removed = edges[:ix + 1]
            del edges[:ix + 1]
            for e in removed:
                active.append({"s": y, "edge": e})
        active = [ae for ae in active if ae["edge"]["ymax"] > y]
        active.sort(key=_functools.cmp_to_key(
            lambda a1, a2: 0 if a1["edge"]["x"] == a2["edge"]["x"]
            else (-1 if a1["edge"]["x"] < a2["edge"]["x"] else 1)))
        if step != 1 or (it % gap == 0):
            if len(active) > 1:
                for i in range(0, len(active), 2):
                    nexti = i + 1
                    if nexti >= len(active):
                        break
                    ce, ne = active[i]["edge"], active[nexti]["edge"]
                    lines.append([[round(ce["x"]), y], [round(ne["x"]), y]])
        y += step
        for ae in active:
            ae["edge"]["x"] = ae["edge"]["x"] + step * ae["edge"]["islope"]
        it += 1
    return lines

def _hachure_lines(polygons, hachure_gap, hachure_angle, step=1):
    angle = hachure_angle
    gap = max(hachure_gap, 0.1)
    plist = polygons
    center = [0, 0]
    if angle:
        for poly in plist:
            _rotate_points(poly, center, angle)
    lines = _straight_hachure_lines(plist, gap, step)
    if angle:
        for poly in plist:
            _rotate_points(poly, center, -angle)
        _rotate_lines(lines, center, -angle)
    return lines

def _polygon_hachure_lines(polygon_list, o):
    angle = o["hachureAngle"] + 90
    gap = o["hachureGap"]
    if gap < 0:
        gap = o["strokeWidth"] * 4
    gap = max(gap, 0.1)
    skip = 1
    if o["roughness"] >= 1:
        if random(o) > 0.7:      # RNG-LOAD-BEARING: exact position matches scan-line-hachure.js
            skip = gap
    return _hachure_lines([[list(p) for p in poly] for poly in polygon_list], gap, angle, skip or 1)

def hachure_fill_polygon(polygon_list, o):
    ops = []
    for line in _polygon_hachure_lines(polygon_list, o):
        ops.extend(_double_line(line[0][0], line[0][1], line[1][0], line[1][1], o, filling=True))
    return {"type": "fillSketch", "ops": ops}


def hatch_fill_polygon(polygon_list, o):
    s1 = hachure_fill_polygon(polygon_list, o)
    o2 = dict(o); o2["hachureAngle"] = o["hachureAngle"] + 90
    s2 = hachure_fill_polygon(polygon_list, o2)
    s1["ops"] = s1["ops"] + s2["ops"]
    return s1

def fill_polygon(polygon_list, o):
    style = o.get("fillStyle") or "hachure"
    if style == "solid":
        return solid_fill_polygon(polygon_list, o)
    if style == "cross-hatch":
        return hatch_fill_polygon(polygon_list, o)
    # hachure (default) and any not-yet-ported style fall back to hachure
    return hachure_fill_polygon(polygon_list, o)

def solid_fill_polygon(polygon_list, o):              # source: renderer.ts L196-211
    ops = []
    for points in polygon_list:
        if not points: continue
        offset = o['maxRandomnessOffset'] or 0
        if len(points) > 2:
            ops.append(('move', points[0][0] + _offset_opt(offset, o),   # X first
                                points[0][1] + _offset_opt(offset, o)))  # Y second
            for i in range(1, len(points)):
                ops.append(('lineTo', points[i][0] + _offset_opt(offset, o),
                                      points[i][1] + _offset_opt(offset, o)))
    return {'type': 'fillPath', 'ops': ops}


# ---------------------------------------------------------------------------
# Task 7b: curve + path (rounded shapes)
# ---------------------------------------------------------------------------

def clone_options_alter_seed(o):                      # source: renderer.ts L258-265
    """Return a shallow copy of o with seed+1 and randomizer cleared."""
    result = dict(o)
    result['randomizer'] = None        # clear so next random() seeds from seed+1
    result['seed'] = (o.get('seed') or 0) + 1
    return result


def _curve_with_offset(points, offset, o):            # source: renderer.ts L363-391
    """Add jitter around each point, then pass to _curve."""
    if not points:
        return []
    ps = []
    # Duplicate first point (jittered) twice for catmull-rom start tangent
    ps.append([points[0][0] + _offset_opt(offset, o),
               points[0][1] + _offset_opt(offset, o)])
    ps.append([points[0][0] + _offset_opt(offset, o),
               points[0][1] + _offset_opt(offset, o)])
    for i in range(1, len(points)):
        ps.append([points[i][0] + _offset_opt(offset, o),
                   points[i][1] + _offset_opt(offset, o)])
        if i == len(points) - 1:
            # Duplicate last point for end tangent
            ps.append([points[i][0] + _offset_opt(offset, o),
                       points[i][1] + _offset_opt(offset, o)])
    return _curve(ps, None, o)


def curve(input_points, o):                           # source: renderer.ts L56-88
    """Open curve through input_points (single point-list form only).

    Draws the curve twice (underlay + overlay) unless disableMultiStroke.
    Returns OpSet {'type':'path', 'ops':[...]}
    """
    if not input_points:
        return {'type': 'path', 'ops': []}
    pts = input_points                                # single list of [x,y]
    roughness = o['roughness']
    o1 = _curve_with_offset(pts, 1 * (1 + roughness * 0.2), o)
    if o['disableMultiStroke']:
        o2 = []
    else:
        o2 = _curve_with_offset(pts, 1.5 * (1 + roughness * 0.22),
                                 clone_options_alter_seed(o))
    return {'type': 'path', 'ops': o1 + o2}


def _bezier_to(x1, y1, x2, y2, x, y, current, o):   # source: renderer.ts L510-535
    """Rough bezier segment from current → (x,y) with ctrl pts (x1,y1),(x2,y2)."""
    ops = []
    ros = [o['maxRandomnessOffset'] or 1, (o['maxRandomnessOffset'] or 1) + 0.3]
    preserve = o['preserveVertices']
    iterations = 1 if o['disableMultiStroke'] else 2
    for i in range(iterations):
        if i == 0:
            ops.append(('move', current[0], current[1]))
        else:
            dx = 0 if preserve else _offset_opt(ros[0], o)
            dy = 0 if preserve else _offset_opt(ros[0], o)
            ops.append(('move', current[0] + dx, current[1] + dy))
        fx = x if preserve else x + _offset_opt(ros[i], o)
        fy = y if preserve else y + _offset_opt(ros[i], o)
        ops.append(('bcurveTo',
                    x1 + _offset_opt(ros[i], o), y1 + _offset_opt(ros[i], o),
                    x2 + _offset_opt(ros[i], o), y2 + _offset_opt(ros[i], o),
                    fx, fy))
    return ops


def _parse_path_d(d):                                 # stdlib SVG path mini-parser
    """Parse an SVG path d-string into a list of (command, *args) absolute segments.

    Supports M, L, Q, C, Z (upper-case only, as produced by Excalidraw).
    Q (quadratic) is converted to C (cubic) via degree elevation:
        P1 = start + 2/3*(Q-start), P2 = end + 2/3*(Q-end)
    so the returned segments are: ('M',x,y), ('L',x,y), ('C',x1,y1,x2,y2,x,y), ('Z',)
    """
    import re as _re
    # Tokenise: split on command letters, keeping the letter
    tokens = _re.split(r'([MLQCZmlqcz])', d.strip())
    segments = []
    current = [0.0, 0.0]
    first = [0.0, 0.0]
    i = 0
    while i < len(tokens):
        tok = tokens[i].strip()
        if not tok:
            i += 1; continue
        if tok in 'MLQCZmlqcz':
            cmd = tok.upper()
            i += 1
            # collect the numeric payload (may span the next token(s))
            num_str = tokens[i].strip() if i < len(tokens) else ''
            nums = [float(v) for v in _re.split(r'[\s,]+', num_str) if v]
            if cmd == 'M':
                x, y = nums[0], nums[1]
                current = [x, y]; first = [x, y]
                segments.append(('M', x, y))
            elif cmd == 'L':
                x, y = nums[0], nums[1]
                segments.append(('L', x, y))
                current = [x, y]
            elif cmd == 'Q':
                qx, qy, ex, ey = nums[0], nums[1], nums[2], nums[3]
                # Degree elevation Q→C
                x1 = current[0] + 2/3 * (qx - current[0])
                y1 = current[1] + 2/3 * (qy - current[1])
                x2 = ex + 2/3 * (qx - ex)
                y2 = ey + 2/3 * (qy - ey)
                segments.append(('C', x1, y1, x2, y2, ex, ey))
                current = [ex, ey]
            elif cmd == 'C':
                x1, y1, x2, y2, ex, ey = nums[0], nums[1], nums[2], nums[3], nums[4], nums[5]
                segments.append(('C', x1, y1, x2, y2, ex, ey))
                current = [ex, ey]
            elif cmd == 'Z':
                segments.append(('Z',))
                current = list(first)
        i += 1
    return segments


def path(d, o):                                       # source: renderer.ts svgPath L163-196
    """Render an SVG path d-string using rough ops.

    Approach: faithful port of rough's svgPath. Parses M/L/Q/C/Z (Q→C via
    degree elevation). Uses _double_line for L/Z, _bezier_to for C.
    No external dependencies — stdlib only.
    """
    segs = _parse_path_d(d)
    ops = []
    current = [0.0, 0.0]
    first = [0.0, 0.0]
    for seg in segs:
        cmd = seg[0]
        if cmd == 'M':
            current = [seg[1], seg[2]]
            first = [seg[1], seg[2]]
        elif cmd == 'L':
            ops += _double_line(current[0], current[1], seg[1], seg[2], o)
            current = [seg[1], seg[2]]
        elif cmd == 'C':
            x1, y1, x2, y2, x, y = seg[1], seg[2], seg[3], seg[4], seg[5], seg[6]
            ops += _bezier_to(x1, y1, x2, y2, x, y, current, o)
            current = [x, y]
        elif cmd == 'Z':
            ops += _double_line(current[0], current[1], first[0], first[1], o)
            current = list(first)
    return {'type': 'path', 'ops': ops}
