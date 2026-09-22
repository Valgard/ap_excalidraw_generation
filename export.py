# /// script
# requires-python = ">=3.10"
# dependencies = ["resvg-py==0.3.3"]
# ///
"""Deterministic .excalidraw → PNG export. Run: uv run export.py IN -o OUT --scale 2"""
import argparse
import json
import pathlib

import excalidraw_svg
import export_options
import fonts


def render_png(src, out, scale=None, background=None, options=None):
    """Rasterise *src* (.excalidraw file path or parsed dict) to a PNG at *out*.

    Args:
        src: Path string to a .excalidraw file, or an already-parsed dict.
        out: Destination path for the PNG file.
        scale: Zoom multiplier (1, 2, or 3).  When None, inherits from *options*
               or defaults to 1 (Excalidraw-conformant default).
               Back-compat: passing scale=2 still works exactly as before.
        background: "light" → white (#ffffff); "transparent" → no background;
                    or a literal CSS colour string.  When None, inherits from
                    *options* or the file's appState.
               Back-compat: passing background="light" or background="transparent"
               still works exactly as before.
        options: ExportOptions instance.  When None, resolved from the document
                 (using appState precedence) with any explicit scale/background
                 args applied on top.

    Returns:
        The *out* path (str).
    """
    doc = json.loads(pathlib.Path(src).read_text()) if isinstance(src, str) else src

    if options is None:
        # Build override kwargs from the explicit arguments (None = "not given").
        override_kwargs = {}
        if scale is not None:
            override_kwargs["export_scale"] = float(scale)
        if background is not None:
            if background == "transparent":
                override_kwargs["export_background"] = False
            else:
                # "light" → "#ffffff"; a raw colour string is passed through.
                override_kwargs["view_background_color"] = (
                    "#ffffff" if background == "light" else background
                )
                override_kwargs["export_background"] = True
        options = export_options.resolve(doc, **override_kwargs)

    svg = excalidraw_svg.to_svg(doc, options=options)

    import resvg_py  # imported here so bare-python collection doesn't fail

    # resvg ignores base64 @font-face in the SVG — the bundled hand-drawn fonts must
    # be handed to its own font loader, matched by their exact internal family names.
    # Load ONLY the text fonts this document references (+ Latin-free fallbacks): keeping an
    # unused complete Latin font like LiberationSans out of resvg's fontdb prevents it from
    # poisoning a hand-drawn run that contains a symbol (→ ✗ …). See fonts.font_file_paths.
    png_bytes = resvg_py.svg_to_bytes(
        svg_string=svg, zoom=float(options.export_scale),
        font_files=fonts.font_file_paths(fonts.used_codes(doc), authentic_virgil=options.authentic_virgil),
        skip_system_fonts=True,  # determinism: depend only on the bundled fonts
    )
    pathlib.Path(out).write_bytes(bytes(png_bytes))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Convert a .excalidraw file to PNG via resvg."
    )
    ap.add_argument("input", help="Path to .excalidraw source file")
    ap.add_argument("-o", "--output", help="Output PNG path (default: <input>.png)")
    ap.add_argument(
        "--scale", type=float, default=None,
        help="Zoom multiplier (default: from appState or 1)"
    )
    ap.add_argument(
        "--background", default=None,
        metavar="MODE",
        help=(
            "Background: 'light' (white), 'transparent', or 'color:#RRGGBB'. "
            "Default: from appState (white)."
        ),
    )
    ap.add_argument(
        "--padding", type=int, default=None,
        help="Export padding in pixels (default: from appState or 10)"
    )
    ap.add_argument(
        "--dark-mode", action="store_true", default=None,
        help="Enable dark-mode export (minimal: dark background)"
    )
    ap.add_argument(
        "--embed-scene", action="store_true", default=None,
        help="Embed raw scene JSON in SVG <metadata>"
    )
    ap.add_argument(
        "--authentic-virgil", action="store_true", default=None,
        help=(
            "Render deprecated Virgil (fontFamily=1) as the genuine Virgil font "
            "instead of Excalifont (default: Excalifont, matching ExcalidrawZ)"
        ),
    )
    a = ap.parse_args(argv)

    # Parse --background flag into render_png-compatible form.
    bg_arg = None
    if a.background is not None:
        if a.background.startswith("color:"):
            bg_arg = a.background[len("color:"):]  # strip prefix, pass raw CSS colour
        else:
            bg_arg = a.background  # "light" | "transparent"

    # Build explicit overrides from CLI flags; pass None for unset flags.
    doc = json.loads(pathlib.Path(a.input).read_text())
    override_kwargs = {}
    if a.scale is not None:
        override_kwargs["export_scale"] = a.scale
    if a.padding is not None:
        override_kwargs["export_padding"] = a.padding
    if a.dark_mode:
        override_kwargs["export_with_dark_mode"] = True
    if a.embed_scene:
        override_kwargs["export_embed_scene"] = True
    if a.authentic_virgil:
        override_kwargs["authentic_virgil"] = True
    if bg_arg == "transparent":
        override_kwargs["export_background"] = False
    elif bg_arg is not None:
        override_kwargs["view_background_color"] = "#ffffff" if bg_arg == "light" else bg_arg
        override_kwargs["export_background"] = True

    opts = export_options.resolve(doc, **override_kwargs)
    out = a.output or str(pathlib.Path(a.input).with_suffix(".png"))
    render_png(a.input, out, options=opts)
    print(out)


if __name__ == "__main__":
    main()
