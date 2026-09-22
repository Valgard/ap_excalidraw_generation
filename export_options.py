"""Export options mirroring Excalidraw's exportToSvg opts.

Precedence: explicit kwarg > file appState > hard default.

Hard defaults match Excalidraw's own defaults from scene/export.ts:
  export_background=True, view_background_color="#ffffff",
  export_padding=10, export_scale=1,
  export_with_dark_mode=False, export_embed_scene=False.
"""
from dataclasses import dataclass

_DEFAULTS = {
    "export_background": True,
    "view_background_color": "#ffffff",
    "export_padding": 10,
    "export_scale": 1,
    "export_with_dark_mode": False,
    "export_embed_scene": False,
    "authentic_virgil": False,
}

# appState key (Excalidraw camelCase) -> our snake_case field
_APPSTATE = {
    "exportBackground": "export_background",
    "viewBackgroundColor": "view_background_color",
    "exportPadding": "export_padding",
    "exportScale": "export_scale",
    "exportWithDarkMode": "export_with_dark_mode",
    "exportEmbedScene": "export_embed_scene",
}


@dataclass
class ExportOptions:
    export_background: bool = True
    view_background_color: str = "#ffffff"
    export_padding: int = 10
    export_scale: float = 1
    export_with_dark_mode: bool = False
    export_embed_scene: bool = False
    authentic_virgil: bool = False


def resolve(doc, **overrides) -> ExportOptions:
    """Build ExportOptions with precedence: explicit kwarg > appState > hard default.

    Args:
        doc: Parsed Excalidraw document dict (may be empty or lack appState).
        **overrides: Explicit field overrides (snake_case). None values are ignored
                     so callers can pass optional CLI args without conditional logic.

    Returns:
        Fully resolved ExportOptions instance.
    """
    values = dict(_DEFAULTS)
    app = (doc or {}).get("appState") or {}
    for k, field in _APPSTATE.items():
        if k in app and app[k] is not None:
            values[field] = app[k]
    for field, v in overrides.items():
        if v is not None:
            values[field] = v
    return ExportOptions(**values)
