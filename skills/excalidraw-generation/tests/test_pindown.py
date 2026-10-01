# tests/test_pindown.py
import sys, glob, json, pathlib
sys.path.insert(0, "."); sys.path.insert(0, "tools"); sys.path.insert(0, "tests")
import pytest, excalidraw_svg, fonts
from svg_compare import sub_font_block, first_divergence
from known_findings import CRASHING_INPUTS, CRASHING_REASON

_RAW = sorted(glob.glob("tests/inputs/**/*.excalidraw", recursive=True))
def _param(path):
    stem = pathlib.Path(path).stem
    if stem in CRASHING_INPUTS:
        return pytest.param(path, marks=pytest.mark.xfail(reason=CRASHING_REASON, strict=False), id=stem)
    return pytest.param(path, id=stem)

@pytest.mark.parametrize("path", [_param(p) for p in _RAW])
def test_pindown_byte_exact(path):
    p = pathlib.Path(path); tier = p.parent.name
    golden = pathlib.Path(f"tests/pindown/{tier}/{p.stem}.svg")
    assert golden.exists(), f"no pin-down golden for {p.stem} (re-run tools/mint_pindown.py)"
    got = sub_font_block(excalidraw_svg.to_svg(json.loads(p.read_text(encoding="utf-8"))))
    want = golden.read_text(encoding="utf-8")
    assert got == want, first_divergence(got, want)

def test_pindown_font_block():
    assert fonts.font_face_css() == pathlib.Path("tests/pindown/_fonts.svg").read_text(encoding="utf-8")
