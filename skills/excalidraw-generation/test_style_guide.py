import os


def _doc():
    return open(os.path.join(os.path.dirname(__file__), "style-guide.md"), encoding="utf-8").read()


def test_style_guide_has_required_sections_and_styles():
    txt = _doc()
    for heading in ["Base atoms", "Choosing a style", "Sketch", "Minimal"]:
        assert heading in txt, f"missing section/style: {heading}"


def test_style_guide_references_the_atoms():
    txt = _doc()
    assert "PALETTE" in txt and "SEMANTIC" in txt and "role(" in txt


def test_style_guide_covers_every_sketch_archetype():
    txt = _doc().lower()
    for arch in ["flow", "layered", "card", "timeline", "chart", "illustration"]:
        assert arch in txt, f"archetype not documented: {arch}"


def test_skill_md_points_at_the_style_layer():
    txt = open(os.path.join(os.path.dirname(__file__), "SKILL.md"), encoding="utf-8").read()
    assert "style-guide.md" in txt and "excalidraw_palette" in txt
