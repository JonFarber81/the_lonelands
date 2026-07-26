"""Global configuration: screen geometry, fonts, and layout constants."""
from __future__ import annotations

import os

# --- Window / console geometry (in tiles) ---------------------------------
SCREEN_WIDTH = 92
SCREEN_HEIGHT = 54

# The map viewport is upper-left. A stats sidebar runs the full height on the
# right; the bottom-left pane holds the dice tray above the message log.
MAP_WIDTH = 62
MAP_HEIGHT = 44

SIDEBAR_X = MAP_WIDTH
SIDEBAR_WIDTH = SCREEN_WIDTH - MAP_WIDTH  # 30

# The bottom-left "Chronicle" pane is a framed box. Reading top-to-bottom:
#   LOG_Y            frame top border (carries the " Chronicle " title)
#   TRAY_Y..         the dice tray — the player's latest roll, rendered as dice.
#                    Dice are two cells tall, so the tray spans TRAY_ROWS rows.
#   TRAY_DIVIDER_Y   a thin rule separating the tray from the prose
#   LOG_TEXT_Y..     the scrolling message log (LOG_TEXT_HEIGHT rows)
#   (frame bottom border)
LOG_Y = MAP_HEIGHT
LOG_HEIGHT = SCREEN_HEIGHT - MAP_HEIGHT   # 10

TRAY_Y = LOG_Y + 1
TRAY_ROWS = 2                             # dice are 2 cells tall
TRAY_DIVIDER_Y = TRAY_Y + TRAY_ROWS
LOG_TEXT_Y = TRAY_DIVIDER_Y + 1
# borders (2) + tray (TRAY_ROWS) + rule (1) leave the rest for prose (5 rows)
LOG_TEXT_HEIGHT = LOG_HEIGHT - (3 + TRAY_ROWS)

# --- Font -----------------------------------------------------------------
# We render with a heavy monospace that fills its cell for legibility at small
# sizes. Because every glyph — map symbols and prose alike — shares one cell,
# the font must fill the cell: narrow faces (Monaco, SF Mono, DejaVu Sans Mono)
# leave a gap after each letter that scatters prose and reads worse. We bundle
# Atkinson Hyperlegible Mono (SIL OFL, see assets/fonts/OFL.txt), which fills
# the cell as tightly as Andale but with letterforms engineered for reading, so
# the Chronicle and menus stay legible without hurting the map. The system fonts
# are fallbacks if the bundled file is missing. NOTE: libtcod can only load
# plain .ttf files, not .ttc collections (e.g. Menlo.ttc). Fallbacks are tried
# in order; the first that both exists and loads wins.
_ASSETS = os.path.join(os.path.dirname(__file__), "assets", "fonts")

FONT_CANDIDATES = [
    os.path.join(_ASSETS, "AtkinsonHyperlegibleMono-Regular.ttf"),
    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
    "/Library/Fonts/Andale Mono.ttf",
    "/System/Library/Fonts/Monaco.ttf",
    "/System/Library/Fonts/SFNSMono.ttf",
]

# --- Map tileset ----------------------------------------------------------
# Map terrain and entity glyphs are drawn from a Dwarf-Fortress-style 16x16
# CP437 tilesheet (see lonelands/fonts.py, lonelands/tile_glyphs.py); prose stays
# on the TrueType font above. The bundled sheet is the "Wanderlust" tileset,
# kept local and gitignored — see lonelands/assets/tiles/README.md. If no sheet
# is present the map falls back to TTF-rendered glyphs (the pre-tileset look).
_TILES = os.path.join(os.path.dirname(__file__), "assets", "tiles")

TILESET_CANDIDATES = [
    os.path.join(_TILES, "wanderlust_16x16.png"),
]

# Cell size in pixels. A tcod console has one cell size for the whole screen, so
# map and prose share it. The tileset art is square 16x16; lonelands.fonts
# letterboxes it (centres the square tile, never stretches) so the cell can be a
# little taller than wide — giving the TTF prose the vertical room it needs to
# stay legible while the map tiles stay crisp, with only a thin grid gap between
# rows. 16x20 balances a readable Chronicle against a solid map. The window
# re-renders the tileset crisply on resize, so this is a starting size.
TILE_WIDTH = 16
TILE_HEIGHT = 20

WINDOW_TITLE = "The Lonelands — Eriador, TA 2965"


def find_font() -> str | None:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None
