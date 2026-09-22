# test_font_diff.py — pure metrics for the font-render error detector.
#
# These metrics compare the alpha channel of OUR export against the ORIGINAL
# excalidraw.com asset, restricted to a text element's pixel bounding box. The
# whole point is AA-robustness: anti-aliasing smears glyph edges by 1-2px but
# preserves total ink, so metrics that aggregate over a box see through the
# wobble and only fire on real font-render failures (missing glyphs, the usvg
# whole-chunk poison, wrong fallback font, displaced text).
import json
import math
import pathlib
import sys

import pytest

np = pytest.importorskip("numpy")

sys.path.insert(0, str(pathlib.Path(__file__).parent))          # tools/ → font_diff
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))   # repo root → excalidraw_svg
import font_diff as fd  # noqa: E402
import excalidraw_svg  # noqa: E402
import export_options  # noqa: E402


def _blank(h=20, w=40):
    return np.zeros((h, w), dtype=np.float64)


# --- ink_from_rgba (background-invariant ink signal) -----------------------

def test_ink_from_rgba_opaque_white_is_zero():
    img = np.zeros((5, 5, 4)); img[:, :, :3] = 255; img[:, :, 3] = 255
    assert fd.ink_from_rgba(img).max() == pytest.approx(0.0)


def test_ink_from_rgba_transparent_is_zero():
    img = np.zeros((5, 5, 4))  # alpha 0 everywhere → over white = white = no ink
    assert fd.ink_from_rgba(img).max() == pytest.approx(0.0)


def test_ink_from_rgba_opaque_black_is_max():
    img = np.zeros((5, 5, 4)); img[:, :, 3] = 255  # rgb 0, alpha 255 = black
    assert fd.ink_from_rgba(img)[0, 0] == pytest.approx(255.0)


def test_ink_from_rgba_is_background_invariant():
    # Same dark pixel, once on an OPAQUE-WHITE canvas, once on a TRANSPARENT one.
    opaque = np.zeros((5, 5, 4)); opaque[:, :, :3] = 255; opaque[:, :, 3] = 255
    opaque[2, 2, :3] = 0                       # black pixel on white
    transp = np.zeros((5, 5, 4))
    transp[2, 2, :3] = 0; transp[2, 2, 3] = 255  # same black pixel on transparent
    assert np.allclose(fd.ink_from_rgba(opaque), fd.ink_from_rgba(transp))


# --- is_transparent (match the asset background for the A/B page) -----------

def test_is_transparent_opaque_is_false():
    img = np.zeros((10, 10, 4)); img[:, :, 3] = 255
    assert fd.is_transparent(img) is False


def test_is_transparent_mostly_transparent_is_true():
    img = np.zeros((10, 10, 4)); img[4:6, 4:6, 3] = 255  # mostly alpha 0
    assert fd.is_transparent(img) is True


def test_is_transparent_few_transparent_pixels_is_false():
    img = np.zeros((10, 10, 4)); img[:, :, 3] = 255; img[0, 0, 3] = 0  # 1% transparent
    assert fd.is_transparent(img) is False


FULL = (0, 0, 40, 20)  # (x0, y0, x1, y1) covering the whole 20x40 array


# --- ink_balance -----------------------------------------------------------

def test_ink_balance_identical_is_one():
    a = _blank()
    a[5:15, 10:30] = 255
    assert fd.ink_balance(a, a, FULL) == pytest.approx(1.0)


def test_ink_balance_half_ink_is_half():
    orig = _blank(); orig[5:15, 10:30] = 255          # 200 px of ink
    ours = _blank(); ours[5:15, 10:20] = 255          # 100 px of ink
    assert fd.ink_balance(ours, orig, FULL) == pytest.approx(0.5)


def test_ink_balance_is_aa_invariant():
    # Same TOTAL alpha spread over more pixels (anti-aliasing smears the edge).
    orig = _blank(); orig[10, 10:20] = 254            # 10 px * 254 = 2540
    ours = _blank(); ours[10, 10:30] = 127            # 20 px * 127 = 2540
    assert fd.ink_balance(ours, orig, FULL) == pytest.approx(1.0)


def test_ink_balance_both_empty_is_one():
    a = _blank()
    assert fd.ink_balance(a, a, FULL) == pytest.approx(1.0)


def test_ink_balance_restricted_to_box():
    # Ink outside the box must not count.
    orig = _blank(); orig[2, 2] = 255                  # outside box below
    ours = _blank()
    box = (10, 5, 30, 15)
    orig[8, 12] = 255; ours[8, 12] = 255              # equal inside box
    assert fd.ink_balance(ours, orig, box) == pytest.approx(1.0)


# --- projection_correlation ------------------------------------------------

def _glyph_row(glyphs=(5, 15, 25, 35, 45), gw=4, val=255, h=20, w=60, rows=(6, 14)):
    """A fake text line: vertical glyph-strokes with gaps, like a real column profile."""
    a = np.zeros((h, w), dtype=np.float64)
    for gx in glyphs:
        a[rows[0]:rows[1], gx:gx + gw] = val
    return a


BOX60 = (0, 0, 60, 20)


def test_projection_correlation_identical_is_one():
    a = _glyph_row()
    assert fd.projection_correlation(a, a, BOX60) == pytest.approx(1.0)


def test_projection_correlation_full_block_identical_is_one():
    # Flat profile (zero variance) but identical → must be 1.0, not undefined.
    orig = _glyph_row(glyphs=(0,), gw=60)
    ours = _glyph_row(glyphs=(0,), gw=60, val=127)     # same shape, half intensity
    assert fd.projection_correlation(ours, orig, BOX60) == pytest.approx(1.0)


def test_projection_correlation_one_px_shift_stays_high():
    orig = _glyph_row()
    ours = _glyph_row(glyphs=(6, 16, 26, 36, 46))      # every glyph shifted +1px
    assert fd.projection_correlation(ours, orig, BOX60) > 0.98


def test_projection_correlation_missing_glyph_drops():
    orig = _glyph_row(glyphs=(5, 15, 25, 35, 45))
    ours = _glyph_row(glyphs=(5, 15, 35, 45))          # middle glyph dropped
    assert fd.projection_correlation(ours, orig, BOX60) < 0.9


def test_projection_correlation_both_empty_is_one():
    a = _blank()
    assert fd.projection_correlation(a, a, BOX60) == pytest.approx(1.0)


def test_projection_correlation_one_empty_is_zero():
    orig = _glyph_row()
    ours = _blank()
    assert fd.projection_correlation(ours, orig, BOX60) == pytest.approx(0.0)


# --- centroid_shift --------------------------------------------------------

def test_centroid_shift_identical_is_zero():
    a = _blank(30, 40); a[5:15, 10:20] = 255
    assert fd.centroid_shift(a, a, (0, 0, 40, 30)) == pytest.approx(0.0)


def test_centroid_shift_measures_offset():
    orig = _blank(30, 40); orig[5:15, 10:20] = 255     # centroid (14.5, 9.5)
    ours = _blank(30, 40); ours[7:17, 13:23] = 255     # centroid (17.5, 11.5) → +3,+2
    assert fd.centroid_shift(ours, orig, (0, 0, 40, 30)) == pytest.approx((13) ** 0.5)


def test_centroid_shift_both_empty_is_zero():
    a = _blank(30, 40)
    assert fd.centroid_shift(a, a, (0, 0, 40, 30)) == pytest.approx(0.0)


def test_centroid_shift_one_empty_is_zero():
    # Empty side is ink_balance's job; centroid is undefined → report no shift.
    orig = _blank(30, 40); orig[5:15, 10:20] = 255
    ours = _blank(30, 40)
    assert fd.centroid_shift(ours, orig, (0, 0, 40, 30)) == pytest.approx(0.0)


# --- classify_verdict ------------------------------------------------------

def test_verdict_ok():
    assert fd.classify_verdict(ink=1.0, corr=1.0, shift_px=0.0) == "OK"


def test_verdict_ink_loss():
    assert fd.classify_verdict(ink=0.3, corr=1.0, shift_px=0.0) == "INK_LOSS"


def test_verdict_ink_gain():
    assert fd.classify_verdict(ink=2.0, corr=1.0, shift_px=0.0) == "INK_GAIN"


def test_verdict_inf_ink_is_gain():
    # ink appeared where the original had none (ink_balance → inf).
    assert fd.classify_verdict(ink=float("inf"), corr=1.0, shift_px=0.0) == "INK_GAIN"


def test_verdict_shape_mismatch():
    assert fd.classify_verdict(ink=1.0, corr=0.5, shift_px=0.0) == "SHAPE_MISMATCH"


def test_verdict_displaced():
    assert fd.classify_verdict(ink=1.0, corr=1.0, shift_px=10.0) == "DISPLACED"


def test_verdict_ink_loss_beats_shape():
    # A poisoned chunk drops BOTH ink and corr — must read as INK_LOSS.
    assert fd.classify_verdict(ink=0.2, corr=0.2, shift_px=0.0) == "INK_LOSS"


def test_verdict_thresholds_overridable():
    assert fd.classify_verdict(ink=0.7, corr=1.0, shift_px=0.0, ink_lo=0.8) == "INK_LOSS"


# --- text_pixel_boxes ------------------------------------------------------

def _free_text_doc(x=10.0, y=20.0, w=100.0, h=30.0, text="Hi"):
    return {
        "elements": [{
            "id": "t1", "type": "text", "x": x, "y": y, "width": w, "height": h,
            "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
            "roughness": 1, "roundness": None, "opacity": 100,
            "groupIds": [], "frameId": None, "boundElements": None,
            "updated": 0, "link": None, "locked": False, "containerId": None,
            "seed": 1, "version": 1, "versionNonce": 1, "isDeleted": False, "index": "a1",
            "text": text, "originalText": text, "fontFamily": 1, "fontSize": 20,
            "textAlign": "left", "verticalAlign": "top", "lineHeight": 1.25, "autoResize": None,
        }],
        "appState": {"viewBackgroundColor": "#ffffff"}, "files": {},
    }


def _bound_text_doc():
    """Container rect 200x80 at (0,0) + center/middle bound text with STALE x/y=999."""
    return {
        "elements": [
            {"id": "c1", "type": "rectangle", "x": 0, "y": 0, "width": 200, "height": 80,
             "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
             "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1,
             "roundness": None, "opacity": 100, "groupIds": [], "frameId": None,
             "boundElements": [{"id": "t1", "type": "text"}], "updated": 0, "link": None,
             "locked": False, "seed": 1, "version": 1, "versionNonce": 1, "isDeleted": False,
             "index": "a1"},
            {"id": "t1", "type": "text", "x": 999, "y": 999, "width": 160, "height": 40,
             "angle": 0, "strokeColor": "#1e1e1e", "backgroundColor": "transparent",
             "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1,
             "roundness": None, "opacity": 100, "groupIds": [], "frameId": None,
             "boundElements": None, "updated": 0, "link": None, "locked": False,
             "seed": 2, "version": 1, "versionNonce": 2, "isDeleted": False, "index": "a2",
             "text": "Center", "originalText": "Center", "containerId": "c1",
             "fontFamily": 1, "fontSize": 20, "textAlign": "center", "verticalAlign": "middle",
             "lineHeight": 1.25, "autoResize": None},
        ],
        "appState": {"viewBackgroundColor": "#ffffff"}, "files": {},
    }


def test_text_pixel_boxes_free_text_transform():
    doc = _free_text_doc(x=10, y=20, w=100, h=30)
    opts = export_options.resolve(doc)
    layout = excalidraw_svg.scene_layout(doc, opts)
    boxes = fd.text_pixel_boxes(doc, opts, layout)
    assert len(boxes) == 1
    x0, y0, x1, y1 = boxes[0]["box"]
    s, ox, oy = layout.scale, layout.off_x, layout.off_y
    assert x0 == int(math.floor((10 + ox) * s))
    assert y0 == int(math.floor((20 + oy) * s))
    assert x1 == int(math.ceil((110 + ox) * s))
    assert y1 == int(math.ceil((50 + oy) * s))


def test_text_pixel_boxes_scale_doubles_coords():
    doc = _free_text_doc()
    o1 = export_options.resolve(doc, export_scale=1.0)
    o2 = export_options.resolve(doc, export_scale=2.0)
    b1 = fd.text_pixel_boxes(doc, o1)[0]["box"]
    b2 = fd.text_pixel_boxes(doc, o2)[0]["box"]
    # width of the box at 2x is ~2x the width at 1x
    assert (b2[2] - b2[0]) == pytest.approx(2 * (b1[2] - b1[0]), abs=2)


def test_text_pixel_boxes_bound_text_uses_container_not_stored_xy():
    doc = _bound_text_doc()
    opts = export_options.resolve(doc)
    layout = excalidraw_svg.scene_layout(doc, opts)
    tb = next(b for b in fd.text_pixel_boxes(doc, opts, layout) if b["id"] == "t1")
    x0, y0, x1, y1 = tb["box"]
    # bound position resolves to scene (20, 20); stored 999 must NOT be used.
    assert x0 == int(math.floor((20 + layout.off_x) * layout.scale))
    assert x1 < 500, "stored x=999 leaked into the pixel box"


def test_text_pixel_boxes_skips_non_text():
    doc = _bound_text_doc()  # has a rectangle + a text
    boxes = fd.text_pixel_boxes(doc, export_options.resolve(doc))
    assert [b["id"] for b in boxes] == ["t1"]


def test_text_pixel_boxes_within_image():
    doc = _free_text_doc()
    opts = export_options.resolve(doc)
    layout = excalidraw_svg.scene_layout(doc, opts)
    w_px = int(round(layout.width * layout.scale))
    h_px = int(round(layout.height * layout.scale))
    for b in fd.text_pixel_boxes(doc, opts, layout):
        x0, y0, x1, y1 = b["box"]
        assert 0 <= x0 < x1 <= w_px
        assert 0 <= y0 < y1 <= h_px


# --- aa_tolerant_diff ------------------------------------------------------

def test_aa_tolerant_diff_identical_has_no_diff():
    a = _blank(30, 40); a[5:20, 5:20] = 255
    assert not fd.aa_tolerant_diff(a, a).any()


def test_aa_tolerant_diff_tolerates_one_px_shift():
    orig = _blank(30, 40); orig[10:20, 10:20] = 255
    ours = _blank(30, 40); ours[10:20, 11:21] = 255   # shifted +1px in x
    assert not fd.aa_tolerant_diff(ours, orig).any()


def test_aa_tolerant_diff_flags_real_difference():
    orig = _blank(30, 40)
    ours = _blank(30, 40); ours[10:20, 10:20] = 255   # a block orig lacks entirely
    mask = fd.aa_tolerant_diff(ours, orig)
    assert mask[12:18, 12:18].all()                   # interior of the block flagged


def test_aa_tolerant_diff_respects_threshold():
    orig = _blank(30, 40)
    ours = _blank(30, 40); ours[10:20, 10:20] = 20    # below default thresh=24
    assert not fd.aa_tolerant_diff(ours, orig, thresh=24).any()


# --- gaussian_blur (dampens high-frequency AA jitter before corr) -----------

def test_gaussian_blur_sigma_zero_is_identity():
    m = _blank(); m[5:10, 5:10] = 100.0
    assert np.array_equal(fd.gaussian_blur(m, 0), m)


def test_gaussian_blur_spreads_peak_and_conserves_mass():
    m = _blank(20, 20); m[10, 10] = 100.0
    b = fd.gaussian_blur(m, 1.0)
    assert b[10, 10] < 100.0                              # peak lowered
    assert b[10, 11] > 0.0 and b[11, 10] > 0.0            # spread to neighbours
    assert b.sum() == pytest.approx(m.sum())              # total ink conserved


def test_gaussian_blur_preserves_constant_field():
    m = np.full((20, 20), 50.0)
    assert fd.gaussian_blur(m, 1.0) == pytest.approx(50.0)


# --- analyze_text_elements (orchestration) ---------------------------------

def _canvas_and_box(doc, opts):
    layout = excalidraw_svg.scene_layout(doc, opts)
    w = int(round(layout.width * layout.scale))
    h = int(round(layout.height * layout.scale))
    box = fd.text_pixel_boxes(doc, opts, layout)[0]["box"]
    return layout, np.zeros((h, w), dtype=np.float64), box


def _fill_glyphs(canvas, box, val=255, step=3):
    x0, y0, x1, y1 = box
    canvas[y0:y1, x0:x1:step] = val   # vertical strokes = glyph-like column profile


def test_analyze_identical_is_ok():
    doc = _free_text_doc()
    opts = export_options.resolve(doc)
    layout, canvas, box = _canvas_and_box(doc, opts)
    _fill_glyphs(canvas, box)
    res = fd.analyze_text_elements(doc, opts, canvas, canvas.copy(), layout)
    assert len(res) == 1
    assert res[0]["verdict"] == "OK"
    assert res[0]["id"] == "t1"
    assert set(res[0]) >= {"id", "text", "box", "ink", "corr", "shift", "verdict"}


def test_analyze_missing_ink_is_ink_loss():
    doc = _free_text_doc()
    opts = export_options.resolve(doc)
    layout, orig, box = _canvas_and_box(doc, opts)
    _fill_glyphs(orig, box)
    ours = np.zeros_like(orig)                     # nothing rendered → poisoned/tofu
    res = fd.analyze_text_elements(doc, opts, ours, orig, layout)
    assert res[0]["verdict"] == "INK_LOSS"


def test_analyze_missing_glyph_is_shape_mismatch():
    doc = _free_text_doc()
    opts = export_options.resolve(doc)
    layout, orig, box = _canvas_and_box(doc, opts)
    _fill_glyphs(orig, box)
    ours = orig.copy()
    x0, y0, x1, y1 = box                           # blank the left third → gap in profile
    ours[y0:y1, x0:x0 + (x1 - x0) // 3] = 0
    res = fd.analyze_text_elements(doc, opts, ours, orig, layout)
    assert res[0]["verdict"] in ("SHAPE_MISMATCH", "INK_LOSS")


def test_analyze_blur_zero_matches_raw_corr():
    # blur_sigma=0 must reproduce the raw projection_correlation exactly.
    doc = _free_text_doc()
    opts = export_options.resolve(doc)
    layout, orig, box = _canvas_and_box(doc, opts)
    _fill_glyphs(orig, box)
    ours = orig.copy()
    x0, y0, x1, y1 = box
    ours[y0:y1, x0:x0 + 5] = 0
    got = fd.analyze_text_elements(doc, opts, ours, orig, layout, blur_sigma=0)[0]["corr"]
    assert got == pytest.approx(fd.projection_correlation(ours, orig, box))


def test_analyze_blur_affects_corr_not_ink():
    # Blur must feed the corr metric (changes it) but NOT ink (measured on raw maps).
    doc = _free_text_doc()
    opts = export_options.resolve(doc)
    layout, orig, box = _canvas_and_box(doc, opts)
    x0, y0, x1, y1 = box
    orig[y0:y1, x0:x1] = 255
    ours = orig.copy()
    ours[y0:y1, x0:x1:2] = 0          # high-frequency column gaps orig lacks
    r0 = fd.analyze_text_elements(doc, opts, ours, orig, layout, blur_sigma=0)[0]
    r2 = fd.analyze_text_elements(doc, opts, ours, orig, layout, blur_sigma=2)[0]
    assert r0["corr"] != r2["corr"]                 # blur reaches the corr metric
    assert r0["ink"] == pytest.approx(r2["ink"])    # ink stays on the raw maps


# --- end-to-end (real render) ---------------------------------------------
# Validates the whole pipeline on a real diagram: render → text_pixel_boxes →
# ink_from_rgba → metrics → verdict. Simulates the reliable failure mode (a text
# chunk vanishing, i.e. whole-chunk poison / tofu) by blanking one box, and checks
# that an identical render is fully clean (no false positives). Skips without resvg.

CALIB = dict(ink_lo=0.55, ink_hi=1.8, corr_min=0.10, shift_max=10.0)  # driver defaults
_ROOT = pathlib.Path(__file__).resolve().parent.parent            # excalidraw-generation/
_E2E_SRC = _ROOT / "tests/inputs/atkinson-shiffrin-de.excalidraw"


def _render_ink(src, opts):
    import tempfile
    from PIL import Image
    import export
    with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
        export.render_png(str(src), tmp.name, options=opts)
        return fd.ink_from_rgba(np.asarray(Image.open(tmp.name).convert("RGBA"), dtype=np.float64))


def test_e2e_identical_render_is_clean():
    pytest.importorskip("resvg_py")
    doc = json.loads(_E2E_SRC.read_text())
    opts = export_options.resolve(doc)
    layout = excalidraw_svg.scene_layout(doc, opts)
    ink = _render_ink(_E2E_SRC, opts)
    res = fd.analyze_text_elements(doc, opts, ink, ink, layout, **CALIB)
    assert res and all(r["verdict"] == "OK" for r in res)


def test_e2e_vanished_text_chunk_is_ink_loss():
    pytest.importorskip("resvg_py")
    src = _E2E_SRC
    doc = json.loads(src.read_text())
    opts = export_options.resolve(doc)
    layout = excalidraw_svg.scene_layout(doc, opts)
    ink_ref = _render_ink(src, opts)
    boxes = fd.text_pixel_boxes(doc, opts, layout)
    ink_bad = ink_ref.copy()
    x0, y0, x1, y1 = boxes[0]["box"]
    ink_bad[y0:y1, x0:x1] = 0.0                     # text chunk vanished (poison/tofu)
    res = fd.analyze_text_elements(doc, opts, ink_bad, ink_ref, layout, **CALIB)
    target = next(r for r in res if r["id"] == boxes[0]["id"])
    assert target["verdict"] == "INK_LOSS"
