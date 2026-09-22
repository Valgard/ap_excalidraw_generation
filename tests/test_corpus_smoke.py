# tests/test_corpus_smoke.py
import glob, json, pathlib, sys
sys.path.insert(0, ".")
sys.path.insert(0, "tests")
import pytest, excalidraw_svg
from known_findings import CRASHING_INPUTS, CRASHING_REASON

_RAW_INPUTS = sorted(glob.glob("tests/inputs/**/*.excalidraw", recursive=True))

def _make_param(path):
    stem = pathlib.Path(path).stem
    if stem in CRASHING_INPUTS:
        return pytest.param(path, marks=pytest.mark.xfail(reason=CRASHING_REASON, strict=False), id=stem)
    return pytest.param(path, id=stem)

INPUTS = [_make_param(p) for p in _RAW_INPUTS]

@pytest.mark.parametrize("path", INPUTS)
def test_renders_without_crash(path):
    doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    svg = excalidraw_svg.to_svg(doc)          # findings: a crash here is a recorded gap
    assert svg.startswith("<svg")
