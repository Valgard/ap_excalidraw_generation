"""Shared visual atoms for Excalidraw diagrams — data only, no layout logic."""
from excalidraw_toolkit import FONT  # re-export; one-way import, no cycle

# Open-Color shades the reference corpus uses: fill (light) + stroke (dark).
PALETTE = {
    "blue":      {"fill": "#a5d8ff", "stroke": "#1971c2"},
    "blue_pale": {"fill": "#e7f5ff", "stroke": "#74c0fc"},
    "green":     {"fill": "#b2f2bb", "stroke": "#2f9e44"},
    "amber":     {"fill": "#ffe8cc", "stroke": "#e8590c"},
    "yellow":    {"fill": "#fff3bf", "stroke": "#f08c00"},
    "red":       {"fill": "#ffc9c9", "stroke": "#e03131"},
    "violet":    {"fill": "#d0bfff", "stroke": "#862e9c"},
    "gray":      {"fill": "#e9ecef", "stroke": "#868e96"},
    "dark":      {"fill": "#343a40", "stroke": "#1e1e1e"},
}

# Meaning -> hue. The semantic layer callers should reach for first.
SEMANTIC = {
    "danger":   "red",
    "success":  "green",
    "warning":  "amber",
    "info":     "blue",
    "optional": "blue_pale",
    "neutral":  "gray",
    "accent":   "violet",
    "emphasis": "dark",
}

def role(name):
    """Semantic role -> a fresh {'fill','stroke'} dict; splat into box()/rect()."""
    return dict(PALETTE[SEMANTIC[name]])

# Shared title/subtitle text-kwargs (font role + size), used by both styles.
TITLE    = {"font": "hand", "font_size": 28}
SUBTITLE = {"font": "hand", "font_size": 16}
