# Minimal-style demo: semantic colour-block rows via role().
from excalidraw import Diagram, role

ROWS = [
    ("Cascading Decision Error", "danger"),
    ("Consistency Collapse", "warning"),
    ("Detected by PAEF", "success"),
]

def make():
    d = Diagram("minimal-matrix-demo")
    y = 40
    for i, (label, r) in enumerate(ROWS):
        d.box(f"cell-{i}", 40, y, 360, 56, **role(r), text=label, text_font="normal")
        y += 72
    return d

if __name__ == "__main__":
    make().write("minimal_matrix.excalidraw")
