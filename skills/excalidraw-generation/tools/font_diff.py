"""Pure metrics for the .excalidraw font-render error detector.

The exporter (resvg) and excalidraw.com (WebKit) anti-alias hand-drawn glyphs
1-2px differently at every edge, so a naive per-pixel RGB threshold drowns real
font bugs in AA wobble. These metrics instead aggregate an INK-INTENSITY MAP over a
text element's pixel bounding box: AA smears ink across more pixels but keeps the
total roughly constant, so aggregation sees through the wobble and only fires on
real failures — missing glyphs, the usvg whole-chunk poison, a wrong fallback font
(bolder/thinner), or displaced text.

The ink map is darkness-over-white (:func:`ink_from_rgba`), NOT the raw alpha
channel: our export and the excalidraw.com assets may differ in background (opaque
white vs transparent), and only compositing both over white makes their text ink
comparable. Higher value = more ink.

All metric functions are pure (numpy arrays + plain tuples in, floats out) so the
whole detector is unit-testable without rendering. The thin corpus driver lives in
the (untracked-history-wise) ``diff_detect.py`` and imports from here.

Box convention everywhere: ``(x0, y0, x1, y1)`` in pixel coordinates, half-open
(rows ``y0:y1``, cols ``x0:x1``), matching numpy slicing.
"""
import math

import numpy as np


def ink_from_rgba(rgba):
    """Background-invariant ink map from an RGBA array: darkness composited over white.

    Composites *rgba* over an opaque white background, then returns ``255 - luma``
    so 0 = white/blank and 255 = solid black ink. This makes a transparent-background
    asset and an opaque-white render directly comparable — the whole reason the raw
    alpha channel fails as an ink signal. Input: ``(H, W, 4)`` array; output: ``(H, W)``.
    """
    a = np.asarray(rgba, dtype=np.float64)
    al = a[:, :, 3:4] / 255.0
    over_white = a[:, :, :3] * al + 255.0 * (1.0 - al)
    return 255.0 - over_white.mean(axis=2)


def is_transparent(rgba, min_fraction=0.05, alpha_thresh=250):
    """True if an RGBA image has a meaningful transparent region (not an opaque canvas).

    Used by the driver to render OUR export on the SAME background as the asset (so the
    A/B page shows both on one ground) — it does NOT affect any metric (ink_from_rgba
    composites over white either way). ``(H, W, 4)`` in; True if >``min_fraction`` of
    pixels are below ``alpha_thresh``.
    """
    a = np.asarray(rgba)[:, :, 3]
    return bool((a < alpha_thresh).mean() > min_fraction)


def gaussian_blur(m, sigma):
    """Separable Gaussian blur of a 2D array (numpy-only, no scipy/PIL).

    Dampens the high-frequency edge jitter that makes resvg-vs-WebKit hand-drawn
    text look different at 1x, so projection_correlation compares glyph *structure*
    rather than per-edge AA noise. sigma<=0 returns the input unchanged. Uses roll-
    based convolution with a unit-sum kernel → total ink is conserved exactly; the
    circular wrap is negligible because text ink maps have an empty border.
    """
    if sigma <= 0:
        return m
    r = max(1, int(round(3 * sigma)))
    x = np.arange(-r, r + 1)
    k = np.exp(-(x ** 2) / (2.0 * sigma ** 2))
    k /= k.sum()
    out = np.zeros_like(m, dtype=np.float64)
    for i, w in enumerate(k):                       # blur along rows
        out += w * np.roll(m, i - r, axis=0)
    m2, out = out, np.zeros_like(out)
    for i, w in enumerate(k):                       # blur along cols
        out += w * np.roll(m2, i - r, axis=1)
    return out


def ink_balance(alpha_ours, alpha_orig, box):
    """Ratio of total ink (sum of alpha) inside *box*: ours / orig.

    ``1.0`` means equal ink; ``< 1`` means ours is missing ink (dropped glyph /
    poison / tofu), ``> 1`` means ours has excess ink (a bolder wrong fallback).
    Robust to anti-aliasing because it sums alpha rather than counting edges.

    When the original has no ink in the box: returns ``1.0`` if ours is also
    empty (nothing to compare), else ``inf`` (ink appeared where none belongs).
    """
    x0, y0, x1, y1 = box
    s_ours = float(alpha_ours[y0:y1, x0:x1].sum())
    s_orig = float(alpha_orig[y0:y1, x0:x1].sum())
    if s_orig == 0.0:
        return 1.0 if s_ours == 0.0 else float("inf")
    return s_ours / s_orig


def _ncc(a, b):
    """Normalized cross-correlation of two equal-length 1D profiles, in [-1, 1].

    Scale-invariant (mean-centred, unit-normed), so a uniformly thinner/bolder
    glyph of the SAME shape still scores 1.0 — that difference is ink_balance's
    job, not shape's. Degenerate (zero-variance) cases: both flat → 1.0 (same
    lack of structure), exactly one flat → 0.0 (no shared structure).
    """
    a = a - a.mean()
    b = b - b.mean()
    na = float(np.sqrt((a * a).sum()))
    nb = float(np.sqrt((b * b).sum()))
    if na == 0.0 and nb == 0.0:
        return 1.0
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float((a * b).sum() / (na * nb))


def _ncc_best_shift(a, b, k):
    """Max NCC of *a* vs *b* over integer shifts in [-k, k], on the overlap.

    Absorbs the 1-2px sub-pixel offset between resvg and WebKit rasterisers so a
    correctly-rendered-but-slightly-shifted line still scores ~1.0, while a
    genuinely different shape (missing/wrong glyph) cannot be rescued by any
    shift and stays low.
    """
    n = len(a)
    best = -1.0
    for d in range(-k, k + 1):
        if d == 0:
            av, bv = a, b
        elif d > 0:
            av, bv = a[d:], b[:n - d]
        else:
            av, bv = a[:d], b[-d:]
        if len(av) == 0:
            continue
        best = max(best, _ncc(av, bv))
    return best


def projection_correlation(alpha_ours, alpha_orig, box, shift=2):
    """Shape agreement of the text line inside *box*, in [0, 1] (higher = better).

    Compares the 1D ink-projection signatures — column profile (ink summed over
    rows) and row profile (ink summed over cols) — of ours vs orig, each with
    ±*shift* px tolerance, and returns the WORSE axis. AA-blind (aggregated
    projections), but sharp on missing glyphs (gap in the column profile),
    wrong-shape fallbacks (different profile), and displacement beyond *shift*.
    """
    x0, y0, x1, y1 = box
    so = alpha_ours[y0:y1, x0:x1]
    sr = alpha_orig[y0:y1, x0:x1]
    col = _ncc_best_shift(so.sum(axis=0), sr.sum(axis=0), shift)
    row = _ncc_best_shift(so.sum(axis=1), sr.sum(axis=1), shift)
    return min(col, row)


def _centroid(sub):
    """Alpha-weighted (cx, cy) of *sub* in its local coords, or None if no ink."""
    s = float(sub.sum())
    if s == 0.0:
        return None
    ys, xs = np.indices(sub.shape)
    return float((xs * sub).sum() / s), float((ys * sub).sum() / s)


def centroid_shift(alpha_ours, alpha_orig, box):
    """Euclidean distance (px) between ours' and orig's ink centroid inside *box*.

    Catches text that renders in the right box but at the wrong position. If
    either side has no ink the shift is undefined — return ``0.0`` and let
    :func:`ink_balance` own that case.
    """
    x0, y0, x1, y1 = box
    co = _centroid(alpha_ours[y0:y1, x0:x1])
    cr = _centroid(alpha_orig[y0:y1, x0:x1])
    if co is None or cr is None:
        return 0.0
    return float(((co[0] - cr[0]) ** 2 + (co[1] - cr[1]) ** 2) ** 0.5)


def classify_verdict(ink, corr, shift_px, *,
                     ink_lo=0.6, ink_hi=1.6, corr_min=0.85, shift_max=3.0):
    """Reduce the three metrics of one text element to a single verdict string.

    Returns one of ``OK``, ``INK_LOSS``, ``INK_GAIN``, ``SHAPE_MISMATCH``,
    ``DISPLACED``. Checked in that priority order: an ink deficit/excess is a
    coarser, more actionable diagnosis than a shape difference (a poisoned chunk
    trips both, but "text missing" is what you want to read), and displacement
    is only meaningful once ink and shape are otherwise fine.

    Thresholds are keyword args so the corpus driver can calibrate them against
    the known-clean baseline.
    """
    if ink < ink_lo:
        return "INK_LOSS"
    if ink > ink_hi:
        return "INK_GAIN"
    if corr < corr_min:
        return "SHAPE_MISMATCH"
    if shift_px > shift_max:
        return "DISPLACED"
    return "OK"


def text_pixel_boxes(doc, options, layout=None):
    """Pixel bounding box of every visible text element in *doc*.

    Returns a list of ``{"id", "text", "box": (x0, y0, x1, y1)}``. The scene→pixel
    transform is ``px = (scene + off) * scale`` using :func:`excalidraw_svg.scene_layout`
    (shared with the renderer, so boxes land exactly on the exported PNG). Bound-text
    position is resolved through the SAME helpers to_svg uses — container-bound text is
    placed from the container geometry, so a stale stored ``x/y`` never leaks in.

    Boxes are clamped to the image; degenerate/empty ones are dropped. The
    excalidraw_svg import is lazy so the pure metrics above stay dependency-free.
    """
    import excalidraw_svg  # noqa: PLC0415 — lazy: keep the metric core numpy-only

    if layout is None:
        layout = excalidraw_svg.scene_layout(doc, options)
    s, ox, oy = layout.scale, layout.off_x, layout.off_y
    w_px = int(round(layout.width * s))
    h_px = int(round(layout.height * s))

    boxes = []
    for el in doc["elements"]:
        if el.get("isDeleted") or el.get("type") != "text":
            continue
        cid = el.get("containerId")
        container = layout.by_id.get(cid) if cid else None
        if container is not None and container["type"] in ("rectangle", "ellipse", "diamond"):
            bx, by = excalidraw_svg._get_bound_text_position(container, el)
        elif container is not None and container["type"] in ("arrow", "line"):
            bx, by = excalidraw_svg._get_arrow_label_position(container, el)
        else:
            bx, by = el["x"], el["y"]
        w, h = el["width"], el["height"]
        x0 = max(0, min(w_px, int(math.floor((bx + ox) * s))))
        y0 = max(0, min(h_px, int(math.floor((by + oy) * s))))
        x1 = max(0, min(w_px, int(math.ceil((bx + w + ox) * s))))
        y1 = max(0, min(h_px, int(math.ceil((by + h + oy) * s))))
        if x1 <= x0 or y1 <= y0:
            continue
        boxes.append({"id": el["id"], "text": el.get("text", ""), "box": (x0, y0, x1, y1)})
    return boxes


def _shift2d(a, dy, dx, fill=0):
    """Shift a 2D array by (dy, dx), filling the exposed border with *fill*."""
    out = np.full_like(a, fill)
    h, w = a.shape
    ys, yd = slice(max(0, -dy), h - max(0, dy)), slice(max(0, dy), h - max(0, -dy))
    xs, xd = slice(max(0, -dx), w - max(0, dx)), slice(max(0, dx), w - max(0, -dx))
    out[yd, xd] = a[ys, xs]
    return out


def aa_tolerant_diff(alpha_ours, alpha_orig, thresh=24, radius=1):
    """Boolean mask of pixels that differ beyond *thresh* AFTER shift tolerance.

    For each pixel the difference is the MINIMUM of ``|ours - orig_shifted|`` over a
    ``(2*radius+1)²`` neighbourhood, so a 1-2px sub-pixel offset between the resvg and
    WebKit rasterisers finds a match nearby and does not register — only genuine
    changes (a fill/arrowhead present in one and not the other) survive. Used for the
    NON-text regions; text regions are judged by the aggregate metrics instead.
    """
    o = alpha_ours.astype(np.int32)
    r = alpha_orig.astype(np.int32)
    best = np.full(o.shape, 1 << 30, dtype=np.int32)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            best = np.minimum(best, np.abs(o - _shift2d(r, dy, dx, fill=0)))
    return best > thresh


def analyze_text_elements(doc, options, ink_ours, ink_orig, layout=None,
                          blur_sigma=1.0, **thresholds):
    """Full per-text-element analysis: box + three metrics + verdict.

    For each visible text element, measures :func:`ink_balance`,
    :func:`projection_correlation` and :func:`centroid_shift` over its pixel box and
    reduces them to a :func:`classify_verdict` label. ``thresholds`` are forwarded to
    classify_verdict (``ink_lo``, ``ink_hi``, ``corr_min``, ``shift_max``) so the
    corpus driver can calibrate. Returns a list of dicts with keys ``id, text, box,
    ink, corr, shift, verdict``. This is the orchestration the corpus driver calls;
    the driver itself only renders and reports.

    ``blur_sigma`` (>0) Gaussian-blurs the maps ONLY for the projection correlation,
    dampening 1x hand-drawn AA jitter so corr compares glyph structure rather than
    edge noise (measured to lift correct-render corr from ~0.51 to ~0.72, so a higher
    corr_min catches more real wrong-font swaps). ink and shift stay on the raw maps.
    """
    corr_ours = gaussian_blur(ink_ours, blur_sigma) if blur_sigma else ink_ours
    corr_orig = gaussian_blur(ink_orig, blur_sigma) if blur_sigma else ink_orig
    results = []
    for b in text_pixel_boxes(doc, options, layout):
        box = b["box"]
        ink = ink_balance(ink_ours, ink_orig, box)
        corr = projection_correlation(corr_ours, corr_orig, box)
        shift = centroid_shift(ink_ours, ink_orig, box)
        results.append({
            **b,
            "ink": ink,
            "corr": corr,
            "shift": shift,
            "verdict": classify_verdict(ink, corr, shift, **thresholds),
        })
    return results
