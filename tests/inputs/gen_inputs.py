# Generates the canonical .excalidraw inputs via the real toolkit (fixed ids → fixed seeds).
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # skill root
from excalidraw import Diagram

OUT = pathlib.Path(__file__).parent / "atomic"
OUT.mkdir(exist_ok=True)

def emit(name, build):
    """build(d): mutate a Diagram; writes atomic/<name>.excalidraw."""
    from excalidraw import Diagram
    d = Diagram(name)
    build(d)
    d.write(str(OUT / f"{name}.excalidraw"))
    print("wrote", name)

def ellipse_dashed():
    d = Diagram("fix-ellipse-dashed")
    d.ellipse("e", 0, 0, 120, 120, dashed=True)
    return d

def diamond_plain():
    d = Diagram("fix-diamond"); d.diamond("dm", 0, 0, 140, 80); return d

def text_multiline():
    d = Diagram("fix-text")
    d.text("t", 0, 0, 200, 60, "line one\nline two", font="hand", font_size=20)
    return d

for name, fn in [("ellipse-dashed", ellipse_dashed),
                 ("diamond", diamond_plain), ("text", text_multiline)]:
    fn().write(str(OUT / f"{name}.excalidraw"))
    print("wrote", name)

def gen_line():
    emit("line-plain", lambda d: d.line("l", [(0,0),(160,0)]))

def gen_arrowheads():
    heads = ["bar","circle","circle_outline","triangle_outline","diamond",
        "diamond_outline","cardinality_one","cardinality_many","cardinality_one_or_many",
        "cardinality_exactly_one","cardinality_zero_or_one","cardinality_zero_or_many","dot"]
    for ah in heads:
        def build(d, ah=ah):
            a = d.arrow("a", [(0,0),(160,0)]); a["endArrowhead"] = ah
        emit(f"arrowhead-{ah}", build)
    def both(d):
        a = d.arrow("a", [(0,0),(160,0)]); a["startArrowhead"]="dot"; a["endArrowhead"]="triangle"
    emit("arrowhead-both", both)

gen_line()
gen_arrowheads()

def gen_scaffolding():
    def fill(style):
        def b(d):
            e=d.box("r",0,0,160,80); e["backgroundColor"]="#a5d8ff"; e["fillStyle"]=style
        return b
    emit("fill-crosshatch", fill("cross-hatch"))
    emit("fill-zigzag",     fill("zigzag"))
    emit("stroke-dotted",   lambda d: d.box("r",0,0,160,80).__setitem__("strokeStyle","dotted"))
    def legacy(d):
        e=d.box("r",0,0,160,80); e["roundness"]={"type":1}
    emit("roundness-legacy", legacy)
    for v in (0,2):
        emit(f"roughness-{v}", (lambda v: lambda d: d.box("r",0,0,160,80).__setitem__("roughness",v))(v))
    emit("strokewidth-thin", lambda d: d.box("r",0,0,160,80).__setitem__("strokeWidth",1))
    emit("strokewidth-bold", lambda d: d.box("r",0,0,160,80).__setitem__("strokeWidth",4))
    emit("opacity-50", lambda d: d.box("r",0,0,160,80).__setitem__("opacity",50))

gen_scaffolding()

def gen_text_and_image():
    for code in (2,3,5,6,7,8,9,10):
        emit(f"font-{code}", (lambda code: lambda d: d.text("t",0,0,140,40,"Ag 123").__setitem__("fontFamily",code))(code))
    emit("valign-bottom", lambda d: d.text("t",0,0,140,80,"Ag").__setitem__("verticalAlign","bottom"))
    def boundline(d):
        ln = d.line("ln",[(0,0),(200,0)])
        d.label("lbl", ln, "x")   # bound text on the line (verticalAlign=top path)
    emit("boundtext-line", boundline)
    # image-crop: no d.image() facade — hand-JSON path
    # Copy atomic/image.excalidraw structure and add crop key
    import json as _json
    src = _json.loads((OUT / "image.excalidraw").read_text())
    # Build the hand-JSON document
    im_el = dict(src["elements"][0])  # copy the image element
    W, H = im_el["width"], im_el["height"]  # 120, 120
    im_el["crop"] = {"x": 0, "y": 0, "width": W // 2, "height": H // 2,
                     "naturalWidth": W, "naturalHeight": H}
    doc = {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": [im_el],
        "appState": src["appState"],
        "files": src["files"],
    }
    (OUT / "image-crop.excalidraw").write_text(_json.dumps(doc, indent=2))
    print("wrote image-crop")

gen_text_and_image()

def gen_bundle_atoms():
    def solid(d):
        e=d.box("r",0,0,160,80); e["backgroundColor"]="#a5d8ff"; e["fillStyle"]="solid"
    emit("fill-solid", solid)
    emit("rotation", lambda d: d.box("r",0,0,160,80).__setitem__("angle",0.4))
    emit("boundtext-shape", lambda d: d.box("r",0,0,160,80, text="Hi"))

gen_bundle_atoms()

def gen_elbow():
    def b(d):
        a = d.arrow("elb", [(0,0),(120,0),(120,80)]); a["elbowed"] = True
    emit("elbow-arrow", b)

gen_elbow()
