# tools/mint_pindown.py
"""Mint pin-down goldens from OUR OWN to_svg output. Run: uv run python tools/mint_pindown.py"""
import sys, glob, json, pathlib
sys.path.insert(0, ".")
sys.path.insert(0, "tools")
sys.path.insert(0, "tests")
import excalidraw_svg, fonts
from svg_compare import sub_font_block
from known_findings import CRASHING_INPUTS

OUT = pathlib.Path("tests/pindown")

def mint():
    (OUT / "atomic").mkdir(parents=True, exist_ok=True)
    (OUT / "integration").mkdir(parents=True, exist_ok=True)
    (OUT / "_fonts.svg").write_text(fonts.font_face_css(), encoding="utf-8")
    n = 0
    for path in sorted(glob.glob("tests/inputs/**/*.excalidraw", recursive=True)):
        p = pathlib.Path(path); stem = p.stem; tier = p.parent.name  # atomic | integration
        if stem in CRASHING_INPUTS:
            continue  # recorded finding — no golden
        doc = json.loads(p.read_text(encoding="utf-8"))
        svg = sub_font_block(excalidraw_svg.to_svg(doc))
        (OUT / tier / f"{stem}.svg").write_text(svg, encoding="utf-8")
        n += 1
    print(f"minted {n} goldens + _fonts.svg")

if __name__ == "__main__":
    mint()
