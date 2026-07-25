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
#   TRAY_Y           the dice tray — the player's latest roll, rendered as dice
#   TRAY_DIVIDER_Y   a thin rule separating the tray from the prose
#   LOG_TEXT_Y..     the scrolling message log (LOG_TEXT_HEIGHT rows)
#   (frame bottom border)
LOG_Y = MAP_HEIGHT
LOG_HEIGHT = SCREEN_HEIGHT - MAP_HEIGHT   # 10

TRAY_Y = LOG_Y + 1
TRAY_DIVIDER_Y = LOG_Y + 2
LOG_TEXT_Y = LOG_Y + 3
LOG_TEXT_HEIGHT = LOG_HEIGHT - 4          # 6 rows of prose (borders + tray + rule)

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

# Cell size in pixels. Glyphs are rendered by lonelands.fonts, which auto-fits
# the largest pixel size that fills this cell (advance <= width, ink extent <=
# height) and lays every glyph on one shared baseline — so the text fills the
# cell instead of floating tiny inside it. This font's advance is ~0.63x its
# height, so the width must be roughly two-thirds of the height or wide glyphs
# would be starved; 16x28 fits caps + accents (Dúnedain) and descenders (g, y)
# comfortably. The window re-renders the tileset crisply on resize, so this is
# just the starting size, not a ceiling.
TILE_WIDTH = 16
TILE_HEIGHT = 28

WINDOW_TITLE = "The Lonelands — Eriador, TA 2965"


def find_font() -> str | None:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None
