"""Tests for export_options: ExportOptions dataclass + resolve() precedence chain."""
import export_options as eo


def test_precedence_explicit_over_appstate_over_default():
    doc = {"appState": {"viewBackgroundColor": "#abcdef", "exportPadding": 20}}
    # default when neither present
    assert eo.resolve({"appState": {}}).export_padding == 10
    assert eo.resolve({"appState": {}}).view_background_color == "#ffffff"
    # appState inherited
    r = eo.resolve(doc)
    assert r.view_background_color == "#abcdef" and r.export_padding == 20
    # explicit overrides appState
    r2 = eo.resolve(doc, export_padding=3, view_background_color="#000000")
    assert r2.export_padding == 3 and r2.view_background_color == "#000000"


def test_defaults():
    r = eo.resolve({})
    assert (r.export_background, r.export_scale, r.export_with_dark_mode) == (True, 1, False)


import json, excalidraw_svg, export_options


def test_to_svg_backcompat_and_options_equivalent():
    doc = {"type": "excalidraw", "elements": [], "appState": {"viewBackgroundColor": "#ffffff"}}
    a = excalidraw_svg.to_svg(doc)  # legacy default
    b = excalidraw_svg.to_svg(doc, options=export_options.resolve(doc))
    assert a == b
