import json
import pathlib
import roughjs
import pytest

FIX = pathlib.Path("tests/fixtures/roughjs")


def _norm(sets):  # rough JSON op → our tuple, rounded to 2 decimals
    out = []
    for s in sets:
        ops = []
        for op in s['ops']:
            ops.append((op['op'], *[round(v, 2) for v in op['data']]))
        out.append({'type': s['type'], 'ops': ops})
    return out


def _ours(opset):
    return [{'type': opset['type'],
             'ops': [(k, *[round(float(v), 2) for v in d]) for (k, *d) in opset['ops']]}]


def test_minstd_sequence_is_deterministic_for_nonzero_seed():
    r = roughjs.Random(42)
    seq = [r.next() for _ in range(3)]
    # MINSTD: seed_{n+1} = imul(48271, seed_n); value = (0x7fffffff & seed) / 2**31
    assert seq[0] == ((2**31 - 1) & (roughjs._imul(48271, 42) & 0xFFFFFFFF)) / 2**31
    r2 = roughjs.Random(42)
    assert [r2.next() for _ in range(3)] == seq   # same seed → same sequence
    assert roughjs.Random(43).next() != seq[0]    # different seed → different


def test_ops_to_path_rounds_to_2_decimals():
    opset = {'type': 'path', 'ops': [('move', 1.239, 2.0), ('lineTo', 3.0, 4.567)]}
    assert roughjs.ops_to_path(opset) == "M1.24 2 L3 4.57"


def test_rectangle_matches_real_roughjs():
    ref = json.loads((FIX / "rect.json").read_text())
    o = roughjs.resolve_options(seed=ref['seed'])
    got = _ours(roughjs.rectangle(0, 0, 160, 60, o))
    assert got == _norm(ref['sets'])


def test_line_matches_real_roughjs():
    ref = json.loads((FIX / "line.json").read_text())
    o = roughjs.resolve_options(seed=ref['seed'])
    got = _ours(roughjs.line(0, 0, 200, 80, o))
    assert got == _norm(ref['sets'])


def test_ellipse_matches_real_roughjs():
    ref = json.loads((FIX / "ellipse.json").read_text())
    o = roughjs.resolve_options(seed=ref['seed'], curveFitting=1)   # Excalidraw sets curveFitting=1
    got = _ours(roughjs.ellipse(60, 60, 120, 120, o))
    assert got == _norm(ref['sets'])


def test_solid_fill_matches_real_roughjs():
    ref = json.loads((FIX / "fill.json").read_text())
    fill_ref = [s for s in ref['sets'] if s['type'] == 'fillPath']
    assert fill_ref, "fixture must contain a fillPath set"
    o = roughjs.resolve_options(seed=ref['seed'], fillStyle='solid')
    # rough.js generator.rectangle() computes the stroke outline FIRST (advancing the
    # shared randomizer), then computes the solid fill.  Reproduce that order so our
    # RNG state matches the state at which the fixture's fillPath ops were generated.
    roughjs.rectangle(0, 0, 100, 100, o)
    got = roughjs.solid_fill_polygon([[[0,0],[100,0],[100,100],[0,100]]], o)
    got_n = [(k, *[round(float(v), 2) for v in d]) for (k, *d) in got['ops']]
    ref_n = [(op['op'], *[round(v, 2) for v in op['data']]) for op in fill_ref[0]['ops']]
    assert got_n == ref_n


def test_hachure_lines_square_angle0_horizontal():
    sq = [[0, 0], [100, 0], [100, 100], [0, 100]]
    lines = roughjs._hachure_lines([sq], 10, 0, 1)
    # every line is horizontal, spans x 0..100, at y in [0,100) — ymin boundary included
    assert lines, "expected hachure lines"
    for (x1, y1), (x2, y2) in lines:
        assert y1 == y2
        assert {x1, x2} == {0, 100}
        assert 0 <= y1 < 100


def test_hachure_fill_matches_reference_rng_order():
    import json
    ref = json.loads(open("tests/fixtures/roughjs/hachure.json").read())
    fill_ref = [s for s in ref['sets'] if s['type'] == 'fillSketch']
    assert fill_ref, "fixture must contain a fillSketch set"
    o = roughjs.resolve_options(**{k: v for k, v in ref['options'].items()
                                   if k in roughjs.DEFAULT_OPTIONS})
    o['seed'] = ref['seed']
    o['randomizer'] = None
    # Reproduce rough.js: stroke outline is generated first, advancing the RNG
    roughjs.rectangle(0, 0, 100, 100, o)
    polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
    got = roughjs.hachure_fill_polygon([polygon], o)
    assert got['type'] == 'fillSketch'
    got_n = [(k, *[round(float(v), 2) for v in d]) for (k, *d) in got['ops']]
    ref_n = [(op['op'], *[round(v, 2) for v in op['data']]) for op in fill_ref[0]['ops']]
    assert got_n == ref_n


def test_empty_polygon_guard_no_raise():
    """fill_polygon and hachure_fill_polygon must not raise on empty/degenerate inputs.

    Guards the IndexError that would occur in _straight_hachure_lines when a polygon
    has 0 or 1 points (v[0]/v[-1] access on an empty list).  Regression: before the
    'if len(v) < 2: continue' guard was added, fill_polygon([[]], o) raised IndexError.
    """
    o = roughjs.resolve_options(seed=1)
    # Empty polygon inside a polygon list — no IndexError, empty ops returned
    result_hachure = roughjs.hachure_fill_polygon([[]], o)
    assert result_hachure['type'] == 'fillSketch'
    assert result_hachure['ops'] == []

    o2 = roughjs.resolve_options(seed=1)
    result_fill = roughjs.fill_polygon([[]], o2)
    assert result_fill['type'] == 'fillSketch'
    assert result_fill['ops'] == []

    # Single-point polygon — also degenerate, must not raise
    o3 = roughjs.resolve_options(seed=1)
    result_single = roughjs.fill_polygon([[[5, 5]]], o3)
    assert result_single['type'] == 'fillSketch'
    assert result_single['ops'] == []
