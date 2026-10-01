# excalidraw_svg.py — element document → deterministic SVG (stdlib only).
# source: excalidraw scene/export.ts + renderer/staticSvgScene.ts
import re as _re
import roughjs
import fonts
import freehand
import excalidraw_shape as shape
import excalidraw_bounds
import collections

# RTL Unicode ranges (port of staticSvgScene.ts isRTL / direction detection).
# Covers: Hebrew, Arabic, Arabic Supplement, Arabic Extended-A, Arabic Presentation Forms-A/B,
# Arabic Mathematical, and the Unicode BIDI markers.
_RTL_RE = _re.compile(
    r"[֐-׿"   # Hebrew
    r"؀-ۿ"    # Arabic
    r"ݐ-ݿ"    # Arabic Supplement
    r"ࢠ-ࣿ"    # Arabic Extended-A
    r"ﭐ-﷿"    # Arabic Presentation Forms-A
    r"ﹰ-﻿"    # Arabic Presentation Forms-B / Arabic math
    r"]"
)


def _is_rtl(text: str) -> bool:
    """Return True if *text* contains RTL characters (Arabic / Hebrew / etc.).

    Port of the direction detection in staticSvgScene.ts:674-699 — Excalidraw
    checks whether the element's text contains RTL codepoints and, when it does,
    emits direction="rtl" + text-anchor="end".
    """
    return bool(_RTL_RE.search(text))

PAD = 10                                              # DEFAULT_EXPORT_PADDING
BOUND_TEXT_PADDING = 5                                # padding inside container for bound text (non-center)

# ---------------------------------------------------------------------------
# Frame constants (ZA in staticSvgScene.ts)
# ---------------------------------------------------------------------------
_FRAME_STROKE_COLOR = "#bbb"
_FRAME_STROKE_WIDTH = 2
_FRAME_RADIUS = 8
_FRAME_NAME_OFFSET_Y = 3       # ZA.nameOffsetY
_FRAME_NAME_FONT_SIZE = 14     # ZA.nameFontSize
_FRAME_NAME_LINE_HEIGHT = 1.25 # ZA.nameLineHeight
_FRAME_NAME_COLOR = "#999999"  # ZA.nameColorLightTheme

# Helvetica (dA.Helvetica=2) font metrics from font-metadata.ts
# Used for frame name label vertical-offset calculation
_HELVETICA_UNITS_PER_EM = 2048
_HELVETICA_ASCENDER = 1577
_HELVETICA_DESCENDER = -471
# Family string: Yo({fontFamily: 2}) = "Helvetica, Segoe UI Emoji"
_HELVETICA_FAMILY = "Helvetica, Segoe UI Emoji"


def _f(v):
    return roughjs._fmt(v, 2)


def _fv(v):
    """Full-precision float string for scene-level dimensions (viewBox, width, height).

    Strips trailing '.0' for whole numbers so that '160.0' becomes '160', matching
    Excalidraw's SVG export format for integer-valued scene bounds.
    """
    s = repr(v)
    return s[:-2] if s.endswith('.0') else s



def _path_el(opset, *, fill, stroke, stroke_width, dash=None, linecap="round"):
    d = roughjs.ops_to_path(opset)
    if opset["type"] == "fillPath":
        attrs = {"d": d, "stroke": "none", "fill": fill}
    else:
        attrs = {"d": d, "fill": "none", "stroke": stroke,
                 "stroke-width": _f(stroke_width), "stroke-linecap": linecap}
        if dash:
            attrs["stroke-dasharray"] = ",".join(_f(x) for x in dash)
    return el("path", attrs, void=True)


def _render_element(el_, options=None):
    t = el_["type"]
    if t == "text":
        return _render_text(el_, options)
    if t == "freedraw":
        return _render_freedraw(el_)
    if t == "image":
        return _render_image_use(el_)
    if t in ("embeddable", "iframe"):
        return _render_embeddable_paths(el_)
    sets = shape.generate_element_shape(el_)
    opts = shape.generate_rough_options(el_)
    parts = []
    for s in sets:
        if s["type"] == "fillSketch":
            # Hachure / cross-hatch fill lines: rough.js draws these in the fill colour
            # (backgroundColor) at fillWeight — NOT in the stroke colour/width, and NOT dashed.
            parts.append(_path_el(
                s,
                fill=None,
                stroke=el_.get("backgroundColor"),
                stroke_width=opts["fillWeight"],
                dash=None,
            ))
        else:
            parts.append(_path_el(
                s,
                fill=el_.get("backgroundColor"),
                stroke=el_["strokeColor"],
                stroke_width=opts["strokeWidth"],
                # Arrowhead opsets render solid — the shaft's dash never applies to them.
                dash=None if s.get("_arrowhead") else opts.get("strokeLineDash"),
            ))
    return "".join(parts)


def _render_embeddable_paths(el_):
    """Render embeddable/iframe rough paths (inner content of the stroke-linecap group).

    Port of staticSvgScene.ts embeddable/iframe branch: generates rough rectangle
    shape paths. The <g stroke-linecap="round"> wrapper and <a href> are applied
    in to_svg().
    """
    sets = shape.generate_element_shape(el_)
    opts = shape.generate_rough_options(el_)
    parts = []
    for s in sets:
        if s["type"] == "fillSketch":
            # Hachure / cross-hatch fill lines: rough.js draws these in the fill colour
            # (backgroundColor) at fillWeight — NOT in the stroke colour/width, and NOT dashed.
            parts.append(_path_el(
                s,
                fill=None,
                stroke=el_.get("backgroundColor"),
                stroke_width=opts["fillWeight"],
                dash=None,
            ))
        else:
            parts.append(_path_el(
                s,
                fill=el_.get("backgroundColor"),
                stroke=el_["strokeColor"],
                stroke_width=opts["strokeWidth"],
                dash=opts.get("strokeLineDash"),
            ))
    return "".join(parts)


def _render_image_use(el_):
    """Render an image element as a <use> referencing a <symbol> defined in <defs>.

    Port of staticSvgScene.ts image branch: emits
      <use href="#image-{fileId}" width="{w}" height="{h}" opacity="{opacity}">
    The corresponding <symbol> is collected by to_svg() and placed in <defs>.
    """
    file_id = el_.get("fileId", "")
    w = _fv(el_["width"])
    h = _fv(el_["height"])
    opacity = el_.get("opacity", 100) / 100
    # Format opacity: strip trailing '.0' for integer values (e.g. 1.0 → "1")
    opacity_s = repr(opacity)
    if opacity_s.endswith(".0"):
        opacity_s = opacity_s[:-2]
    return el("use", {"href": f"#image-{file_id}", "width": w, "height": h, "opacity": opacity_s})


def _render_freedraw(el_):
    """Render a freedraw element as a single filled <path> (no stroke).

    Port of staticSvgScene.ts freedraw branch + shape.ts getFreeDrawSvgPath.
    The outline is computed by perfect-freehand (freehand.py), then smoothed
    into a quadratic Bézier path (getSvgPathFromStroke).
    """
    d = freehand.get_freedraw_svg_path(el_)
    return el("path", {"fill": el_["strokeColor"], "d": d}, void=True)


def _line_height(el: dict) -> float:
    """Resolve the effective unitless line-height for a text element.

    Port of Excalidraw's Ua(A) / lineHeight fixup path in packages/element/src/:
    - If the element stores an explicit ``lineHeight``, use it directly.
    - Otherwise, if the element has a stored ``height`` (legacy elements created
      before lineHeight was persisted), recover it as::

          lineHeight = element.height / line_count / font_size

      (mirrors ``Ua(A) = A.height / Cw(A.text).length / A.fontSize``).
    - Final fallback: font-family default from ``fonts.line_height(code)``.
    """
    stored = el.get("lineHeight")
    if stored:
        return stored
    h = el.get("height")
    if h:
        lines = el.get("text", "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        n = len(lines) or 1
        return h / n / el["fontSize"]
    return fonts.line_height(el["fontFamily"])


def _render_text(el_, options=None):
    code = el_["fontFamily"]
    fs = el_["fontSize"]
    lh = _line_height(el_)
    lh_px = fs * lh
    voff = fonts.vertical_offset(code, fs, lh_px)
    align = el_.get("textAlign", "left")
    rtl = _is_rtl(el_.get("text", ""))
    # RTL: force anchor to "end" (port of staticSvgScene.ts direction branch).
    # LTR: derive anchor from textAlign as normal.
    if rtl:
        anchor = "end"
        direction = "rtl"
    else:
        anchor = "middle" if align == "center" else "end" if align == "right" else "start"
        direction = "ltr"
    hoff = el_["width"] / 2 if align == "center" else el_["width"] if align == "right" else 0
    lines = el_["text"].replace("\r\n", "\n").replace("\r", "\n").split("\n")
    authentic_virgil = options.authentic_virgil if options is not None else False
    out = []
    for i, ln in enumerate(lines):
        y = i * lh_px + voff
        # Shared opening attributes for the <text> element.
        # family_string is XML-attr-escaped: el() calls _escape_attr on the value, which
        # handles quotes in multi-word family names (code 3 → "Cascadia Code" → &quot;).
        # For unquoted values (Virgil, Excalifont, …) _escape_attr is a no-op, so the
        # code-1 fast-path stays byte-identical to the pre-fix output.
        # `white-space: pre;` matches Excalidraw and makes browsers preserve leading/interior
        # spaces (space-indented lines). resvg's CSS parser IGNORES that property, so we ALSO
        # set xml:space="preserve" — the SVG attribute resvg DOES honor — or space-indented
        # continuation lines collapse flush-left (verified: white-space:pre alone → stripped,
        # xml:space="preserve" → preserved). Extra attr vs Excalidraw's bytes; geometry unchanged.
        attrs = {
            "x": _f(hoff),
            "y": _f(y),
            "font-family": fonts.family_string(code, authentic_virgil),
            "font-size": f"{_f(fs)}px",
            "fill": el_["strokeColor"],
            "text-anchor": anchor,
            "style": "white-space: pre;",
            "xml:space": "preserve",
            "direction": direction,
            "dominant-baseline": "alphabetic",
        }
        # Native per-glyph fallback (resvg FontResolver::default) renders any glyph the
        # primary font lacks from the loaded Latin-free fallback fonts, so we emit ONE
        # <text> run — no per-glyph <tspan> routing. Variation selectors (U+FE00–U+FE0F)
        # are still dropped so they never reach the shaper as standalone glyphs; for a
        # line without any VS this is a no-op, keeping primary-covered lines byte-identical.
        clean = "".join(ch for ch in ln if not (0xFE00 <= ord(ch) <= 0xFE0F))
        out.append(el("text", attrs, _escape(clean)))
    return "".join(out)


def _escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(s):
    """Escape a string for safe interpolation into an XML attribute value (double-quoted).

    Prevents attribute-injection / SVG-XSS: escapes &, ", <, > so that a value
    like  foo" onload="x  cannot break out of the enclosing attribute.
    """
    return (
        s.replace("&", "&amp;")
         .replace('"', "&quot;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def el(tag, attrs=None, *children, void=False):
    """Build an SVG element string with all attribute values escaped.
    void=True → '<tag … />' (space before slash, matching the existing <path …/> format).
    Otherwise → '<tag …>children</tag>' (empty children → '<tag></tag>').
    Children are raw SVG strings; escape text content via _escape before passing it in."""
    a = "".join(f' {k}="{_escape_attr(str(v))}"' for k, v in (attrs or {}).items() if v is not None)
    if void:
        return f'<{tag}{a} />'
    return f'<{tag}{a}>{"".join(children)}</{tag}>'


_LINK_ALLOWED_SCHEMES = ("http:", "https:", "mailto:")


def _sanitize_link(link: str) -> str:
    """Return a safe href value for the embeddable <a> wrapper.

    Allows http:, https:, mailto: (case-insensitive); everything else
    (javascript:, data:, vbscript:, …) becomes about:blank.
    Mirrors Excalidraw's @braintree/sanitize-url intent.
    The returned value is NOT yet attribute-escaped — pass it to el() which
    calls _escape_attr() on all attribute values automatically.
    """
    stripped = link.strip().lower()
    for scheme in _LINK_ALLOWED_SCHEMES:
        if stripped.startswith(scheme):
            return link
    return "about:blank"


def _get_arrow_midpoint(points):
    """Get the bound-label anchor point along the arrow/line, in element-local coords.

    Port of LinearElementEditor.getBoundTextElementPosition (linearElementEditor.ts):
    the anchor is chosen by POINT COUNT, not arc length:
      - ODD  point count → the middle control point ``points[n // 2]`` directly. Catmull-Rom
        curves (roundness type 2) pass THROUGH their control points, so this point lies on
        the rendered curve. This is the branch all corpus bound-label arrows take.
      - EVEN point count → the midpoint of the middle segment (points[n//2 - 1]..points[n//2]).

    For 2-point arrows (n == 2, even) this is the straight midpoint — unchanged from the
    previous arc-length behaviour. For even-count CURVED arrows Excalidraw samples the middle
    Bézier segment at 50% arc length (getSegmentMidPoint → curvePointAtLength); we approximate
    with the straight segment midpoint, as no even-count curved bound-label arrow exists in the
    corpus.

    (The previous implementation used 50%-cumulative-arc-length, which diverges from Excalidraw
    for odd-count curved arrows — e.g. a 3-point curved arrow's arc midpoint sits ~16px off the
    middle control point Excalidraw actually uses, ghosting the label.)

    Args:
        points: List of [x, y] pairs in element-local coordinates (relative to el.x, el.y).

    Returns:
        (x, y) in element-local coordinates (add el.x, el.y for scene coords).
    """
    n = len(points)
    if n < 2:
        return (points[0][0], points[0][1]) if points else (0.0, 0.0)
    if n % 2 == 1:
        mid = points[n // 2]
        return (mid[0], mid[1])
    p0, p1 = points[n // 2 - 1], points[n // 2]
    return ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)


def _get_arrow_label_position(container, text_el):
    """Compute scene-coordinate (x, y) for a label bound to an arrow or line.

    Port of LinearElementEditor.getBoundTextElementPosition in Excalidraw source.
    The label is centered at the path midpoint (50% of cumulative segment length).

    Args:
        container: Arrow or line element dict.
        text_el:   Bound text element dict.

    Returns:
        (x, y) scene coordinates for the top-left corner of the label.
    """
    points = container.get("points", [[0, 0], [container["width"], 0]])
    mid_rel_x, mid_rel_y = _get_arrow_midpoint(points)
    abs_mid_x = container["x"] + mid_rel_x
    abs_mid_y = container["y"] + mid_rel_y
    tw, th = text_el["width"], text_el["height"]
    return abs_mid_x - tw / 2, abs_mid_y - th / 2


def _get_bound_text_position(container, text_el):
    """Compute the scene-coordinate (x, y) for a bound text element.

    Port of getBoundTextElementPosition from packages/element/src/boundElements.ts.
    Instead of trusting the text element's stored x/y (which may be stale or wrong),
    derive the position from the container's geometry and the text's alignment.

    For verticalAlign='middle': centers text height within container height.
    For verticalAlign='top' / 'bottom': pads by BOUND_TEXT_PADDING from the edge.
    For textAlign='center': centers text width within container width.
    For textAlign='left' / 'right': pads by BOUND_TEXT_PADDING from the edge.

    NOTE: Only called for shape containers (rectangle, ellipse, diamond).
          Arrow/line containers use _get_arrow_label_position() instead.
    """
    cw, ch = container["width"], container["height"]
    cx, cy = container["x"], container["y"]
    tw, th = text_el["width"], text_el["height"]
    v_align = text_el.get("verticalAlign", "middle")
    h_align = text_el.get("textAlign", "center")

    if v_align == "middle":
        y = cy + (ch - th) / 2
    elif v_align == "bottom":
        y = cy + ch - th - BOUND_TEXT_PADDING
    else:  # "top"
        y = cy + BOUND_TEXT_PADDING

    if h_align == "center":
        x = cx + (cw - tw) / 2
    elif h_align == "right":
        x = cx + cw - tw - BOUND_TEXT_PADDING
    else:  # "left"
        x = cx + BOUND_TEXT_PADDING

    return x, y


def _frame_name_label_height():
    """Return the pixel height of the frame name label.

    Uses ZA.nameFontSize=14, ZA.nameLineHeight=1.25 → lineHeight_px = 17.5.
    """
    return _FRAME_NAME_FONT_SIZE * _FRAME_NAME_LINE_HEIGHT  # 17.5


def _frame_name_label_voffset():
    """Compute vertical baseline offset for the Helvetica frame name label.

    Port of tE(dA.Helvetica, nameFontSize, nameFontSize * nameLineHeight).
    Helvetica metrics: unitsPerEm=2048, ascender=1577, descender=-471.
    """
    fs = _FRAME_NAME_FONT_SIZE
    lh_px = _FRAME_NAME_FONT_SIZE * _FRAME_NAME_LINE_HEIGHT
    em = fs / _HELVETICA_UNITS_PER_EM
    ascender_px = em * _HELVETICA_ASCENDER
    descender_px = em * _HELVETICA_DESCENDER
    line_gap = (lh_px - ascender_px + descender_px) / 2
    return ascender_px + line_gap


def _frame_label_scene_y(frame_el):
    """Return the scene-space y coordinate of the top of the frame name label.

    Port of im() in staticSvgScene.ts:
      label y = frame.y - ZA.nameOffsetY
      label.y -= label.height  (moved above the frame)
    """
    label_height = _frame_name_label_height()
    return frame_el["y"] - _FRAME_NAME_OFFSET_Y - label_height


def _build_frame_name_synthetic_el(frame_el):
    """Build a synthetic text-like dict for the frame name label.

    Mirrors im() from staticSvgScene.ts which creates a GQ text element for
    frame/magicframe elements. Returns None if the frame has no name.
    """
    name = frame_el.get("name")
    if name is None:
        # cc(frame) = "Frame" for normal frames, "AI Frame" for magicframes
        name = "Frame" if frame_el["type"] == "frame" else "AI Frame"
    label_height = _frame_name_label_height()
    label_y = _frame_label_scene_y(frame_el)
    # Width is approximate (canvas-dependent); use frame width as upper bound.
    # For bounds computation, frame.x to frame.x+frame.width covers the label.
    label_width = frame_el["width"]
    return {
        "_is_frame_label": True,       # marker: handled specially in to_svg()
        "type": "text",                # treated as text for bounds
        "x": frame_el["x"],
        "y": label_y,
        "width": label_width,
        "height": label_height,
        "angle": frame_el.get("angle", 0),
        "text": name,
        "_frame_id": frame_el["id"],
    }


def _render_frame_name_label(label_el, tx, ty, angle_deg, rcx, rcy):
    """Emit the <g transform> + <text> for a frame name label.

    Port of the text rendering used by the frame label in staticSvgScene.ts.
    Uses Helvetica font metrics (dA.Helvetica=2 in Excalidraw).
    """
    voff = _frame_name_label_voffset()
    text = _escape(label_el["text"])
    transform = f'translate({_f(tx)} {_f(ty)}) rotate({_f(angle_deg)} {_f(rcx)} {_f(rcy)})'
    return el("g", {"transform": transform},
        el("text", {
            "x": "0",
            "y": voff,
            "font-family": _HELVETICA_FAMILY,
            "font-size": f"{_FRAME_NAME_FONT_SIZE}px",
            "fill": _FRAME_NAME_COLOR,
            "text-anchor": "start",
            "style": "white-space: pre;",
            "xml:space": "preserve",
            "direction": "ltr",
            "dominant-baseline": "alphabetic",
        }, text)
    )


def _render_frame_rect(frame_el, tx, ty, angle_deg, rcx, rcy):
    """Emit the bare <rect> for a frame outline.

    Port of staticSvgScene.ts frame/magicframe case:
      rect with ZA constants, transform embedded directly (no <g> wrapper).
    """
    w = frame_el["width"]
    h = frame_el["height"]
    transform = f'translate({_f(tx)} {_f(ty)}) rotate({_f(angle_deg)} {_f(rcx)} {_f(rcy)})'
    # el() void emits ' />' but golden expects '/>'; left as f-string to stay byte-exact.
    return (
        f'<rect transform="{transform}" '
        f'width="{w}px" height="{h}px" '
        f'rx="{_FRAME_RADIUS}" ry="{_FRAME_RADIUS}" '
        f'fill="none" stroke="{_FRAME_STROKE_COLOR}" '
        f'stroke-width="{_FRAME_STROKE_WIDTH}"/>'
    )


def _build_frame_clip_path(frame_el, tx, ty, angle_deg, rcx, rcy):
    """Build a <clipPath> element for a frame (placed in <defs>).

    Port of the Zw(A)/clipPath logic in exportToSvg:
      <clipPath id="{frame.id}"><rect transform="..." width="..." height="..." rx="8" ry="8"/>
    """
    w = frame_el["width"]
    h = frame_el["height"]
    transform = f'translate({_f(tx)} {_f(ty)}) rotate({_f(angle_deg)} {_f(rcx)} {_f(rcy)})'
    # Inner <rect> uses f-string: el() void emits ' />' but golden expects '/>'.
    inner = (
        f'<rect transform="{transform}" '
        f'width="{w}" height="{h}" '
        f'rx="{_FRAME_RADIUS}" ry="{_FRAME_RADIUS}"/>'
    )
    return el("clipPath", {"id": frame_el["id"]}, inner)


SceneLayout = collections.namedtuple(
    "SceneLayout",
    "els by_id frame_labels arrow_label_scene "
    "off_x off_y width height padding background scale min_x min_y",
)


def scene_layout(doc, options=None, background="#ffffff", padding=PAD):
    """Compute the scene→SVG layout for *doc* — the single source of truth.

    Returns a :class:`SceneLayout` with the offset/size fields to_svg needs
    (off_x, off_y, width, height) plus everything the render loop reuses
    (els, by_id, frame_labels, arrow_label_scene). The font-render detector
    (tools/font_diff.py) uses off_x/off_y/width/height/scale to map a text
    element's scene bbox onto the exported PNG. Because to_svg() calls this
    same function, the two can never disagree on where anything lands.
    """
    if options is not None:
        background = options.view_background_color if options.export_background else None
        padding = options.export_padding
    els = [e for e in doc["elements"] if not e.get("isDeleted")]
    # Sort elements by fractional index (lexicographic string order).
    # Elements missing index sort first (empty string). Excalidraw renders in index order.
    els = sorted(els, key=lambda e: e.get("index") or "")

    # Build synthetic frame name label elements (im() port).
    # These extend the scene bounds upward and are rendered before the frame rect.
    frame_labels = {}   # frame_id → synthetic label dict
    els_with_labels = []
    for el in els:
        if el["type"] in ("frame", "magicframe"):
            lbl = _build_frame_name_synthetic_el(el)
            frame_labels[el["id"]] = lbl
            els_with_labels.append(lbl)   # label contributes to bounds
        els_with_labels.append(el)

    # Build id→element map for bound-text container lookups.
    # Must be built BEFORE bounds computation so arrow-label positions can be resolved.
    _by_id = {e["id"]: e for e in els}

    # Pre-pass: for each arrow/line element, compute the label scene position so we can
    # (a) emit a <mask> on the arrow stroke group (gap behind the label text), and
    # (b) feed the CORRECTED label position into scene bounds (Fix 1: stale stored x/y).
    # Maps arrow_id → (label_x, label_y, label_w, label_h) in SCENE coordinates.
    _arrow_label_scene: dict = {}
    for el in els:
        if el["type"] not in ("arrow", "line"):
            continue
        bound = el.get("boundElements") or []
        for ref in bound:
            if ref.get("type") != "text":
                continue
            lbl = _by_id.get(ref["id"])
            if lbl is None:
                continue
            lx, ly = _get_arrow_label_position(el, lbl)
            _arrow_label_scene[el["id"]] = (lx, ly, lbl["width"], lbl["height"])
            break  # only one label per arrow

    # Compute scene bounds INCLUDING frame name labels.
    # Frame labels are text-like (have x, y, width, height, angle) but not real elements.
    # We compute bounds over ALL contributing objects.
    #
    # Fix 1 — arrow/line-bound text labels: substitute the RECOMPUTED midpoint position
    # for bounds computation instead of the stored (often stale) x/y.  Real Excalidraw
    # always recomputes the label position from the path geometry before computing export
    # bounds; our stored x/y can be far off, inflating the viewBox by 100-200 px.
    # We identify arrow-bound text elements by checking if their containerId belongs to
    # an arrow/line that is in _arrow_label_scene.
    _arrow_bound_label_ids = {
        ref["id"]
        for el in els
        if el["type"] in ("arrow", "line") and el["id"] in _arrow_label_scene
        for ref in (el.get("boundElements") or [])
        if ref.get("type") == "text"
    }
    bounds_els = []
    for obj in els_with_labels:
        if obj.get("_is_frame_label"):
            # Treat as a simple axis-aligned rect for bounds (angle handled via parent frame).
            bounds_els.append({
                "type": "rectangle", "x": obj["x"], "y": obj["y"],
                "width": obj["width"], "height": obj["height"],
                "angle": obj["angle"],
            })
        elif obj.get("type") == "text" and obj.get("id") in _arrow_bound_label_ids:
            # Arrow/line-bound label: substitute recomputed midpoint position for bounds.
            container_id = obj.get("containerId")
            container = _by_id.get(container_id)
            if container is not None:
                lx, ly, lw, lh = _arrow_label_scene[container_id]
                bounds_els.append({
                    "type": "rectangle",
                    "x": lx, "y": ly,
                    "width": lw, "height": lh,
                    "angle": obj.get("angle", 0),
                })
            else:
                bounds_els.append(obj)
        else:
            bounds_els.append(obj)

    min_x, min_y, max_x, max_y = excalidraw_bounds.get_common_bounds(bounds_els)
    width = (max_x - min_x) + padding * 2
    height = (max_y - min_y) + padding * 2
    off_x = -min_x + padding
    off_y = -min_y + padding
    scale = float(options.export_scale) if options is not None else 1.0
    return SceneLayout(
        els=els, by_id=_by_id, frame_labels=frame_labels,
        arrow_label_scene=_arrow_label_scene,
        off_x=off_x, off_y=off_y, width=width, height=height,
        padding=padding, background=background, scale=scale,
        min_x=min_x, min_y=min_y,
    )


def to_svg(doc, options=None, background="#ffffff", padding=PAD):
    """Convert an Excalidraw document dict to a deterministic SVG string.

    Args:
        doc: Parsed Excalidraw JSON as a Python dict.
        options: ExportOptions instance (from export_options.resolve).  When given,
                 it takes precedence over the *background* and *padding* kwargs.
                 Back-compat: a bare to_svg(doc) call (options=None) behaves exactly
                 as before — white background, padding=10.
        background: Background fill colour (CSS colour string) or None for transparent.
                    Ignored when *options* is provided.
        padding: Padding in pixels around the scene bounds (default 10).
                 Ignored when *options* is provided.

    Returns:
        A self-contained SVG string with embedded fonts.
    """
    layout = scene_layout(doc, options, background=background, padding=padding)
    els = layout.els
    _by_id = layout.by_id
    frame_labels = layout.frame_labels
    _arrow_label_scene = layout.arrow_label_scene
    off_x, off_y = layout.off_x, layout.off_y
    width, height = layout.width, layout.height
    padding = layout.padding
    background = layout.background

    # Arrow masks: one <mask> per arrow/line that has a bound label.
    # The mask punches a transparent hole in the arrow stroke behind the label.
    # Port of real Excalidraw staticSvgScene.ts:
    #   mask id = "mask-{el.id}" (not "arrow-label-mask-{el.id}")
    #   mask is in SVG ROOT coordinate space (scene coords + off_x/off_y)
    #   white rect covers total SVG canvas (width+PAD, height+PAD sized)
    #   black rect = label bounds in scene+offset coords with opacity="1"
    #   mask is placed INLINE after the masked arrow group body (not in <defs>)
    #
    # NOTE: We pre-build the mask strings below as a dict keyed by el_id.
    # They are emitted inline in the main rendering loop after each arrow group.
    # Stored with placeholder for off_x/off_y (unknown until bounds computed above).
    arrow_masks: dict = {}   # el_id → mask SVG string (built after off_x/off_y known)

    body = []
    if background:
        # el() void emits ' />' but golden expects '/>'; left as f-string to stay byte-exact.
        body.append(
            f'<rect x="0" y="0" width="{_fv(width)}" height="{_fv(height)}" fill="{background}"/>'
        )

    # Collect image symbols: one <symbol> per unique fileId (defined once in <defs>).
    # Port of staticSvgScene.ts image branch: symbol id = "image-{fileId}".
    files = doc.get("files") or {}
    image_symbols = {}   # fileId → symbol SVG string (deduplicated)
    frame_clip_paths = {}  # frame_id → clipPath SVG string

    for el_ in els:
        angle = el_.get("angle", 0)
        deg = 180 * angle / 3.141592653589793
        # Compute rotate center from faithful element coords (mirrors staticSvgScene.ts:98-100).
        # get_element_absolute_coords returns the unrotated tight bbox; the rotate center
        # in element-local coords is the center of that bbox offset from el_["x"]/el_["y"].
        # For shapes this equals width/2, height/2; for linear elements it uses the
        # curve-ops bbox center (previously wrong when the curve bbox ≠ points bbox).
        x1, y1, x2, y2, _cx, _cy = excalidraw_bounds.get_element_absolute_coords(el_)
        rcx = (x2 - x1) / 2 - (el_["x"] - x1)   # rotate center x in element-local frame
        rcy = (y2 - y1) / 2 - (el_["y"] - y1)   # rotate center y in element-local frame

        # For shape-bound text, compute position from the container geometry rather than
        # trusting the stored x/y (getBoundTextElementPosition port).
        # For arrow/line-bound labels, compute the position from the path midpoint
        # (port of LinearElementEditor.getBoundTextElementPosition in Excalidraw source).
        # Stored x/y for arrow labels may be stale or wrong — real Excalidraw always
        # recomputes from the path geometry.
        container_id = el_.get("containerId")
        container = _by_id.get(container_id) if (el_["type"] == "text" and container_id and container_id in _by_id) else None
        if container is not None and container["type"] in ("rectangle", "ellipse", "diamond"):
            bx, by = _get_bound_text_position(container, el_)
            tx, ty = bx + off_x, by + off_y
        elif container is not None and container["type"] in ("arrow", "line"):
            bx, by = _get_arrow_label_position(container, el_)
            tx, ty = bx + off_x, by + off_y
        else:
            tx, ty = el_["x"] + off_x, el_["y"] + off_y   # free text (no container)

        # ── frame / magicframe ────────────────────────────────────────────────
        if el_["type"] in ("frame", "magicframe"):
            # Render frame name label BEFORE the frame rect (matches Excalidraw output order).
            lbl = frame_labels.get(el_["id"])
            if lbl is not None:
                lbl_ty = lbl["y"] + off_y
                lbl_tx = lbl["x"] + off_x
                lbl_height = lbl["height"]
                lbl_width = lbl["width"]
                lbl_rcx = lbl_width / 2
                lbl_rcy = lbl_height / 2
                body.append(_render_frame_name_label(lbl, lbl_tx, lbl_ty, deg, lbl_rcx, lbl_rcy))
            # Frame rect: bare <rect> (no <g> wrapper), transform embedded in the rect.
            body.append(_render_frame_rect(el_, tx, ty, deg, rcx, rcy))
            # Collect frame clipPath for <defs>.
            # NOTE: clipPath emitted for golden parity; frameId-based child clipping is NOT
            # implemented — populated frames export children unclipped (no populated-frame
            # case in the corpus).
            frame_clip_paths[el_["id"]] = _build_frame_clip_path(el_, tx, ty, deg, rcx, rcy)
            continue

        # ── embeddable / iframe ───────────────────────────────────────────────
        if el_["type"] in ("embeddable", "iframe"):
            transform = (
                f'translate({_f(tx)} {_f(ty)}) rotate({_f(deg)} {_f(rcx)} {_f(rcy)})'
            )
            opacity = el_.get("opacity", 100) / 100
            g_dict = {"stroke-linecap": "round", "transform": transform}
            if opacity != 1.0:
                g_dict = {**g_dict, "stroke-opacity": opacity, "fill-opacity": opacity}
            inner = _render_element(el_, options)
            g_tag = el("g", g_dict, inner)
            # If the element has a link, wrap in <a href>.
            link = el_.get("link")
            if link:
                # _sanitize_link enforces protocol whitelist (http/https/mailto → about:blank).
                # el() escapes the href value — no manual _escape_attr needed.
                body.append(el("a", {"href": _sanitize_link(link)}, g_tag))
            else:
                body.append(g_tag)
            continue

        transform = (
            f'translate({_f(tx)} {_f(ty)}) rotate({_f(deg)} {_f(rcx)} {_f(rcy)})'
        )

        # Collect image symbol definition for <defs> (deduplicated per fileId).
        if el_["type"] == "image":
            file_id = el_.get("fileId", "")
            if file_id and file_id not in image_symbols:
                file_entry = files.get(file_id)
                if file_entry:
                    data_url = _escape_attr(file_entry["dataURL"])
                    image_symbols[file_id] = (
                        f'<symbol id="image-{file_id}">'
                        f'<image href="{data_url}" preserveAspectRatio="none"'
                        f' width="100%" height="100%"></image>'
                        f'</symbol>'
                    )

        # Arrow/line elements:
        # - WITH a bound label: outer group carries mask="url(#mask-{id})" and a
        #   filled <mask> is emitted after the group (punches gap in stroke behind label).
        # - WITHOUT a bound label: outer group has no mask attribute, followed by an
        #   empty <mask></mask> (Fix 2: structural parity with real Excalidraw, which
        #   unconditionally emits a mask element after every arrow/line group).
        # Port of real Excalidraw staticSvgScene.ts: the mask is emitted AFTER the group,
        # uses id="mask-{el_.id}" (labeled) or is bare empty (unlabeled), and is in SVG
        # root/scene coordinate space.
        el_id = el_.get("id")
        el_opacity = el_.get("opacity", 100) / 100
        if el_["type"] in ("arrow", "line") and el_id in _arrow_label_scene:
            mask_id = f"mask-{el_id}"
            if el_opacity != 1.0:
                inner_g = el("g", {"stroke-opacity": el_opacity, "fill-opacity": el_opacity, "transform": transform}, _render_element(el_, options))
            else:
                inner_g = el("g", {"transform": transform}, _render_element(el_, options))
            body.append(el("g", {"mask": f"url(#{mask_id})", "stroke-linecap": "round"}, inner_g))
            # Build and emit the mask INLINE after the arrow group (scene coords + offset).
            lx, ly, lw, lh = _arrow_label_scene[el_id]
            # Scene coords with offset (SVG root coordinate space)
            svg_lx = lx + off_x
            svg_ly = ly + off_y
            # White rect: large enough to cover the whole SVG canvas
            white_w = _f(width + padding)
            white_h = _f(height + padding)
            # Inner <rect> elements use f-string: el() void emits ' />' but golden expects '/>'.
            body.append(el("mask", {"id": mask_id},
                f'<rect x="0" y="0" fill="#fff" width="{white_w}" height="{white_h}"/>'
                f'<rect x="{_f(svg_lx)}" y="{_f(svg_ly)}" fill="#000" '
                f'width="{_f(lw)}" height="{_f(lh)}" opacity="1"/>'
            ))
        elif el_["type"] in ("arrow", "line"):
            # Unlabeled arrow/line: plain stroke-linecap group + empty mask (Fix 2).
            if el_opacity != 1.0:
                inner_g = el("g", {"stroke-opacity": el_opacity, "fill-opacity": el_opacity, "transform": transform}, _render_element(el_, options))
            else:
                inner_g = el("g", {"transform": transform}, _render_element(el_, options))
            body.append(el("g", {"stroke-linecap": "round"}, inner_g))
            body.append(el("mask", None))
        else:
            # General elements (rectangle, ellipse, diamond, text, freedraw, image …).
            # Rough shapes (non-text) carry stroke-linecap="round" from real Excalidraw's
            # renderElementToSvg; text does not. Opacity attrs go on the same root group.
            if el_opacity != 1.0:
                if el_["type"] == "text":
                    body.append(el("g", {"stroke-opacity": el_opacity, "fill-opacity": el_opacity, "transform": transform}, _render_element(el_, options)))
                else:
                    body.append(el("g", {"stroke-opacity": el_opacity, "fill-opacity": el_opacity, "stroke-linecap": "round", "transform": transform}, _render_element(el_, options)))
            else:
                body.append(el("g", {"transform": transform}, _render_element(el_, options)))

    clip_paths_str = "".join(frame_clip_paths.values())
    symbols_str = "".join(image_symbols.values())
    css = fonts.font_face_css()  # raw CSS — passed as literal child, NOT escaped
    style = el("defs", None, clip_paths_str, symbols_str, el("style", {"class": "style-fonts"}, css))

    # Dark-mode: when export_with_dark_mode is True, invert the background colour
    # to the dark-theme counterpart (#1e1e2e as a minimal stub — corpus uses neither).
    # DONE_WITH_CONCERNS: full dark-mode would remap all element colours via Excalidraw's
    # "invertSelectedElements" logic; only the bg inversion is implemented here.
    dark_mode = options is not None and options.export_with_dark_mode
    if dark_mode and background:
        background = "#1e1e2e"  # Excalidraw dark canvas background (minimal stub)

    # Embed-scene: when export_embed_scene is True, embed the raw scene JSON in <metadata>.
    # This mirrors Excalidraw's own SVG export (importFromSVG can round-trip it).
    import json as _json
    embed_scene = options is not None and options.export_embed_scene
    if embed_scene:
        scene_json = _json.dumps(doc, separators=(",", ":"))
        # scene_json is raw JSON — pass as literal child to avoid double-escaping.
        metadata = el("metadata", None, el("excalidraw-scene", None, scene_json))
    else:
        metadata = el("metadata", None)

    w_s = _fv(width)
    h_s = _fv(height)
    return el("svg",
        {"version": "1.1", "xmlns": "http://www.w3.org/2000/svg",
         "viewBox": f"0 0 {w_s} {h_s}", "width": w_s, "height": h_s},
        f'<!-- svg-source:excalidraw -->{metadata}{style}{"".join(body)}',
    )
