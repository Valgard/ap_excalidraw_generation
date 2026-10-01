# test_excalidraw_helpers.py
import excalidraw_helpers as xh


def test_flow_row_positions_with_gaps():
    els = xh.flow_row("f", ["A", "B", "C"], x=80, w=160, gap=100)
    boxes = [e for e in els if e["type"] == "rectangle"]
    assert [b["x"] for b in boxes] == [80, 340, 600]
    assert any(e["type"] == "text" and e.get("containerId") for e in els)


def test_grid_centers():
    cells = xh.grid("g", 2, 2, x=60, y=60, cell_w=200, cell_h=100, gap=20)
    assert cells[(0, 0)] == (160, 110)
    assert cells[(1, 1)] == (380, 230)


def test_panel_card_title_and_bound_rows():
    els = xh.panel("p", title="Vorher", rows=["a", "b"])
    assert els[0]["id"] == "p-panel" and els[0]["type"] == "rectangle"
    assert els[1]["type"] == "text" and els[1]["text"] == "Vorher"
    assert sum(1 for e in els if e["type"] == "rectangle") == 3   # card + 2 rows
    assert sum(1 for e in els if e.get("containerId")) == 2        # 2 bound row labels


def test_columns_builds_header_and_bound_rows():
    els = xh.columns("c", [("Head", ["r1", "r2"])])
    assert els[0]["id"] == "c-c0-h"                          # column header box
    # header label + one bound label per row:
    assert sum(1 for e in els if e.get("containerId")) == 3
    # header box + one box per row:
    assert sum(1 for e in els if e["type"] == "rectangle") == 3


def test_timeline_has_baseline_and_one_dot_per_point():
    els = xh.timeline("t", [("1885",), ("2020",)], x=80, gap=160)
    assert sum(1 for e in els if e["type"] == "line") == 1
    assert sum(1 for e in els if e["type"] == "ellipse") == 2


def test_curve_is_deterministic_function_eval():
    import math
    a = xh.curve("c", lambda t: 100 * math.e ** (-t / 5), 0, 30, n=60)
    b = xh.curve("c", lambda t: 100 * math.e ** (-t / 5), 0, 30, n=60)
    line_a = next(e for e in a if e["type"] == "line")
    line_b = next(e for e in b if e["type"] == "line")
    assert line_a["points"] == line_b["points"]
    assert len(line_a["points"]) == 61


def test_bars_height_from_value():
    els = xh.bars("b", [("x", 10), ("y", 20)], scale=2.0)
    rects = [e for e in els if e["type"] == "rectangle"]
    assert rects[0]["height"] == 20 and rects[1]["height"] == 40
