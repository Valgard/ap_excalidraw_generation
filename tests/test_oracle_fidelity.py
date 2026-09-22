# tests/test_oracle_fidelity.py
import glob, json, pathlib, sys
sys.path.insert(0,"."); sys.path.insert(0,"tools")
import excalidraw_svg
from svg_compare import sub_font_block, diff

def compare_input(inp_path, oracle_dir="tests/oracle"):
    p = pathlib.Path(inp_path); key = f"{p.parent.name}/{p.stem}"
    master = pathlib.Path(oracle_dir)/f"{key}.svg"
    if not master.exists(): return {"key":key,"status":"no-master"}
    try: ours = sub_font_block(excalidraw_svg.to_svg(json.loads(p.read_text())))
    except Exception as e: return {"key":key,"status":"our-crash","error":str(e)}
    d = diff(ours, sub_font_block(master.read_text()))  # both sides font-factored → symmetric
    return {"key":key,"status":"match" if d["byte_equal"] or (d["path_count_ok"] and d["viewbox_ok"]) else "diff",
            "first_divergence":d.get("first_divergence")}

def build_report(oracle_dir="tests/oracle"):
    return [compare_input(p, oracle_dir) for p in sorted(glob.glob("tests/inputs/**/*.excalidraw", recursive=True))]

def test_compare_categorises(tmp_path):
    # synthetic: one input, a matching master → status match; crashing handled
    inp = tmp_path/"atomic"; inp.mkdir(parents=True)
    scene = {"type":"excalidraw","version":2,"elements":[{"id":"d","type":"diamond","x":0,"y":0,"width":80,"height":60,"angle":0,"strokeColor":"#1e1e1e","backgroundColor":"transparent","fillStyle":"solid","strokeWidth":2,"strokeStyle":"solid","roughness":1,"opacity":100,"groupIds":[],"frameId":None,"roundness":None,"seed":1,"version":1,"versionNonce":1,"isDeleted":False,"boundElements":None,"updated":1,"link":None,"locked":False,"index":"a0"}],"appState":{},"files":{}}
    (inp/"diamond.excalidraw").write_text(json.dumps(scene))
    ours = sub_font_block(excalidraw_svg.to_svg(scene))
    od = tmp_path/"oracle"/"atomic"; od.mkdir(parents=True); (od/"diamond.svg").write_text(ours)  # identical → match
    r = compare_input(str(inp/"diamond.excalidraw"), str(tmp_path/"oracle"))
    assert r["status"]=="match"

    # de-tautologise: prove diff category is reachable
    # Build a master that is structurally different (extra <path>) → must yield "diff"
    import xml.etree.ElementTree as ET
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root = ET.fromstring(ours)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    extra = ET.SubElement(root, "{http://www.w3.org/2000/svg}path")
    extra.set("d", "M0 0L9 9")
    mutated = ET.tostring(root, encoding="unicode")
    (od/"diamond.svg").write_text(mutated)   # overwrite with structurally different master
    r2 = compare_input(str(inp/"diamond.excalidraw"), str(tmp_path/"oracle"))
    assert r2["status"] == "diff", f"Expected diff for mutated master, got {r2['status']!r}"

if __name__ == "__main__":
    import collections
    rep = build_report(); tally = collections.Counter(r["status"] for r in rep)
    print(json.dumps({"tally":dict(tally),"report":rep}, indent=2))
