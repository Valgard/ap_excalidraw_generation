# test_excalidraw_shape.py
import excalidraw_shape as sh

def _el(**kw):
    base = dict(type="rectangle", width=160, height=60, strokeColor="#1e1e1e",
               backgroundColor="transparent", fillStyle="solid", strokeWidth=2,
               strokeStyle="solid", roughness=1, seed=12345, roundness=None, points=None)
    base.update(kw); return base

def test_rough_options_solid_rectangle():
    o = sh.generate_rough_options(_el())
    assert o["seed"] == 12345
    assert o["disableMultiStroke"] is False
    assert o["strokeWidth"] == 2
    assert o["fillWeight"] == 1.0 and o["hachureGap"] == 8
    assert "strokeLineDash" not in o or o["strokeLineDash"] is None

def test_rough_options_dashed_adds_dash_and_bumps_width():
    o = sh.generate_rough_options(_el(strokeStyle="dashed"))
    assert o["disableMultiStroke"] is True
    assert o["strokeWidth"] == 2.5
    assert o["strokeLineDash"] == [8, 8 + 2]     # [8, 8+sw], sw is the ORIGINAL 2

def test_ellipse_adds_curve_fitting():
    o = sh.generate_rough_options(_el(type="ellipse"))
    assert o["curveFitting"] == 1

def test_adjust_roughness_downscales_small_shape():
    assert sh.adjust_roughness(_el(width=8, height=8, roughness=1)) == 1/3
    assert sh.adjust_roughness(_el(width=160, height=60, roughness=1)) == 1  # kept

def test_diamond_points_add_one_to_avoid_zeros():
    pts = sh.get_diamond_points(_el(type="diamond", width=140, height=80))
    assert pts[0] == [71, 0] and pts[1] == [140, 41]

def test_rectangle_shape_uses_rough_rectangle_when_unrounded():
    el = _el(seed=42)
    sets = sh.generate_element_shape(el)
    # unrounded rectangle → single rough rectangle drawable (one path opset, no fill)
    assert [s["type"] for s in sets] == ["path"]

def test_filled_rectangle_prepends_fillpath():
    el = _el(seed=42, backgroundColor="#a5d8ff", fillStyle="solid")
    sets = sh.generate_element_shape(el)
    assert sets[0]["type"] == "fillPath"   # fill drawn under stroke

def test_arrow_appends_two_barb_lines():
    el = _el(type="arrow", width=200, height=0, points=[[0, 0], [200, 0]],
             endArrowhead="arrow", startArrowhead=None, seed=7)
    sets = sh.generate_element_shape(el)
    # 1 stroke path for the shaft + 2 barb line opsets
    assert len(sets) == 3


def test_arrow_double_head_appends_four_barb_lines():
    """Arrow with both start and end 'arrow' heads: shaft + 4 barb lines = 5 sets."""
    el = _el(type="arrow", width=200, height=0, points=[[0, 0], [200, 0]],
             endArrowhead="arrow", startArrowhead="arrow", seed=7)
    sets = sh.generate_element_shape(el)
    # 1 shaft + 2 start barbs + 2 end barbs = 5
    assert len(sets) == 5


def test_arrow_null_start_arrowhead_no_extra_sets():
    """null startArrowhead must NOT produce any arrowhead sets."""
    el = _el(type="arrow", width=200, height=0, points=[[0, 0], [200, 0]],
             endArrowhead="arrow", startArrowhead=None, seed=7)
    sets = sh.generate_element_shape(el)
    # Still exactly shaft + 2 end barbs (same as the original test)
    assert len(sets) == 3


def test_arrow_triangle_end_produces_fill_and_stroke():
    """'triangle' endArrowhead → fillPath + path (filled polygon + rough outline) = 2 extra sets."""
    el = _el(type="arrow", width=200, height=0, points=[[0, 0], [200, 0]],
             endArrowhead="triangle", startArrowhead=None, seed=7)
    sets = sh.generate_element_shape(el)
    # shaft + fillPath (solid fill) + path (rough outline) = 3
    assert len(sets) == 3
    types = [s["type"] for s in sets]
    # At least one fillPath (the filled triangle)
    assert "fillPath" in types


def test_arrow_diamond_end_produces_fill_and_stroke():
    """'diamond' endArrowhead → fillPath + path = 2 extra sets."""
    el = _el(type="arrow", width=200, height=0, points=[[0, 0], [200, 0]],
             endArrowhead="diamond", startArrowhead=None, seed=7)
    sets = sh.generate_element_shape(el)
    # shaft + fillPath + path = 3
    assert len(sets) == 3
    types = [s["type"] for s in sets]
    assert "fillPath" in types


# ---------------------------------------------------------------------------
# Task 4: cross-hatch filler + fillStyle dispatch
# ---------------------------------------------------------------------------
import roughjs

def test_hatch_is_two_hachure_passes():
    sq = [[[0, 0], [100, 0], [100, 100], [0, 100]]]
    o1 = roughjs.resolve_options(seed=1, fillStyle="hachure", hachureGap=10, roughness=0)
    o2 = roughjs.resolve_options(seed=1, fillStyle="cross-hatch", hachureGap=10, roughness=0)
    n_hachure = len(roughjs.hachure_fill_polygon([[list(p) for p in sq[0]]], o1)["ops"])
    n_hatch = len(roughjs.hatch_fill_polygon([[list(p) for p in sq[0]]], o2)["ops"])
    assert n_hatch > n_hachure  # second 90°-rotated pass added


def test_fillstyle_dispatch_hachure_rect():
    """generate_element_shape for hachure rect produces fillSketch (not fillPath)."""
    el = _el(type="rectangle", width=100, height=100,
             backgroundColor="#ff0000", fillStyle="hachure", seed=42)
    sets = sh.generate_element_shape(el)
    types = [s["type"] for s in sets]
    assert "fillSketch" in types, f"Expected fillSketch in {types}"
    assert "fillPath" not in types


def test_fillstyle_dispatch_crosshatch_rect():
    """generate_element_shape for cross-hatch rect produces fillSketch with more ops than single hachure."""
    el_hachure = _el(type="rectangle", width=100, height=100,
                     backgroundColor="#ff0000", fillStyle="hachure", seed=42)
    el_crosshatch = _el(type="rectangle", width=100, height=100,
                        backgroundColor="#ff0000", fillStyle="cross-hatch", seed=42)
    sets_h = sh.generate_element_shape(el_hachure)
    sets_c = sh.generate_element_shape(el_crosshatch)
    fill_h = next(s for s in sets_h if s["type"] == "fillSketch")
    fill_c = next(s for s in sets_c if s["type"] == "fillSketch")
    assert len(fill_c["ops"]) > len(fill_h["ops"]), "cross-hatch must have more ops than hachure"


# ---------------------------------------------------------------------------
# Bug fix: hachure/cross-hatch fill on rounded shapes (Task 5)
# ---------------------------------------------------------------------------

def test_rounded_rect_hachure_fill_has_nonempty_ops():
    """Rounded rectangle with hachure fill must produce a fillSketch with non-empty ops.

    Regression: before the fix, _with_path_fill passed [[]] (empty polygon) to
    fill_polygon, yielding zero hatch lines.
    """
    el = _el(type="rectangle", width=120, height=80,
             backgroundColor="#ff0000", fillStyle="hachure", seed=7,
             roundness={"type": 2})
    sets = sh.generate_element_shape(el)
    fill = next((s for s in sets if s["type"] == "fillSketch"), None)
    assert fill is not None, f"Expected a fillSketch opset in {[s['type'] for s in sets]}"
    assert len(fill["ops"]) > 0, "fillSketch ops must be non-empty for rounded rect with hachure fill"


def test_rounded_diamond_hachure_fill_has_nonempty_ops():
    """Rounded diamond with hachure fill must produce a fillSketch with non-empty ops."""
    el = _el(type="diamond", width=120, height=80,
             backgroundColor="#4dabf7", fillStyle="hachure", seed=13,
             roundness={"type": 2})
    sets = sh.generate_element_shape(el)
    fill = next((s for s in sets if s["type"] == "fillSketch"), None)
    assert fill is not None, f"Expected a fillSketch opset in {[s['type'] for s in sets]}"
    assert len(fill["ops"]) > 0, "fillSketch ops must be non-empty for rounded diamond with hachure fill"


def test_rounded_rect_crosshatch_fill_has_nonempty_ops():
    """Rounded rectangle with cross-hatch fill must produce a fillSketch with non-empty ops."""
    el = _el(type="rectangle", width=120, height=80,
             backgroundColor="#ff0000", fillStyle="cross-hatch", seed=7,
             roundness={"type": 2})
    sets = sh.generate_element_shape(el)
    fill = next((s for s in sets if s["type"] == "fillSketch"), None)
    assert fill is not None, f"Expected a fillSketch opset in {[s['type'] for s in sets]}"
    assert len(fill["ops"]) > 0, "fillSketch ops must be non-empty for rounded rect with cross-hatch fill"
