"""Global configuration: screen geometry, fonts, and layout constants."""
from __future__ import annotations

import os

# --- Debug mode -----------------------------------------------------------
# A runtime-only developer switch (ADR 0012), set once from ``main.py``'s
# ``--debug`` flag. It gates the F12 Debug menu and its cheats and is *never*
# serialized — a save made under --debug reloads as an ordinary game. Read it
# where the switch matters (input_handlers, hud); nothing writes it but main().
DEBUG = False

# --- Sprite mode (SPIKE, issue #92) ---------------------------------------
# A runtime-only switch set once from ``main.py``'s hidden ``--sprites`` flag
# (ADR-0013 Phase 0 vertical slice). When on, the map viewport is composited
# from Kenney Roguelike sprites (see ``lonelands/sprites.py``) over the ASCII
# grid, and cells are made square (``TILE_HEIGHT`` set to ``TILE_WIDTH``). Never
# serialized; nothing writes it but ``main()``. Off = the untouched ASCII path.
SPRITES = False

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
# the Chronicle stays legible without hurting the map. (Native menus render in a
# proportional font instead — see lonelands/ui.py.) The system fonts are
# fallbacks if the bundled file is missing; the first that both exists and loads
# wins.
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

# Cell size in pixels. The console grid has one cell size for the whole screen,
# so map and prose share it. The tileset art is square 16x16; lonelands.fonts
# letterboxes it (centres the square tile, never stretches) so the cell can be a
# little taller than wide — giving the TTF prose the vertical room it needs to
# stay legible while the map tiles stay crisp, with only a thin grid gap between
# rows. 16x20 balances a readable Chronicle against a solid map. The window
# re-renders the tileset crisply on resize, so this is a starting size.
TILE_WIDTH = 16
TILE_HEIGHT = 20

WINDOW_TITLE = "The Lonelands — Eriador, TA 2965"

# --- Difficulty -----------------------------------------------------------
# A run's difficulty scales only the damage the player takes; foes' Endurance
# and aim are untouched. The chosen key is stored on the Engine (and so rides
# along in the save). Each tier is (key, name, incoming-damage multiplier,
# blurb). Wayfarer is the intended balance (1.0×).
DIFFICULTIES = [
    ("merciful", "Merciful", 0.6,
     "The road is kinder; the blows that land bite softly."),
    ("wayfarer", "Wayfarer", 1.0,
     "The North as it is — the intended measure of peril."),
    ("grim", "Grim", 1.4,
     "Death walks close beside you; every wound cuts deep."),
]
DEFAULT_DIFFICULTY = "wayfarer"


def difficulty_multiplier(key: str) -> float:
    """The incoming-damage multiplier for a difficulty key (1.0 if unknown)."""
    for k, _name, mult, _blurb in DIFFICULTIES:
        if k == key:
            return mult
    return 1.0


def find_font() -> str | None:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None
