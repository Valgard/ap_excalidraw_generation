import json
from pathlib import Path
import excalidraw_toolkit as xt

def test_seed_is_deterministic_and_independent_of_process():
    assert xt.stable_seed("d", "a") == xt.stable_seed("d", "a")
    assert xt.stable_seed("d", "a") != xt.stable_seed("d", "b")
    assert 1 <= xt.stable_seed("d", "a") < 2**31

def test_gen_key_orders_beyond_61():
    keys = [xt.gen_key(i) for i in range(1, 130)]
    assert keys == sorted(keys)            # lexicographic order == array order
    assert len(set(keys)) == len(keys)     # all unique
    assert keys[60] == "az" and keys[61] == "b01"

def test_same_scene_compiles_identically(tmp_path):
    def scene():
        return [xt.base_element("rectangle", "box", 0, 0, 100, 50)]
    a, b = tmp_path / "a.excalidraw", tmp_path / "b.excalidraw"
    xt.write_excalidraw(a, scene(), diagram_id="demo")
    xt.write_excalidraw(b, scene(), diagram_id="demo")
    assert a.read_text() == b.read_text()
    el = json.loads(a.read_text())["elements"][0]
    assert el["seed"] == xt.stable_seed("demo", "box")
    assert el["index"] == "a1"


def test_rect_dashed_and_fill():
    r = xt.rect("r", 0, 0, 10, 10, fill="#a5d8ff", stroke="#1971c2", dashed=True)
    assert r["backgroundColor"] == "#a5d8ff" and r["strokeColor"] == "#1971c2"
    assert r["strokeStyle"] == "dashed" and r["roundness"] == {"type": 3}


def test_text_font_mapping_and_right_align_autoresize():
    assert xt.text("t1", 0, 0, 80, 20, "x", font="code")["fontFamily"] == 3
    assert xt.text("t2", 0, 0, 80, 20, "x", font="hand")["fontFamily"] == 1
    rt = xt.text("t3", 0, 0, 80, 20, "x", align="right")
    assert rt["autoResize"] is False


def test_label_binds_reciprocally_and_centers():
    box = xt.rect("box", 80, 20, 220, 60)
    t = xt.label("box-t", box, "Debug", font="code", font_size=24)
    assert t["containerId"] == "box"
    assert {"id": "box-t", "type": "text"} in box["boundElements"]
    assert t["x"] == 95 and t["width"] == 190
    assert t["y"] + t["height"] / 2 == box["y"] + box["height"] / 2


def test_connect_anchors_to_facing_edges_and_binds_both():
    a = xt.rect("a", 80, 20, 220, 60)      # bottom-center = (190, 80)
    b = xt.diamond("b", 120, 140, 140, 80) # top-center    = (190, 140)
    out = xt.connect("a-b", a, b)
    arr = out[0]
    assert arr["x"] == 190 and arr["y"] == 80
    assert arr["points"] == [[0, 0], [0, 60]]
    assert arr["startBinding"] == {"elementId": "a", "focus": 0, "gap": 1}
    assert arr["endBinding"] == {"elementId": "b", "focus": 0, "gap": 1}
    assert {"id": "a-b", "type": "arrow"} in a["boundElements"]
    assert {"id": "a-b", "type": "arrow"} in b["boundElements"]

def test_connect_label_returns_extra_text():
    a = xt.rect("a", 0, 0, 100, 60)
    b = xt.rect("b", 300, 0, 100, 60)
    out = xt.connect("a-b", a, b, label="step", dashed=True)
    assert len(out) == 2 and out[0]["strokeStyle"] == "dashed"
    assert out[1]["type"] == "text" and out[1]["text"] == "step"

def test_arrow_points_are_relative_and_curved_roundness():
    a = xt.arrow("ar", [[100, 100], [150, 100], [150, 160]], curved=True)
    assert a["x"] == 100 and a["y"] == 100
    assert a["points"] == [[0, 0], [50, 0], [50, 60]]
    assert a["roundness"] == {"type": 2}

def test_line_straight_has_no_roundness():
    ln = xt.line("ln", [[0, 0], [200, 0]])
    assert ln["points"] == [[0, 0], [200, 0]] and ln["roundness"] is None

def test_group_tags_all_members():
    els = [xt.line("l1", [[0, 0], [10, 0]]), xt.ellipse("e1", 0, 0, 8, 8)]
    out = xt.group("icon-lock", els)
    assert all("icon-lock" in e["groupIds"] for e in out)


def test_validator_flags_dangling_binding(tmp_path):
    box = xt.rect("box", 0, 0, 100, 60)
    box["boundElements"] = [{"id": "missing", "type": "text"}]  # no such element
    p = tmp_path / "bad.excalidraw"
    xt.write_excalidraw(p, [box], diagram_id="d")
    probs = xt.validate_file(p)
    assert any("dangling" in s or "missing" in s for s in probs)


def test_validator_passes_clean_bound_scene(tmp_path):
    box = xt.rect("box", 0, 0, 220, 60)
    t = xt.label("box-t", box, "Hi")
    p = tmp_path / "ok.excalidraw"
    xt.write_excalidraw(p, [box, t], diagram_id="d")
    assert xt.validate_file(p) == []


def test_validator_flags_dangling_container_id(tmp_path):
    box = xt.rect("box", 0, 0, 220, 60)
    t = xt.label("t", box, "Hi")
    t["containerId"] = "ghost"          # points at no element
    p = tmp_path / "bad.excalidraw"
    xt.write_excalidraw(p, [box, t], diagram_id="d")
    probs = xt.validate_file(p)
    assert any("containerId" in s or "ghost" in s for s in probs)


def test_arrow_has_binding_fields_line_does_not():
    a = xt.arrow("a", [[0, 0], [10, 0]])
    ln = xt.line("l", [[0, 0], [10, 0]])
    assert "startBinding" in a and "elbowed" in a and a["endArrowhead"] == "arrow"
    assert "startBinding" not in ln and "elbowed" not in ln


def test_validator_flags_dangling_start_binding(tmp_path):
    a = xt.rect("a", 0, 0, 100, 60)
    b = xt.rect("b", 300, 0, 100, 60)
    out = xt.connect("a-b", a, b)
    arr = out[0]
    arr["startBinding"]["elementId"] = "ghost"        # break the start binding
    p = tmp_path / "bad.excalidraw"
    xt.write_excalidraw(p, [a, b, arr], diagram_id="d")
    assert any("startBinding" in s or "ghost" in s for s in xt.validate_file(p))


def test_primitives_accept_roughness():
    assert xt.rect("r", 0, 0, 10, 10, roughness=0)["roughness"] == 0
    assert xt.ellipse("e", 0, 0, 10, 10, roughness=0)["roughness"] == 0
    assert xt.diamond("d", 0, 0, 10, 10, roughness=0)["roughness"] == 0
    assert xt.line("l", [[0, 0], [10, 0]], roughness=0)["roughness"] == 0
    assert xt.arrow("a", [[0, 0], [10, 0]], roughness=0)["roughness"] == 0
    assert xt.rect("r2", 0, 0, 10, 10)["roughness"] == 1   # default unchanged
