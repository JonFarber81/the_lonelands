"""Global configuration: screen geometry, fonts, and layout constants."""
from __future__ import annotations

import os

# --- Window / console geometry (in tiles) ---------------------------------
SCREEN_WIDTH = 92
SCREEN_HEIGHT = 54

# The map viewport is upper-left. A stats sidebar runs the full height on the
# right; a message log runs beneath the map on the left.
MAP_WIDTH = 62
MAP_HEIGHT = 46

SIDEBAR_X = MAP_WIDTH
SIDEBAR_WIDTH = SCREEN_WIDTH - MAP_WIDTH  # 30

LOG_Y = MAP_HEIGHT
LOG_HEIGHT = SCREEN_HEIGHT - MAP_HEIGHT   # 8

# --- Font -----------------------------------------------------------------
# We render with a crisp TrueType monospace for that clean Brogue/Cogmind look.
# Fallbacks are tried in order; the first that exists wins.
FONT_CANDIDATES = [
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
    "/Library/Fonts/Andale Mono.ttf",
]

TILE_WIDTH = 12
TILE_HEIGHT = 20  # taller cells read better for text-heavy roguelikes

WINDOW_TITLE = "The Lonelands — Eriador, TA 2965"


def find_font() -> str | None:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None
