#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["resvg-py==0.3.3", "pillow", "numpy"]
# ///
"""Font-render error detector for the .excalidraw exporter (dev/CI tool).

Thin driver over ``tools/font_diff.py`` (which holds all the tested logic). For each
corpus diagram it renders OURS with the exporter, loads the ORIGINAL excalidraw.com
asset, scale-matches, then — per TEXT ELEMENT — measures three alpha-aggregate metrics
that see through anti-aliasing and only fire on real font failures:

  * ink balance      Σα(ours)/Σα(orig)  — missing glyphs / whole-chunk poison / tofu
                     (INK_LOSS) or a bolder wrong fallback (INK_GAIN)
  * projection corr  1D column/row ink-signature agreement — a wrong-shape fallback or
                     a dropped glyph (SHAPE_MISMATCH); shift-tolerant so AA wobble passes
  * centroid shift   ink-centroid displacement in px (DISPLACED)

Text boxes come from the SAME scene_layout the renderer uses, so they land exactly on
the PNG (bound text resolved from container geometry, never a stale stored x/y).
Non-text regions get an AA-tolerant pixel diff so fill/arrowhead bugs still surface.

Why this beats a plain RGB threshold: font bugs live exactly where the AA wobble lives
(in the text). Aggregating ink over each element's box separates the signal (a whole
glyph's worth of missing ink) from the noise (1-2px edge jitter at every glyph).

Scope & limits (measured against the poison-free 102-diagram corpus): ink_balance is
the reliable signal — clean ink sits in [0.72, 1.09], so a vanished/poisoned chunk
(ink→0) or a bolder tofu fallback (ink↑) stands out cleanly. The projection
correlation is WEAK at 1x hand-drawn text: correct resvg-vs-WebKit rendering already
spreads corr from ~0.2 to ~1.0, overlapping a wrong-font substitution of similar
coverage — so a *subtle* font swap (e.g. Virgil→Helvetica) is NOT reliably caught.
corr_min is therefore a coarse total-shape-collapse net (corr≈0/negative), not a
fine discriminator. The detector's strength is catching the DOCUMENTED drastic modes
(whole-chunk poison, tofu, wrong-weight fallback, gross displacement).

Run:
  BLOGS_ARTICLES_DIR=/path/to/blogs/articles uv run tools/diff_detect.py
  uv run tools/diff_detect.py --articles /path/to/blogs/articles
  uv run tools/diff_detect.py --json report.json          # machine-readable verdicts
  open file:///tmp/ab-final/index.html                    # triage view
Exit code is non-zero if any text element trips a verdict (CI gate).
"""
import argparse
import html
import json
import os
import pathlib
import struct
import sys

import numpy as np
from PIL import Image

GEN = pathlib.Path(__file__).resolve().parent.parent  # the excalidraw-generation dir
sys.path.insert(0, str(GEN))
import excalidraw_svg  # noqa: E402
import export  # noqa: E402
import export_options  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # tools/
import font_diff  # noqa: E402

OUT = pathlib.Path("/tmp/ab-final")
AA_THRESH = 24  # non-text pixel is "changed" if AA-tolerant |Δα| exceeds this

# Verdict → overlay colour + one-line meaning (drives the box overlays AND the HTML legend).
VERDICT_COLOUR = {
    "OK": None,
    "INK_LOSS": "#e5484d",       # red — missing glyph / poison / tofu
    "INK_GAIN": "#f5a623",       # amber — bolder wrong fallback
    "SHAPE_MISMATCH": "#8e4ec6", # purple — wrong shape / dropped glyph
    "DISPLACED": "#0091ff",      # blue — mispositioned
}
VERDICT_DESC = {
    "INK_LOSS": "text missing / poison / tofu (reliable)",
    "INK_GAIN": "bolder / wrong fallback",
    "SHAPE_MISMATCH": "wrong glyph shape — weak signal at 1x",
    "DISPLACED": "text off-position (>10px)",
}


def _dims(p):
    with open(p, "rb") as f:
        f.read(16)
        return struct.unpack(">II", f.read(8))


def _ink(p, size=None):
    """Background-invariant ink map (darkness over white) of *p*, shape (H, W).

    Resizes to *size*=(w, h) if given. Uses font_diff.ink_from_rgba so a transparent
    excalidraw.com asset and our (white-bg) render are directly comparable — raw alpha
    is not (opaque render vs transparent asset)."""
    im = Image.open(p).convert("RGBA")
    if size and im.size != size:
        im = im.resize(size, Image.LANCZOS)
    return font_diff.ink_from_rgba(np.asarray(im, dtype=np.float64))


def _resolve_articles(cli_value):
    root = cli_value or os.environ.get("BLOGS_ARTICLES_DIR")
    if not root:
        sys.exit(
            "error: pass --articles PATH or set BLOGS_ARTICLES_DIR (the blogs/articles dir "
            "holding <slug>/**/*.excalidraw + <slug>/assets/<stem>.png pairs)."
        )
    p = pathlib.Path(root).expanduser()
    if not p.is_dir():
        sys.exit(f"error: articles dir not found: {p}")
    return p


def _integer_scale(doc, ow, oh):
    """Render scale so ours matches the original asset size (integer zoom, no blur)."""
    opts1 = export_options.resolve(doc, export_scale=1.0)
    layout1 = excalidraw_svg.scene_layout(doc, opts1)
    w1, h1 = int(round(layout1.width)), int(round(layout1.height))
    if not w1:
        return 1
    k = round(ow / w1)
    if k >= 1 and abs(ow - k * w1) <= 2 and abs(oh - k * h1) <= 2:
        return k
    return 1


def analyze_one(src, orig_png, params):
    """Render, scale-match, and analyse one diagram. Returns a result dict or raises."""
    doc = json.loads(src.read_text())
    ow, oh = _dims(orig_png)
    scale = _integer_scale(doc, ow, oh)

    # Match the asset's background so the A/B page shows both on the SAME ground
    # (a transparent asset must not sit next to a white-bg render). This is also more
    # correct metrically: _ink now composites BOTH sides symmetrically over white
    # (before, ours was resvg-blended onto white, the asset straight-composited by
    # _ink) — the only effect is a sub-pixel AA-edge shift on a borderline element.
    asset_transparent = font_diff.is_transparent(
        np.asarray(Image.open(orig_png).convert("RGBA"))
    )
    opts = export_options.resolve(doc, export_scale=float(scale),
                                  export_background=not asset_transparent)

    # Collision-safe id: two articles can share a stem (e.g. two timeline-en);
    # key output files + JSON/HTML by <article-dir>__<stem> so they never overwrite.
    uid = f"{src.parent.parent.name}__{src.stem}"
    ours_png = OUT / (uid + ".ours.png")
    export.render_png(str(src), str(ours_png), options=opts)

    ink_ours = _ink(ours_png)
    h, w = ink_ours.shape
    ink_orig = _ink(orig_png, size=(w, h))

    layout = excalidraw_svg.scene_layout(doc, opts)
    elements = font_diff.analyze_text_elements(
        doc, opts, ink_ours, ink_orig, layout, **params
    )
    nontext = _nontext_diff_pct(ink_ours, ink_orig, elements)
    return {
        "src": src, "uid": uid, "orig": orig_png, "ours_png": ours_png,
        "scale": scale, "dims": (w, h),
        "elements": elements,
        "nontext_pct": nontext,
        "bad": [e for e in elements if e["verdict"] != "OK"],
    }


def _nontext_diff_pct(ink_ours, ink_orig, elements):
    """% of NON-text pixels changed (AA-tolerant). Masks out text boxes first."""
    mask = font_diff.aa_tolerant_diff(ink_ours, ink_orig, thresh=AA_THRESH)
    for e in elements:
        x0, y0, x1, y1 = e["box"]
        mask[y0:y1, x0:x1] = False
    return 100.0 * float(mask.mean())


def _render_heatmap(res):
    """Save a diff heatmap: black base showing the differences (non-text diff in grey),
    text boxes coloured by verdict. Only the verdict boxes are TRANSLUCENT, so diff
    pixels inside a flagged box stay visible (opaque boxes hid them, blocking manual
    verification)."""
    ink_ours = _ink(res["ours_png"])
    ink_orig = _ink(res["orig"], size=(ink_ours.shape[1], ink_ours.shape[0]))
    vis = np.zeros((*ink_ours.shape, 3), dtype=np.float64)  # black diff base (unchanged)
    nt = font_diff.aa_tolerant_diff(ink_ours, ink_orig, thresh=AA_THRESH)
    vis[nt] = (120, 120, 120)  # differences in grey (unchanged)
    for e in res["elements"]:
        c = VERDICT_COLOUR.get(e["verdict"])
        if not c:
            continue
        rgb = np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float64)
        x0, y0, x1, y1 = e["box"]
        # ONLY the issue box is translucent: blend the verdict colour over the base
        # so any diff pixels inside the flagged box remain visible underneath.
        vis[y0:y1, x0:x1] = 0.5 * vis[y0:y1, x0:x1] + 0.5 * rgb
    heat = OUT / (res["uid"] + ".diff.png")
    Image.fromarray(vis.clip(0, 255).astype(np.uint8)).save(heat)
    return heat


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--articles", help="blogs/articles dir (else $BLOGS_ARTICLES_DIR)")
    ap.add_argument("--json", help="write machine-readable verdicts to this path")
    # Defaults calibrated against the poison-free corpus (102 diagrams, 1296 text
    # elements): clean ink ∈ [0.72, 1.09], shift p99=6.9. ink is the reliable signal.
    # corr is blurred (--blur-sigma) before the projection to dampen 1x AA jitter,
    # which lifts clean corr (p10 0.48→0.70) so corr_min=0.30 doubles wrong-font
    # recall (12%→26%) at the SAME ~1% false-positive rate vs the un-blurred raw.
    ap.add_argument("--ink-lo", type=float, default=0.55)
    ap.add_argument("--ink-hi", type=float, default=1.8)
    ap.add_argument("--corr-min", type=float, default=0.30)
    ap.add_argument("--shift-max", type=float, default=10.0)
    ap.add_argument("--blur-sigma", type=float, default=1.0,
                    help="Gaussian blur for the corr metric only (0 = raw, noisier)")
    ap.add_argument("--no-html", action="store_true", help="skip the A/B HTML page")
    a = ap.parse_args(argv)

    art = _resolve_articles(a.articles)
    OUT.mkdir(parents=True, exist_ok=True)
    params = dict(blur_sigma=a.blur_sigma, ink_lo=a.ink_lo, ink_hi=a.ink_hi,
                  corr_min=a.corr_min, shift_max=a.shift_max)

    results, errors = [], []
    for src in sorted(art.glob("**/*.excalidraw")):
        orig = src.parent.parent / "assets" / (src.stem + ".png")
        if not orig.exists():
            continue
        try:
            results.append(analyze_one(src, orig, params))
        except Exception as e:  # noqa: BLE001
            errors.append((src.stem, f"{type(e).__name__}: {e}"))

    flagged = [r for r in results if r["bad"]]
    flagged.sort(key=lambda r: -len(r["bad"]))

    # --- console ---
    n_bad = sum(len(r["bad"]) for r in results)
    print(f"analysed {len(results)} diagrams ({len(errors)} errors); "
          f"{len(flagged)} with font-render issues, {n_bad} bad text elements:")
    for r in flagged:
        print(f"  {r['src'].stem:40s} {r['scale']}x  non-text {r['nontext_pct']:4.1f}%")
        for e in r["bad"]:
            txt = (e["text"] or "").replace("\n", " ")[:32]
            print(f"      {e['verdict']:14s} ink={e['ink']:.2f} corr={e['corr']:.2f} "
                  f"shift={e['shift']:.1f}  {txt!r}")
    for stem, err in errors:
        print(f"  ERROR {stem}: {err}")

    if a.json:
        payload = [{
            "stem": r["src"].stem, "uid": r["uid"], "scale": r["scale"], "nontext_pct": r["nontext_pct"],
            "elements": [{k: (e[k] if k != "box" else list(e["box"]))
                          for k in ("id", "text", "box", "ink", "corr", "shift", "verdict")}
                         for e in r["elements"]],
        } for r in results]
        pathlib.Path(a.json).write_text(json.dumps(payload, indent=2, default=str))
        print(f"\njson: {a.json}")

    if not a.no_html:
        _write_html(results, flagged)

    # CI gate: non-zero if any text element tripped a verdict.
    return 1 if n_bad else 0


def _write_html(results, flagged):
    cards = []
    shown = flagged + [r for r in results if not r["bad"]]
    for r in shown:
        heat = _render_heatmap(r)
        badge = ""
        for e in r["bad"]:
            c = VERDICT_COLOUR.get(e["verdict"], "#888")
            badge += (f'<span style="background:{c}">{html.escape(e["verdict"])} '
                      f'{e["ink"]:.2f}/{e["corr"]:.2f}</span> ')
        cards.append(
            f'<section class=card><h3>{html.escape(r["uid"])} '
            f'<small>{r["scale"]}x · non-text {r["nontext_pct"]:.1f}% · '
            f'{len(r["bad"])} issues</small></h3><div class=badges>{badge or "clean"}</div>'
            f'<div class=row>'
            f'<figure><img src="file://{html.escape(str(r["ours_png"]))}" loading=lazy>'
            f'<figcaption>our export</figcaption></figure>'
            f'<figure><img src="file://{html.escape(str(r["orig"].resolve()))}" loading=lazy>'
            f'<figcaption>original</figcaption></figure>'
            f'<figure><img src="file://{html.escape(str(heat))}" loading=lazy>'
            f'<figcaption>verdict overlay</figcaption></figure>'
            f'</div></section>')
    legend = "".join(
        f'<span class=lg style="background:{VERDICT_COLOUR[v]}">{v}</span><em>{VERDICT_DESC[v]}</em>'
        for v in ("INK_LOSS", "INK_GAIN", "SHAPE_MISMATCH", "DISPLACED")
    ) + '<span class=lg style="background:#888">non-text</span><em>fill/arrow diff</em>'
    doc = f"""<!doctype html><meta charset=utf-8><title>Font-render detector — {len(shown)} diagrams</title>
<style>body{{font:14px/1.5 system-ui;margin:0;background:#f4f5f7;color:#1e1e1e}}
header{{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:12px 20px;z-index:5}}
.wrap{{padding:16px 24px 60px;max-width:3760px;margin:0 auto}}
.card{{background:#fff;border:1px solid #e3e3e3;border-radius:10px;margin:14px 0;padding:12px 16px}}
.card h3{{font-size:14px;margin:0 0 6px}} .card h3 small{{color:#555;font-weight:400;margin-left:8px}}
.badges{{margin:0 0 10px;font-size:11px}} .badges span{{color:#fff;border-radius:4px;padding:1px 6px;margin-right:4px}}
.legend{{margin-top:8px;font-size:11px;display:flex;flex-wrap:wrap;gap:3px 4px;align-items:center}}
.legend .lg{{color:#fff;border-radius:4px;padding:1px 6px}} .legend em{{font-style:normal;color:#555;margin-right:14px}}
.row{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;align-items:start}}
figure{{margin:0;border:1px solid #eee;border-radius:6px;overflow:hidden;
background:repeating-conic-gradient(#f0f0f0 0 25%,#fff 0 50%) 50%/16px 16px}}
figure img{{display:block;width:100%;height:auto}}
figcaption{{font-size:12px;color:#555;padding:4px 8px;background:#fafafa;border-top:1px solid #eee}}
@media(max-width:1100px){{.row{{grid-template-columns:1fr}}}}</style>
<header><b>Font-render detector</b> — {len(shown)} diagrams · left=ours, mid=original, \
right=verdict overlay
<div class=legend>{legend}</div></header>
<div class=wrap>{''.join(cards)}</div>"""
    (OUT / "index.html").write_text(doc)
    print(f"\nindex: {OUT}/index.html")


if __name__ == "__main__":
    raise SystemExit(main())
