# test_check_appstate.py — verdict logic for the appState/churn classifier.
import copy

import check_appstate as ca


def _doc(elements, appstate=None):
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "test",
        "elements": elements,
        "appState": appstate or {"gridSize": None, "viewBackgroundColor": "#fff"},
        "files": {},
    }


def _el(eid, **kw):
    base = {"id": eid, "type": "rectangle", "x": 0.0, "y": 0.0, "width": 100.0,
            "height": 50.0, "angle": 0, "groupIds": [], "text": None,
            "version": 1, "versionNonce": 111, "seed": 222, "index": "a0"}
    base.update(kw)
    return base


# --- base fixtures ---------------------------------------------------------

def _grouped_pair():
    """Two elements sharing one group."""
    return [_el("A", groupIds=["G1"]), _el("B", x=200.0, groupIds=["G1"])]


# --- verdicts --------------------------------------------------------------

def test_unchanged():
    d = _doc(_grouped_pair())
    assert ca.classify(d, copy.deepcopy(d))["verdict"] == "UNCHANGED"


def test_appstate_only():
    old = _doc(_grouped_pair(), {"gridSize": None})
    new = _doc(copy.deepcopy(old["elements"]), {"gridSize": 20, "zoom": 1.5})  # more keys
    res = ca.classify(old, new)
    assert res["verdict"] == "APPSTATE-ONLY"
    assert res["appstate_changed"] is True


def test_churn_volatile_and_index():
    old = _doc(_grouped_pair())
    new = copy.deepcopy(old)
    for e in new["elements"]:
        e["version"] += 7
        e["versionNonce"] = 999
        e["seed"] = 888
        e["index"] = "b2q"  # fractional-index reassignment
    assert ca.classify(old, new)["verdict"] == "CHURN-ONLY"


def test_churn_subpixel_drift_under_eps():
    old = _doc(_grouped_pair())
    new = copy.deepcopy(old)
    new["elements"][0]["y"] = 0.0865  # < default eps 0.5
    assert ca.classify(old, new)["verdict"] == "CHURN-ONLY"


def test_churn_group_label_rename_same_partition():
    old = _doc(_grouped_pair())
    new = copy.deepcopy(old)
    for e in new["elements"]:
        e["groupIds"] = ["G-RENAMED"]  # same members, new label
    res = ca.classify(old, new)
    assert res["verdict"] == "CHURN-ONLY"
    assert res["partition_changed"] is False


def test_churn_reorder():
    old = _doc(_grouped_pair())
    new = copy.deepcopy(old)
    new["elements"].reverse()  # array reordered, ids unchanged
    assert ca.classify(old, new)["verdict"] == "CHURN-ONLY"


def test_real_text_edit():
    old = _doc([_el("A", type="text", text="Channels", originalText="Channels")])
    new = copy.deepcopy(old)
    new["elements"][0]["text"] = "⚠️ Channels"
    new["elements"][0]["originalText"] = "⚠️ Channels"
    res = ca.classify(old, new)
    assert res["verdict"] == "REAL-EDIT"
    assert "text" in res["field_changes"]["A"]


def test_real_element_removed_isdeleted_flips():
    old = _doc([_el("A"), _el("emoji", type="text", text="⚠️")])
    new = copy.deepcopy(old)
    new["elements"][1]["isDeleted"] = True
    new["elements"][1]["text"] = ""
    assert ca.classify(old, new)["verdict"] == "REAL-EDIT"


def test_real_partition_change_member_leaves_group():
    old = _doc(_grouped_pair())  # A and B share G1
    new = copy.deepcopy(old)
    new["elements"][1]["groupIds"] = []  # B leaves the group -> partition changes
    res = ca.classify(old, new)
    assert res["verdict"] == "REAL-EDIT"
    assert res["partition_changed"] is True


def test_real_element_added():
    old = _doc([_el("A")])
    new = _doc([_el("A"), _el("C")])
    res = ca.classify(old, new)
    assert res["verdict"] == "REAL-EDIT"
    assert res["added"] == ["C"]


def test_real_geometry_move_over_eps():
    old = _doc([_el("A")])
    new = copy.deepcopy(old)
    new["elements"][0]["x"] = 40.0  # >> eps
    assert ca.classify(old, new)["verdict"] == "REAL-EDIT"


def test_eps_boundary_is_configurable():
    old = _doc([_el("A")])
    new = copy.deepcopy(old)
    new["elements"][0]["y"] = 2.0
    assert ca.classify(old, new, eps=0.5)["verdict"] == "REAL-EDIT"
    assert ca.classify(old, new, eps=5.0)["verdict"] == "CHURN-ONLY"
