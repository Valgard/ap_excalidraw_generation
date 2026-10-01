"""Dev-time comparator: our to_svg vs @excalidraw/utils reference SVG.
Byte-exact on geometry/structure after normalisation (whitespace, font-style block,
semantic font-family). NOT used at runtime."""
import re

# ---------------------------------------------------------------------------
# Pin-down helpers (byte-exact, no tolerance)
# ---------------------------------------------------------------------------

FONT_SENTINEL = "@@FONTS@@"
# NOTE: substitution assumes the tag/class `<style class="style-fonts">` stays stable;
# if a future exporter change alters it, the sub silently stops matching and the raw
# font blob lands in goldens (surfaces as re-mint bloat, not a silent pass).
_FONT_BLOCK_RE = re.compile(r'(<style class="style-fonts">).*?(</style>)', re.DOTALL)


def sub_font_block(svg: str) -> str:
    """Replace the inner text of the style-fonts <style> with FONT_SENTINEL, byte-exact elsewhere."""
    return _FONT_BLOCK_RE.sub(r'\1' + FONT_SENTINEL + r'\2', svg)


def first_divergence(a: str, b: str):
    """Return a short description of the first differing char, or None if equal."""
    if a == b:
        return None
    n = min(len(a), len(b))
    i = next((k for k in range(n) if a[k] != b[k]), n)
    lo = max(0, i - 30)
    return f"char[{i}]: ours={a[lo:i+30]!r} golden={b[lo:i+30]!r}"

_FONT_STYLE = re.compile(r'<style class="style-fonts">.*?</style>', re.S)
_WS = re.compile(r"\s+")
_PATH_D = re.compile(r'<path\b[^>]*\bd="([^"]*)"')
_TEXT = re.compile(r'<text\b([^>]*)>(.*?)</text>', re.S)

def normalize(svg: str) -> str:
    svg = _FONT_STYLE.sub("", svg)
    return _WS.sub(" ", svg).strip()

def _path_ds(svg: str):
    return _PATH_D.findall(svg)

def _texts(svg: str):
    out = []
    for m in _TEXT.finditer(svg):
        attrs, body = m.group(1), m.group(2)
        x = re.search(r'\bx="([-\d.]+)"', attrs)
        y = re.search(r'\by="([-\d.]+)"', attrs)
        content = _WS.sub(" ", re.sub(r"<[^>]+>", "", body)).strip()
        out.append((content, x.group(1) if x else None, y.group(1) if y else None))
    return out

def _viewbox(svg: str):
    m = re.search(r'viewBox="([^"]*)"', svg)
    return m.group(1) if m else None

def diff(ours: str, ref: str) -> dict:
    no, nr = normalize(ours), normalize(ref)
    od, rd = _path_ds(no), _path_ds(nr)
    first = None
    for i in range(max(len(od), len(rd))):
        o = od[i] if i < len(od) else "<missing>"
        r = rd[i] if i < len(rd) else "<missing>"
        if o != r:
            first = f"path[{i}] ours={o[:80]!r} ref={r[:80]!r}"
            break
    path_ds = [(i, od[i] if i < len(od) else None, rd[i] if i < len(rd) else None)
               for i in range(max(len(od), len(rd)))]
    return {
        "viewbox_ok": _viewbox(no) == _viewbox(nr),
        "path_count_ok": len(od) == len(rd),
        "path_ds": path_ds,
        "text_positions": list(zip(_texts(no), _texts(nr))),
        "first_divergence": first,
        "byte_equal": no == nr,
    }
