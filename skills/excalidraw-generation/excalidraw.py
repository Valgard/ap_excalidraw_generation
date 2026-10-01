# excalidraw.py — declarative facade over the deterministic toolkit + helpers.
import excalidraw_helpers as _h
from excalidraw_toolkit import (
    rect as _rect, ellipse as _ellipse, diamond as _diamond, text as _text,
    line as _line, arrow as _arrow, label as _label, connect as _connect,
    group as _group, write_excalidraw as _write,
)
from excalidraw_palette import PALETTE, SEMANTIC, role, TITLE, SUBTITLE  # re-exported atoms

class Diagram:
    def __init__(self, diagram_id):
        self.diagram_id = diagram_id
        self.elements = []

    def _emit(self, result):
        """Append a dict or list-of-dicts; return the primary handle."""
        if isinstance(result, list):
            self.elements.extend(result)
            return result[0] if result else None
        self.elements.append(result)
        return result

    def add(self, *els):
        for e in els:
            self._emit(e)
        return els[0] if els else None

    def _shape(self, fn, id_, x, y, w, h, text, text_font, text_color, kw):
        el = fn(id_, x, y, w, h, **kw)
        self.elements.append(el)
        if text is not None:
            self.elements.append(_label(f"{id_}-t", el, text, font=text_font, color=text_color))
        return el

    def box(self, id_, x, y, w, h, *, text=None, text_font="hand", text_color="#1e1e1e", **kw):
        return self._shape(_rect, id_, x, y, w, h, text, text_font, text_color, kw)

    def ellipse(self, id_, x, y, w, h, *, text=None, text_font="hand", text_color="#1e1e1e", **kw):
        return self._shape(_ellipse, id_, x, y, w, h, text, text_font, text_color, kw)

    def diamond(self, id_, x, y, w, h, *, text=None, text_font="hand", text_color="#1e1e1e", **kw):
        return self._shape(_diamond, id_, x, y, w, h, text, text_font, text_color, kw)

    def text(self, id_, x, y, w, h, content, **kw):
        return self._emit(_text(id_, x, y, w, h, content, **kw))

    def line(self, id_, points, **kw):
        return self._emit(_line(id_, points, **kw))

    def arrow(self, id_, points, **kw):
        return self._emit(_arrow(id_, points, **kw))

    def label(self, id_, container, content, **kw):
        return self._emit(_label(id_, container, content, **kw))

    def connect(self, id_, src, dst, **kw):
        return self._emit(_connect(id_, src, dst, **kw))

    def group(self, group_id, *els):
        return _group(group_id, list(els))   # els already added when created

    def panel(self, prefix, **kw):
        return self._emit(_h.panel(prefix, **kw))

    def flow(self, prefix, labels, **kw):
        out = _h.flow_row(prefix, labels, **kw)
        self.elements.extend(out)
        return [e for e in out if e["type"] == "rectangle"]

    def grid(self, prefix, rows, cols, **kw):
        return _h.grid(prefix, rows, cols, **kw)

    def timeline(self, prefix, points, **kw):
        return self._emit(_h.timeline(prefix, points, **kw))

    def axes(self, prefix="axes", **kw):
        return self._emit(_h.axes(prefix, **kw))

    def bars(self, prefix, data, **kw):
        return self._emit(_h.bars(prefix, data, **kw))

    def curve(self, prefix, fn, t0, t1, **kw):
        return self._emit(_h.curve(prefix, fn, t0, t1, **kw))

    def histogram(self, prefix, values, **kw):
        return self._emit(_h.histogram(prefix, values, **kw))

    def write(self, path):
        return _write(path, self.elements, diagram_id=self.diagram_id)

    def export_png(self, path, *, scale=2, background="light"):
        """Render this diagram to PNG via the uv export script. Writes the .excalidraw
        to a temp file, then shells out to `uv run export.py` so the stdlib-only core
        never imports the rasterizer."""
        import subprocess, tempfile, os, pathlib
        skill_dir = pathlib.Path(__file__).parent
        with tempfile.NamedTemporaryFile("w", suffix=".excalidraw", delete=False) as tf:
            self.write(tf.name); src = tf.name
        try:
            cmd = ["uv", "run", str(skill_dir / "export.py"), src,
                   "-o", str(path), "--scale", str(scale), "--background", background]
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(skill_dir))
            if r.returncode != 0:
                raise RuntimeError(f"export failed: {r.stderr}")
        finally:
            os.unlink(src)
        return str(path)
