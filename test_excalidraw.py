# test_excalidraw.py
import json
from excalidraw import Diagram

def test_diagram_accumulates_and_writes(tmp_path):
    d = Diagram("demo")
    a = d.box("a", 0, 0, 100, 60, text="A")
    b = d.box("b", 300, 0, 100, 60, text="B")
    d.connect("a-b", a, b, dashed=True)
    p = tmp_path / "demo.excalidraw"
    assert d.write(p) == []          # validates clean
    ids = {e["id"] for e in json.loads(p.read_text())["elements"]}
    assert ids >= {"a", "a-t", "b", "b-t", "a-b"}

def test_panel_handle_is_connectable(tmp_path):
    d = Diagram("cmp")
    before = d.panel("before", title="Vorher", rows=["x 7/10"])
    after = d.panel("after", x=560, title="Nachher", rows=["x 9/10"])
    d.connect("flow", before, after, label="step")
    assert d.write(tmp_path / "c.excalidraw") == []

def test_two_unbound_panels_need_no_connection(tmp_path):
    d = Diagram("two")
    d.panel("a", title="A", rows=["1"])
    d.panel("b", x=560, title="B", rows=["2"])
    assert d.write(tmp_path / "two.excalidraw") == []   # no arrow required

def test_group_does_not_reappend():
    d = Diagram("g")
    a = d.box("a", 0, 0, 50, 30)
    b = d.box("b", 100, 0, 50, 30)
    n = len(d.elements)
    out = d.group("grp", a, b)
    assert len(d.elements) == n                       # group must NOT duplicate elements
    assert all("grp" in e["groupIds"] for e in out)

def test_grid_returns_dict_without_appending():
    d = Diagram("g2")
    n = len(d.elements)
    cells = d.grid("g", 2, 2)
    assert isinstance(cells, dict)
    assert len(d.elements) == n                        # grid emits no elements

def test_examples_build_and_validate_clean(tmp_path):
    import runpy, glob, os
    here = os.path.dirname(__file__)
    examples = sorted(glob.glob(os.path.join(here, "examples", "*.py")))
    assert examples, "examples/ is empty — smoke test would be vacuous"
    for ex in examples:
        ns = runpy.run_path(ex)
        out = tmp_path / (os.path.basename(ex) + ".excalidraw")
        assert ns["make"]().write(out) == [], ex

def test_palette_atoms_importable_from_facade():
    import excalidraw
    assert hasattr(excalidraw, "PALETTE") and hasattr(excalidraw, "SEMANTIC")
    assert excalidraw.role("success") == {"fill": "#b2f2bb", "stroke": "#2f9e44"}

def test_minimal_example_validates_clean(tmp_path):
    import runpy, os
    ns = runpy.run_path(os.path.join(os.path.dirname(__file__), "examples", "minimal_matrix.py"))
    assert ns["make"]().write(tmp_path / "m.excalidraw") == []

def test_box_text_font_and_color_forward_to_label():
    d = Diagram("tf")
    d.box("h", 0, 0, 100, 40, text="Hdr", text_font="normal", text_color="#ffffff")
    lbl = next(e for e in d.elements if e.get("containerId") == "h")
    assert lbl["fontFamily"] == 5 and lbl["strokeColor"] == "#ffffff"

def test_box_text_label_defaults_unchanged():
    d = Diagram("tf2")
    d.box("b", 0, 0, 100, 40, text="x")
    lbl = next(e for e in d.elements if e.get("containerId") == "b")
    assert lbl["fontFamily"] == 1 and lbl["strokeColor"] == "#1e1e1e"


def test_box_forwards_roughness_kwarg():
    d = Diagram("rr")
    box = d.box("b", 0, 0, 100, 40, roughness=0)
    assert box["roughness"] == 0

def test_export_png_shells_out_and_writes_file(tmp_path, monkeypatch):
    import pathlib
    calls = {}
    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        pathlib.Path(cmd[cmd.index("-o")+1]).write_bytes(b"\x89PNG\r\n\x1a\n")
        class R: returncode = 0; stderr = ""
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    d = Diagram("t"); d.box("b", 0, 0, 100, 40, text="hi")
    out = d.export_png(str(tmp_path / "d.png"))
    assert "export.py" in " ".join(calls["cmd"]) and "uv" in calls["cmd"][0]
    assert pathlib.Path(out).exists()
