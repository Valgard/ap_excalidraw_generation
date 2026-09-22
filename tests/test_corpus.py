import glob
def test_corpus_is_two_tier():
    atomic = glob.glob("tests/inputs/atomic/*.excalidraw")
    integration = glob.glob("tests/inputs/integration/*.excalidraw")
    assert atomic, "no atomic inputs found"
    assert {p.split("/")[-1] for p in integration} >= {
        "atkinson-shiffrin-de.excalidraw", "memgpt-tiers-de.excalidraw",
        "user-segmentation-de.excalidraw"}
    # flat tests/inputs/ must no longer hold .excalidraw files directly
    assert not glob.glob("tests/inputs/*.excalidraw")

import json, pathlib
def _el(name):
    doc = json.loads(pathlib.Path(f"tests/inputs/atomic/{name}.excalidraw").read_text(encoding="utf-8"))
    return doc["elements"]
ARROWHEADS = ["bar","circle","circle_outline","triangle_outline","diamond",
    "diamond_outline","cardinality_one","cardinality_many","cardinality_one_or_many",
    "cardinality_exactly_one","cardinality_zero_or_one","cardinality_zero_or_many","dot"]
def test_line_plain():
    assert any(e["type"]=="line" for e in _el("line-plain"))
import pytest
@pytest.mark.parametrize("ah", ARROWHEADS)
def test_arrowhead(ah):
    arr = [e for e in _el(f"arrowhead-{ah}") if e["type"]=="arrow"][0]
    assert arr["endArrowhead"] == ah
def test_arrowhead_both():
    arr = [e for e in _el("arrowhead-both") if e["type"]=="arrow"][0]
    assert arr["startArrowhead"] and arr["endArrowhead"]

def test_fill_crosshatch():
    e=[x for x in _el("fill-crosshatch") if x["type"]=="rectangle"][0]
    assert e["fillStyle"]=="cross-hatch" and e["backgroundColor"]!="transparent"
def test_fill_zigzag():
    e=[x for x in _el("fill-zigzag") if x["type"]=="rectangle"][0]
    assert e["fillStyle"]=="zigzag"
def test_stroke_dotted():
    assert [x for x in _el("stroke-dotted") if x["type"]=="rectangle"][0]["strokeStyle"]=="dotted"
def test_roundness_legacy():
    r=[x for x in _el("roundness-legacy") if x["type"]=="rectangle"][0]["roundness"]
    assert r and r["type"]==1
def test_roughness():
    for v in (0,2):
        assert [x for x in _el(f"roughness-{v}")][0]["roughness"]==v
def test_strokewidth():
    assert [x for x in _el("strokewidth-thin") if x["type"]=="rectangle"][0]["strokeWidth"]==1
    assert [x for x in _el("strokewidth-bold") if x["type"]=="rectangle"][0]["strokeWidth"]==4
def test_opacity():
    assert [x for x in _el("opacity-50")][0]["opacity"]==50

FONT_CODES=[2,3,5,6,7,8,9,10]
@pytest.mark.parametrize("code", FONT_CODES)
def test_font(code):
    t=[x for x in _el(f"font-{code}") if x["type"]=="text"][0]
    assert t["fontFamily"]==code
def test_valign_bottom():
    t=[x for x in _el("valign-bottom") if x["type"]=="text"][0]
    assert t["verticalAlign"]=="bottom"
def test_bound_text_on_line():
    els=_el("boundtext-line")
    assert any(e["type"] in ("line","arrow") for e in els) and any(e["type"]=="text" and e.get("containerId") for e in els)
def test_image_crop():
    im=[x for x in _el("image-crop") if x["type"]=="image"][0]
    assert im.get("crop")

def test_magicframe():
    assert any(e["type"]=="magicframe" for e in _el("magicframe"))
def test_iframe():
    assert any(e["type"]=="iframe" for e in _el("iframe"))
def test_frame_rotated():
    f=[e for e in _el("frame-rotated") if e["type"]=="frame"][0]
    assert f["angle"]!=0 and f.get("name")
def test_frame_populated():
    els=_el("frame-populated"); f=[e for e in els if e["type"]=="frame"][0]
    assert any(e.get("frameId")==f["id"] for e in els if e["type"]!="frame")

def test_fill_solid():
    e=[x for x in _el("fill-solid") if x["type"]=="rectangle"][0]
    assert e["fillStyle"]=="solid" and e["backgroundColor"]!="transparent"
def test_rotation():
    assert [x for x in _el("rotation") if x["type"]=="rectangle"][0]["angle"]!=0
def test_boundtext_shape():
    els=_el("boundtext-shape")
    assert any(e["type"]=="text" and e.get("containerId") for e in els)
def test_bundles_retired():
    import glob
    for stem in ("rect-fill","rotated-box","arrow"):
        assert not glob.glob(f"tests/inputs/atomic/{stem}.excalidraw")
    # atomic replacements for the retired bundles must exist
    assert glob.glob("tests/inputs/atomic/fill-solid.excalidraw"), "fill-solid.excalidraw missing"
    assert glob.glob("tests/inputs/atomic/rotation.excalidraw"), "rotation.excalidraw missing"
    assert glob.glob("tests/inputs/atomic/boundtext-shape.excalidraw"), "boundtext-shape.excalidraw missing"

def test_elbow_arrow():
    a = [e for e in _el("elbow-arrow") if e["type"]=="arrow"][0]
    assert a.get("elbowed") is True
