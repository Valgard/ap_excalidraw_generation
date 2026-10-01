# tests/test_pindown_helpers.py
import sys, pathlib
sys.path.insert(0, "tools")
import svg_compare as sc


def test_sub_font_block_replaces_inner_only():
    svg = '<svg><defs><style class="style-fonts">@font-face{src:url(AAAA)}</style></defs><path d="M0 0"/></svg>'
    out = sc.sub_font_block(svg)
    assert '<style class="style-fonts">@@FONTS@@</style>' in out
    assert 'AAAA' not in out
    assert '<path d="M0 0"/>' in out            # everything else byte-identical
    assert out.replace('@@FONTS@@', '@font-face{src:url(AAAA)}') == svg


def test_first_divergence():
    assert sc.first_divergence("abc", "abc") is None
    d = sc.first_divergence("abcXe", "abcYe")
    assert d is not None and "3" in d            # index of first differing char
