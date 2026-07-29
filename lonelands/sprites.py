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
  committed; licensed art), slices each sheet at its documented native tile
  size (:data:`_SIZE_HINT`), scales the requested cell into a coverage mask,
  and bakes it into a
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

from lonelands import color, config, fonts


class SpriteRef(NamedTuple):
    """A sprite key's home: ``sheet`` (a key into :data:`SHEETS`) and its
    ``(col, row)`` cell in that sheet's native tile grid."""

    sheet: str
    col: int
    row: int


# --- Sheets ------------------------------------------------------------
# Sheet name -> PNG filename, relative to LONELANDS_TILES.
SHEETS: Dict[str, str] = {
    "Terrain": "Terrain.png",
    "Terrain_Objects": "Terrain_Objects.png",
    "Monsters": "Monsters.png",
    "Avatar": "Avatar.png",
    "Items": "Items.png",
    "Portraits": "Interface_Portraits.png",
}
# (width, height) hints — most Oryx categories are square, but Terrain.png's
# tiles are a taller 16x24: confirmed both by exact-divisor math (256x264 has
# no exact square divisor in the search window, but 16x24 divides both
# dimensions exactly — 16 cols x 11 rows, no cropped remainder) and visually,
# from a labelled grid render (silhouettes like the tombstone arches sit
# snugly in a 16-wide cell; a 24-wide slice split them across a seam).
_SIZE_HINT: Dict[str, tuple[int, int]] = {
    "Terrain": (16, 24),
    "Terrain_Objects": (24, 24),
    "Monsters": (16, 24),
    "Avatar": (16, 24),
    "Items": (24, 24),
    "Portraits": (48, 48),
}


def _grid(sheet: str, index: int, cols: int) -> SpriteRef:
    return SpriteRef(sheet, index % cols, index // cols)


# --- The registry --------------------------------------------------------
# Sequential best-effort grid placements — a first pass covering every
# drawable, not yet visually curated (issue #112 is the plumbing; pinning
# exact cells is expected fast-follow polish once the game runs on-screen).
#
# Terrain is the exception: it's hand-picked below (_TERRAIN_REFS) after
# visually inspecting Terrain.png / Terrain_Objects.png cell-by-cell — the
# original sequential placement pointed grass/road/water/tree at unrelated
# art (a lattice pattern, a row of gravestones, a dot pattern, and a wave
# pattern, respectively), which read as broken seams in an actual screenshot.
# This *Ultimate Roguelike 2.0* sheet is dungeon/graveyard-themed and has no
# real grass-field or dirt-road ground texture at all, so grass/grass_low/
# hill/road/bridge/cobble are the closest available substitutes — not a claim
# that this is what real grass or road art looks like.
#
# Re-picked after discovering Terrain.png's tiles are 16x24, not the square
# 24x24 every cell below used to assume (see _SIZE_HINT) — that misdetection
# reflowed the grid from ~11 columns to 16, so every coordinate picked against
# the old (wrong) grid pointed at different, often blank, art once the slicing
# was fixed. Re-picked from a labelled 16x24 grid render (screenshots/
# terrain_grid_16x24.png): row 3's offset brick-course blocks (cols 0-1) read
# as a road/floor/cobble at a glance; row 1's speckle dot patterns (cols 2-3)
# read as green ground cover once tinted; row 1's ascending diagonal bars
# (cols 14-15) are real stairs art (previously landed on a tombstone arch).
# Not yet re-confirmed on-screen with the project owner — flag if any of
# these read wrong once rendered.
_TERRAIN_REFS: Dict[str, "SpriteRef"] = {
    "floor": SpriteRef("Terrain", 6, 1),            # offset brick-course blocks
    "wall": SpriteRef("Terrain", 0, 0),             # cracked stone wall panel
    "rubble": SpriteRef("Terrain", 9, 7),          # scattered gravel/dot debris
    "down_stairs": SpriteRef("Terrain", 14, 1),     # diagonal ascending steps
    "up_stairs": SpriteRef("Terrain", 15, 1),       # mirrored ascending steps
    "door": SpriteRef("Terrain", 7, 2),             # rounded archway door
    "grass": SpriteRef("Terrain", 2, 1),            # sparse speckle pattern
    "grass_low": SpriteRef("Terrain", 3, 1),        # denser speckle pattern
    "tree": SpriteRef("Terrain_Objects", 4, 6),     # an actual conifer silhouette
    "water": SpriteRef("Terrain", 0, 1),            # horizontal wave pattern
    "road": SpriteRef("Terrain", 13, 0),             # offset brick-course blocks
    "bridge": SpriteRef("Terrain", 1, 3),           # brick blocks, variant (plank tint)
    "hill": SpriteRef("Terrain", 3, 1),             # dense speckle pattern, tinted tan —
    "cobble": SpriteRef("Terrain", 11, 0),           # brick-course blocks (town cobble)
    "building_wall": SpriteRef("Terrain", 13, 0),    # cracked stone chunk
    "ruin_entrance": SpriteRef("Terrain", 14, 1),   # stairs art, tinted for a ruin
}
# Hand-picked cell-by-cell from a labelled 16x24 grid render (screenshots/
# monsters_grid_16x24.png), after fixing Monsters.png's tile size from a wrong
# 16x16 to its true 16x24 (see _SIZE_HINT) — the old 16x16 slice reflowed the
# grid from 26 rows to 39 and cut every 24px-tall sprite across a seam, so the
# earlier sequential _grid("Monsters", i, 8) placements pointed at half-sprites.
# This *Ultimate Roguelike 2.0* sheet is orc/fantasy-heavy and has no Bree-land
# brigands, so footpad/highwayman reuse the closest lithe/cloaked humanoids.
# Not yet re-confirmed on-screen with the project owner — flag if any read wrong.
_MONSTER_REFS: Dict[str, "SpriteRef"] = {
    "cave_goblin": SpriteRef("Monsters", 0, 0),    # small goblin, spear + shield
    "orc_soldier": SpriteRef("Monsters", 4, 0),    # bulky armored melee warrior
    "orc_archer": SpriteRef("Monsters", 12, 10),   # humanoid drawing a bow
    "great_spider": SpriteRef("Monsters", 7, 6),   # round body, eight radiating legs
    "wight": SpriteRef("Monsters", 17, 6),         # hooded robed wraith
    "wolf": SpriteRef("Monsters", 10, 16),         # lean canine quadruped
    "warg": SpriteRef("Monsters", 11, 16),         # larger canine quadruped
    "footpad": SpriteRef("Monsters", 0, 10),       # lithe humanoid with a blade
    "highwayman": SpriteRef("Monsters", 7, 8),     # cloaked armed humanoid
    "boar": SpriteRef("Monsters", 4, 4),           # bulky hog, head lowered
}
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
SPRITE_KEYS.update(_TERRAIN_REFS)
SPRITE_KEYS.update({k: _grid("Terrain_Objects", i, 8) for i, k in enumerate(_PROP_KEYS)})
SPRITE_KEYS.update(_MONSTER_REFS)
# Avatar.png is a 7-col×2-row grid at 16x24 (same tall tile as Terrain/Monsters,
# not the square 16x16 first assumed — the 16x16 slice cut every figure across
# the row seam; see _SIZE_HINT). Column 0 is a small marker glyph, not a figure,
# so the actual silhouettes start at column 1 (confirmed from a labelled 16x24
# grid render). Row 0's six figures cover every avatar key.
SPRITE_KEYS.update({k: _grid("Avatar", i + 1, 7) for i, k in enumerate(_AVATAR_KEYS)})
SPRITE_KEYS.update({k: _grid("Items", i, 8) for i, k in enumerate(_ITEM_KEYS)})
# The player's own figure, hand-picked off the Monsters sheet (owner's pick).
SPRITE_KEYS["player"] = SpriteRef("Monsters", 12, 2)

# The four bespoke tiles (ADR 0016 §curated hybrid coverage): each is its own
# follow-up issue and keeps the ASCII glyph forever, never a registry entry.
BESPOKE_KEYS = frozenset({"hobbit_hole", "prancing_pony", "signpost", "barrow_mound"})

# --- Portraits (ADR 0016 "dialog portraits" follow-up; issue #125) --------
# Interface_Portraits.png is a 7-col x 4-row grid of 48x48 bust silhouettes,
# the same white/alpha-mask shape as every other Oryx sheet. There's no
# per-culture/calling portrait table (out of scope, per the issue's grilling
# notes) — every entity shares one default cell unless it carries its own
# (issue #128 plugs specific-NPC portraits in later via the `portrait` field
# on lonelands.entity.Entity).
DEFAULT_PORTRAIT = SpriteRef("Portraits", 3, 0)


def portrait_ref(entity: object) -> SpriteRef:
    """The entity's own portrait cell, or the shared :data:`DEFAULT_PORTRAIT`
    bust if it doesn't carry one."""
    own = getattr(entity, "portrait", None)
    return own if own is not None else DEFAULT_PORTRAIT


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


# --- native tile size ---------------------------------------------------
# Oryx sheets are cropped tight, not padded to an exact grid multiple, so a
# sheet's tile size usually does *not* divide its pixel dimensions exactly on
# every axis — the crop just trims a partial trailing row/column
# (Terrain_Objects.png: 320px wide at a 24px tile is a clean 13 columns plus
# an 8px sliver, trimmed). An earlier version of this searched nearby sizes
# for one that divides evenly, which looks appealing but is a false-positive
# trap: Terrain_Objects.png has an unrelated exact divisor at 20px that
# slices its conifer-tree sprite in half. Tile size isn't proportional to
# sheet size, so an incidental exact divisor near the hint is noise, not
# signal — the values in _SIZE_HINT (confirmed per sheet by inspecting a
# labelled grid render) are the only trustworthy source, used as-is.


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
        self._native_size: Dict[str, tuple[int, int]] = {}
        self._cache: Dict[int, Optional["pygame.Surface"]] = {}
        self._portrait_cache: Dict[SpriteRef, Optional["pygame.Surface"]] = {}

    def base_surface(self, sid: int) -> Optional["pygame.Surface"]:
        """The white sprite surface for sprite-id ``sid``, or ``None`` if the
        id is unset (0) or its art can't be resolved — callers fall back to
        the ASCII glyph in that case, exactly like a missing codepoint."""
        if sid == 0:
            return None
        if sid not in self._cache:
            self._cache[sid] = self._make(sid)
        return self._cache[sid]

    def portrait_surface(self, entity: object) -> Optional["pygame.Surface"]:
        """The entity's portrait (its own, else the shared default bust),
        baked once at Portraits' native 48x48 size. Unlike map-field sprites
        (tinted per-cell by the drawable's own fg colour, ADR 0016 §1),
        portraits bake in a single fixed ``color.white`` ivory-cameo tint —
        a dialog-portrait-specific decision from the issue #125 grilling
        notes, not a general rule. ``None`` if there's no atlas at all
        (``LONELANDS_TILES`` unset) or the cell is out of bounds — callers
        should skip drawing a portrait entirely, not draw a blank box."""
        ref = portrait_ref(entity)
        if ref not in self._portrait_cache:
            self._portrait_cache[ref] = self._bake_portrait(ref)
        return self._portrait_cache[ref]

    def _bake_portrait(self, ref: SpriteRef) -> Optional["pygame.Surface"]:
        tile = self._slice(ref)
        if tile is None:
            return None
        surf = self._mask_surface(tile)
        if surf is None:
            return None
        tinted = surf.copy()
        tinted.fill((*color.white, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return tinted

    def _make(self, sid: int) -> Optional["pygame.Surface"]:
        key = key_for_id(sid)
        if key is None:
            return None
        ref = SPRITE_KEYS.get(key)
        if ref is None:
            return None
        tile = self._slice(ref)
        if tile is None:
            return None
        scaled = pygame.transform.smoothscale(tile, (self.cell_w, self.cell_h))
        return self._mask_surface(scaled)

    @staticmethod
    def _mask_surface(tile: "pygame.Surface") -> Optional["pygame.Surface"]:
        """``tile``'s alpha channel as a white/alpha coverage surface, via
        :func:`lonelands.fonts.mask_to_surface`."""
        mask = pygame.surfarray.array_alpha(tile)
        return fonts.mask_to_surface(np.ascontiguousarray(mask.T))

    def _slice(self, ref: SpriteRef) -> Optional["pygame.Surface"]:
        """``ref``'s cell, sliced out of its sheet at native size, or ``None``
        if the sheet can't be loaded or the cell falls outside it."""
        sheet = self._sheet(ref.sheet)
        if sheet is None:
            return None
        tile_w, tile_h = self._native_size[ref.sheet]
        rect = pygame.Rect(ref.col * tile_w, ref.row * tile_h, tile_w, tile_h)
        if not sheet.get_rect().contains(rect):
            return None
        return sheet.subsurface(rect).copy()

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
        self._native_size[name] = _SIZE_HINT.get(name, (24, 24))
        return surf
