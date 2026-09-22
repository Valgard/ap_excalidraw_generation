"""Dev-time: render every articles/**/*.excalidraw (transparent, scale from source),
compare to the sibling assets/<stem>.png via ImageMagick AE/PSNR. Regression signal only."""
import pathlib, struct, subprocess, sys
sys.path.insert(0, "<skill-dir>")
import export

ART = pathlib.Path("<articles-dir>")
OUT = pathlib.Path("/tmp/verify-corpus"); OUT.mkdir(exist_ok=True)


def _png_dims(p):
    with open(p, 'rb') as f:
        f.read(16)
        return struct.unpack('>II', f.read(8))


rows = []
dim_mismatches = []
skipped = []

for src in sorted(ART.glob("**/*.excalidraw")):
    orig = src.parent.parent / "assets" / (src.stem + ".png")
    if not orig.exists():
        continue
    png = OUT / (src.stem + ".png")
    try:
        export.render_png(str(src), str(png), background="transparent")  # scale inherited from appState
    except Exception as e:
        skipped.append((src.stem, str(e)))
        continue

    rendered_dims = _png_dims(png)
    orig_dims = _png_dims(orig)
    if rendered_dims != orig_dims:
        dim_mismatches.append((src.stem, rendered_dims, orig_dims))
        continue

    r = subprocess.run(["magick", "compare", "-metric", "PSNR", str(png), str(orig), "null:"],
                       capture_output=True, text=True)
    raw = (r.stderr or r.stdout).strip()
    if not raw:
        rows.append((src.stem, f"PSNR_ERROR magick returned no output (rc={r.returncode})"))
    else:
        try:
            float(raw.split()[0])
            rows.append((src.stem, raw))
        except (ValueError, IndexError):
            rows.append((src.stem, f"PSNR_ERROR unparseable: {raw!r}"))

for stem, psnr in rows:
    print(f"{stem:45s} PSNR={psnr}")

if dim_mismatches:
    print(f"\nDIM_MISMATCH ({len(dim_mismatches)}):")
    for stem, rw, ow in dim_mismatches:
        print(f"  {stem}: rendered {rw[0]}x{rw[1]} vs orig {ow[0]}x{ow[1]}")

if skipped:
    print(f"\nSkipped (render error) ({len(skipped)}):")
    for stem, err in skipped:
        print(f"  {stem}: {err}")

print(f"\n{len(rows)} compared, {len(dim_mismatches)} dim-mismatch, {len(skipped)} crash-skipped")
