# excalidraw_helpers.py
"""
Layout helpers — emit core Excalidraw elements by calling toolkit constructors.

All helpers accept a `prefix` argument; element ids are derived from it
(e.g. f"{prefix}-{i}") so the caller controls uniqueness across a diagram.
"""
from excalidraw_toolkit import rect, label, text, line, ellipse


def flow_row(prefix, labels, *, x=80, y=100, w=160, h=80, gap=100,
             fill="transparent", stroke="#1e1e1e"):
    """N boxes left-to-right with bound labels.

    Returns a flat list of rectangle + text elements.
    """
    els = []
    cx = x
    for i, lab in enumerate(labels):
        box = rect(f"{prefix}-{i}", cx, y, w, h, fill=fill, stroke=stroke)
        els.append(box)
        els.append(label(f"{prefix}-{i}-t", box, lab))
        cx += w + gap
    return els


def grid(prefix, rows, cols, *, x=60, y=60, cell_w=200, cell_h=120, gap=20):
    """Return a {(r, c): (cx, cy)} dict of cell-center coordinates.

    No elements are emitted — the caller places elements at the returned centers.
    The prefix argument is reserved for caller namespacing conventions.
    """
    centers = {}
    for r in range(rows):
        for c in range(cols):
            cx = x + c * (cell_w + gap) + cell_w / 2
            cy = y + r * (cell_h + gap) + cell_h / 2
            centers[(r, c)] = (cx, cy)
    return centers


def columns(prefix, col_specs, *, x=60, y=60, col_w=220, col_gap=190,
            row_h=60, row_gap=20):
    """Multi-column layout: header + stacked labelled rows per column.

    `col_specs` is a list of (header_text, [row_label, ...]) tuples.
    Returns a flat list of rectangle + text elements.
    """
    els = []
    cx = x
    for ci, (header, rows) in enumerate(col_specs):
        hbox = rect(f"{prefix}-c{ci}-h", cx, y, col_w, row_h, fill="#343a40")
        els += [hbox, label(f"{prefix}-c{ci}-h-t", hbox, header, color="#ffffff")]
        ry = y + row_h + row_gap
        for ri, lab in enumerate(rows):
            box = rect(f"{prefix}-c{ci}-r{ri}", cx, ry, col_w, row_h)
            els += [box, label(f"{prefix}-c{ci}-r{ri}-t", box, lab)]
            ry += row_h + row_gap
        cx += col_w + col_gap
    return els


def panel(prefix, *, title, rows, x=40, y=40, w=440, fill="#f8f9fa",
          accent="#868e96", row_fill="#ffffff", title_h=44, row_h=56,
          row_gap=18, pad=20):
    """Enclosing card + title text + N stacked bound-text row boxes.

    Element 0 is the card (`{prefix}-panel`) — use as a connect handle.
    """
    n = len(rows)
    h = title_h + pad + n * row_h + (n - 1) * row_gap + pad
    p = rect(f"{prefix}-panel", x, y, w, h, fill=fill, stroke=accent)
    els = [
        p,
        text(f"{prefix}-title", x + pad, y + 12, w - 2 * pad, 28,
             title, align="left"),
    ]
    ry = y + title_h + pad
    for i, row in enumerate(rows):
        box = rect(f"{prefix}-r{i}", x + pad, ry, w - 2 * pad, row_h,
                   fill=row_fill, stroke=accent)
        els += [box, label(f"{prefix}-r{i}-t", box, row)]
        ry += row_h + row_gap
    return els


def timeline(prefix, points, *, x=80, y=200, gap=160):
    """Horizontal timeline: baseline + dot + top/optional bottom label per point.

    `points` is a list of (top_label,) or (top_label, bottom_label) tuples.
    Returns a flat list of line, ellipse, and text elements.
    """
    els = [line(f"{prefix}-axis", [[x - 40, y], [x + gap * len(points), y]])]
    for i, pt in enumerate(points):
        px = x + i * gap
        els.append(ellipse(f"{prefix}-dot{i}", px - 6, y - 6, 12, 12,
                           fill="#1e1e1e"))
        els.append(text(f"{prefix}-top{i}", px - 60, y - 40, 120, 24, pt[0]))
        if len(pt) > 1:
            els.append(text(f"{prefix}-bot{i}", px - 60, y + 16, 120, 24,
                            pt[1]))
    return els


def axes(prefix, *, ox=100, oy=340, width=500, height=300):
    """X and Y axis lines meeting at origin (ox, oy).

    Returns a list of two line elements.
    """
    return [
        line(f"{prefix}-x", [[ox, oy], [ox + width, oy]]),
        line(f"{prefix}-y", [[ox, oy], [ox, oy - height]]),
    ]


def bars(prefix, data, *, ox=100, oy=340, bar_w=60, gap=40, scale=2.0,
         fill="#b2f2bb", stroke="#2f9e44"):
    """Bar chart: one filled rect + label per (label, value) pair.

    Bar height = value * scale. Returns a flat list of rect and text elements.
    """
    els = []
    bx = ox + gap
    for i, (lab, value) in enumerate(data):
        h = value * scale
        els.append(rect(f"{prefix}-bar{i}", bx, oy - h, bar_w, h,
                        fill=fill, stroke=stroke))
        els.append(text(f"{prefix}-lab{i}", bx - gap / 2, oy + 8, bar_w + gap, 20, lab))
        bx += bar_w + gap
    return els


def curve(prefix, fn, t0, t1, *, n=60, ox=100, oy=340, sx=15, sy=3,
          stroke="#e03131"):
    """Deterministic function curve: evaluates fn at n+1 evenly-spaced t values.

    Pixel mapping: x = ox + (t - t0) * sx, y = oy - fn(t) * sy.
    Returns a list containing one multi-point curved line element.
    """
    pts = []
    for i in range(n + 1):
        t = t0 + (t1 - t0) * i / n
        pts.append([ox + (t - t0) * sx, oy - fn(t) * sy])
    return [line(f"{prefix}-curve", pts, stroke=stroke, curved=True)]


def histogram(prefix, values, *, ox=100, oy=340, bar_w=40, gap=10, scale=2.0):
    """Histogram: one rect per value, no labels.

    Bar height = value * scale. Returns a flat list of rect elements.
    """
    els = []
    bx = ox
    for i, v in enumerate(values):
        h = v * scale
        els.append(rect(f"{prefix}-h{i}", bx, oy - h, bar_w, h,
                        fill="#dee2e6", stroke="#868e96"))
        bx += bar_w + gap
    return els
