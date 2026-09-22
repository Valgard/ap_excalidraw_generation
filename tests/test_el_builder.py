import sys; sys.path.insert(0, ".")
import excalidraw_svg as X

def test_void_matches_path_format():
    # must byte-match the current _path_el output shape: "<path d="…" fill="none" />"
    assert X.el("path", {"d": "M0 0", "fill": "none"}, void=True) == '<path d="M0 0" fill="none" />'

def test_nonvoid_and_empty():
    assert X.el("g", {"transform": "t"}, "<path/>") == '<g transform="t"><path/></g>'
    assert X.el("mask") == '<mask></mask>'                 # empty non-void preserved
    assert X.el("use", {"href": "#x"}) == '<use href="#x"></use>'

def test_escapes_attr_values_and_skips_none():
    assert X.el("a", {"href": 'x"&<y', "extra": None}, "t") == '<a href="x&quot;&amp;&lt;y">t</a>'

def test_attr_insertion_order_preserved():
    assert X.el("path", {"a": "1", "b": "2"}, void=True) == '<path a="1" b="2" />'
