"""Oryx sprite atlas: tinted silhouettes for the play field (ADR 0016).

The Oryx *Ultimate Roguelike 2.0* sheets are monochrome white alpha masks —
the same shape of asset :mod:`lonelands.fonts` already bakes for prose and
dice (a coverage mask, tinted by the cell's foreground colour on blit). This
module is that same seam applied to sliced tile-sheet regions instead of
rendered TTF glyphs.

Two independent things live here:

* :data:`SPRITE_KEYS` — the registry mapping a *sprite key* (a short string
  every drawable in :mod:`lonelands.content`, :mod:`lonelands.tile_types`, and
  the NPC/race machinery names itself by) to a :class:`SpriteRef` — which
  sheet, and which cell of its native tile grid. This is notes/oryx-tileset-
  mapping.md made concrete in code. A drawable with no sprite key (the four
  bespoke props — hobbit-hole, the Prancing Pony, signposts, barrow-mounds —
  are the only ones, tracked as their own follow-up issues) always renders
  ASCII, never blank.
* :class:`SpriteAtlas` — loads the sheets from ``LONELANDS_TILES`` (never
  committed; licensed art), auto-detects each sheet's native tile size, slices
  and scales the requested cell into a coverage mask, and bakes it into a
  white/alpha surface via :func:`lonelands.fonts.mask_to_surface` — tinted by
  the display exactly like every other glyph.

Sprite keys flow through the same codepoint-shaped cache the ASCII path uses:
:func:`sprite_id` assigns each key a small stable integer for the session, so
``tile_types.graphic_dt`` and ``display.console_dt`` can carry a plain
``int32`` alongside ``ch`` without changing their contract.
"""
from __future__ import annotations

import os
from typing import Dict, NamedTuple, Optional

import numpy as np
import pygame

from lonelands import config, fonts


class SpriteRef(NamedTuple):
    """A sprite key's home: ``sheet`` (a key into :data:`SHEETS`) and its
    ``(col, row)`` cell in that sheet's native tile grid."""

    sheet: str
    col: int
    row: int


# --- Sheets ------------------------------------------------------------
# Sheet name -> PNG filename, relative to LONELANDS_TILES. A per-sheet size
# hint (Oryx's documented category sizes) seeds native-size detection —
# these sheets are tightly cropped, not padded to a clean grid multiple, so
# detection searches a small window around the hint rather than demanding
# exact divisibility.
SHEETS: Dict[str, str] = {
    "Terrain": "Terrain.png",
    "Terrain_Objects": "Terrain_Objects.png",
    "Monsters": "Monsters.png",
    "Avatar": "Avatar.png",
    "Items": "Items.png",
}
_SIZE_HINT: Dict[str, int] = {
    "Terrain": 24,
    "Terrain_Objects": 24,
    "Monsters": 16,
    "Avatar": 16,
    "Items": 24,
}


def _grid(sheet: str, index: int, cols: int) -> SpriteRef:
    return SpriteRef(sheet, index % cols, index // cols)


# --- The registry --------------------------------------------------------
# Sequential best-effort grid placements — a first pass covering every
# drawable, not yet visually curated (issue #112 is the plumbing; pinning
# exact cells is expected fast-follow polish once the game runs on-screen).

_TERRAIN_KEYS = [
    "floor", "wall", "rubble", "down_stairs", "up_stairs", "door",
    "grass", "grass_low", "tree", "water", "road", "bridge", "hill",
    "cobble", "building_wall", "ruin_entrance",
]
_MONSTER_KEYS = [
    "cave_goblin", "orc_soldier", "orc_archer", "great_spider", "wight",
    "wolf", "warg", "footpad", "highwayman", "boar",
]
_AVATAR_KEYS = ["player", "npc_standing", "race_man", "race_hobbit", "race_dwarf"]
_PROP_KEYS = ["snare"]
_ITEM_KEYS = [
    "dunedain_sword", "short_sword", "hunting_dagger", "war_spear", "dwarf_axe",
    "shortbow", "longbow", "arrows",
    "leather_gear", "mail_corslet", "buckler", "travellers_hood",
    "ranger_star", "elven_brooch",
    "angolar", "mail_of_the_last_watch", "cloak_of_lorien",
    "athelas", "healing_herbs", "lembas", "miruvor", "pipe_weed",
    "star_brooch", "felling_axe",
    "wolf_pelt", "warg_pelt", "spider_silk", "orc_trophy", "wolf_fang",
]

SPRITE_KEYS: Dict[str, SpriteRef] = {}
SPRITE_KEYS.update({k: _grid("Terrain", i, 8) for i, k in enumerate(_TERRAIN_KEYS)})
SPRITE_KEYS.update({k: _grid("Terrain_Objects", i, 8) for i, k in enumerate(_PROP_KEYS)})
SPRITE_KEYS.update({k: _grid("Monsters", i, 8) for i, k in enumerate(_MONSTER_KEYS)})
# Avatar.png is a 7-col×3-row grid at its native 16px; column 0 is a small
# marker glyph, not a figure — the actual silhouettes start at column 1
# (confirmed by inspecting the sheet).
SPRITE_KEYS.update({k: _grid("Avatar", i + 1, 7) for i, k in enumerate(_AVATAR_KEYS)})
SPRITE_KEYS.update({k: _grid("Items", i, 8) for i, k in enumerate(_ITEM_KEYS)})

# The four bespoke tiles (ADR 0016 §curated hybrid coverage): each is its own
# follow-up issue and keeps the ASCII glyph forever, never a registry entry.
BESPOKE_KEYS = frozenset({"hobbit_hole", "prancing_pony", "signpost", "barrow_mound"})


# --- sprite-id allocation (mirrors the ASCII codepoint cache shape) --------
_next_id = 1
_ids: Dict[str, int] = {}


def sprite_id(key: str) -> int:
    """A stable per-process ``int32`` for sprite key ``key`` (0 means "no
    sprite" — an empty key always maps to 0, so unset fields fall through to
    the ASCII path with no lookup)."""
    global _next_id
    if not key:
        return 0
    sid = _ids.get(key)
    if sid is None:
        sid = _next_id
        _ids[key] = sid
        _next_id += 1
    return sid


def key_for_id(sid: int) -> Optional[str]:
    for key, val in _ids.items():
        if val == sid:
            return key
    return None


# --- availability -----------------------------------------------------------
def available() -> bool:
    """Whether Oryx art is actually on disk — the auto-detect signal (ADR 0016
    §auto-detect default, ASCII toggle)."""
    path = config.tiles_path()
    if path is None:
        return False
    return os.path.isfile(os.path.join(path, SHEETS["Terrain"]))


def enabled() -> bool:
    """Whether the play field should draw sprites right now: art is present
    and the ``--ascii`` toggle hasn't forced ASCII (ADR 0016)."""
    return not config.ASCII_ONLY and available()


# --- native tile-size detection ---------------------------------------------
def _detect_native_size(width: int, height: int, hint: int) -> int:
    """The tile size nearest ``hint`` that divides both ``width`` and
    ``height`` exactly, or ``hint`` itself if none in the window does.

    Oryx sheets are cropped tight, not padded to an exact grid multiple, so a
    sheet's true tile size usually does *not* divide its pixel dimensions —
    the crop just trims a partial trailing row/column. Minimising the total
    remainder (an earlier version of this function) picks up on that noise:
    a *wrong* size can have a smaller combined remainder than the true one
    (Terrain.png: 22 remainders to 14px, the true 24 to 16px — 22 "wins" and
    slices every tile off-grid, producing a visible moiré of seams). An exact
    divisor of both dimensions is real signal; a merely-smaller remainder
    isn't, so only an exact match overrides the documented hint."""
    window = range(max(4, hint - 6), hint + 7)
    for size in sorted(window, key=lambda s: abs(s - hint)):
        if width % size == 0 and height % size == 0:
            return size
    return hint


# --- The atlas ---------------------------------------------------------------
class SpriteAtlas:
    """Per-sprite-key white coverage surfaces at a fixed cell size, sliced
    from the Oryx sheets and scaled to the game's square cell — the same
    tint-on-blit contract as :class:`lonelands.fonts.GlyphAtlas`."""

    def __init__(self, cell_w: int, cell_h: int):
        self.cell_w = cell_w
        self.cell_h = cell_h
        self._path = config.tiles_path()
        self._sheets: Dict[str, "pygame.Surface"] = {}
        self._native_size: Dict[str, int] = {}
        self._cache: Dict[int, Optional["pygame.Surface"]] = {}

    def base_surface(self, sid: int) -> Optional["pygame.Surface"]:
        """The white sprite surface for sprite-id ``sid``, or ``None`` if the
        id is unset (0) or its art can't be resolved — callers fall back to
        the ASCII glyph in that case, exactly like a missing codepoint."""
        if sid == 0:
            return None
        if sid not in self._cache:
            self._cache[sid] = self._make(sid)
        return self._cache[sid]

    def _make(self, sid: int) -> Optional["pygame.Surface"]:
        key = key_for_id(sid)
        if key is None:
            return None
        ref = SPRITE_KEYS.get(key)
        if ref is None:
            return None
        sheet = self._sheet(ref.sheet)
        if sheet is None:
            return None
        size = self._native_size[ref.sheet]
        rect = pygame.Rect(ref.col * size, ref.row * size, size, size)
        if not sheet.get_rect().contains(rect):
            return None
        tile = sheet.subsurface(rect).copy()
        scaled = pygame.transform.smoothscale(tile, (self.cell_w, self.cell_h))
        mask = pygame.surfarray.array_alpha(scaled)
        return fonts.mask_to_surface(np.ascontiguousarray(mask.T))

    def _sheet(self, name: str) -> Optional["pygame.Surface"]:
        if name in self._sheets:
            return self._sheets[name]
        surf = self._load_sheet(name)
        self._sheets[name] = surf
        return surf

    def _load_sheet(self, name: str) -> Optional["pygame.Surface"]:
        if self._path is None:
            return None
        filename = SHEETS.get(name)
        if filename is None:
            return None
        full = os.path.join(self._path, filename)
        if not os.path.isfile(full):
            return None
        surf = pygame.image.load(full).convert_alpha()
        self._native_size[name] = _detect_native_size(
            surf.get_width(), surf.get_height(), _SIZE_HINT.get(name, 24)
        )
        return surf
