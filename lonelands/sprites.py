"""SPIKE (issue #92, Phase 0) — a throwaway vertical slice of the sprite path.

This module proves the whole full-colour sprite pipeline end-to-end on **one
region** (Bree) behind the hidden ``--sprites`` flag, so ADR-0013's later phases
build on a de-risked seam rather than a paper design. Everything here is
deliberately hard-coded and disposable:

* one Kenney **Roguelike Base** sheet for terrain, one **Characters** sheet for
  the humanoid roster (findings: terrain and characters live on *separate* sheets,
  so Phase 1's ``sprite key -> (sheet, col, row)`` table must carry a sheet id);
* a tiny :data:`SPRITE_KEYS` table for the nine spike keys (grass, road, stone,
  wall, door, tree, townsman, orc, ranger), plus a paper-doll crowd
  (:func:`crowd_layers`) that mixes body + clothing + hair so the race-lettered
  wanderers don't all look alike;
* codepoint/kind reverse-mapping to pick a key per cell (Phase 1 replaces this
  with an explicit ``sprite_key`` on every tile type and entity);
* a two-layer blit — terrain, then entities — over the map viewport, in square
  16×16 cells, with **remembered** tiles dimmed and **unseen** left black.

The ASCII path is untouched: with the flag off nothing here runs, and with the
sheets absent the overlay simply draws nothing (the ASCII map shows through).
"""
from __future__ import annotations

import os
import random
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import numpy as np
import pygame

from lonelands import config, tile_glyphs, tile_types

if TYPE_CHECKING:
    from lonelands.game_map import GameMap

# Kenney sheets are 16×16 tiles with a 1px margin between them (NOT the CP437
# packing of the Wanderlust sheet). A tile at grid (col, row) therefore starts at
# pixel (col*STEP, row*STEP).
TILE = 16
MARGIN = 1
STEP = TILE + MARGIN

# Tone grade (SPIKE #92): the Kenney art is bright and cheery; the North is not.
# Every baked sprite is pushed through one transform — darkened, desaturated
# toward its own grey, and warmed slightly — so the map reads weathered and
# Tolkien-somber while keeping each tile's internal shading (this is NOT the flat
# fg-tint ADR-0013 rules out). ``darken`` scales brightness, ``desat`` is the
# fraction mixed toward luma grey (0 = untouched, 1 = greyscale), ``tint`` is a
# per-channel multiplier for a warm/cool cast. Identity = (1.0, 0.0, (1,1,1)).
GRADE: Dict[str, object] = {
    "darken": 0.78,
    "desat": 0.32,
    "tint": (1.02, 0.98, 0.86),  # a touch of amber/olive, cooler blue
}


def _grade(surf: "pygame.Surface") -> "pygame.Surface":
    """Apply the :data:`GRADE` tone transform to ``surf`` in place (RGB only;
    the alpha shape is untouched, so transparent margins stay transparent)."""
    darken = float(GRADE["darken"])          # type: ignore[arg-type]
    desat = float(GRADE["desat"])            # type: ignore[arg-type]
    tint = GRADE["tint"]
    if darken == 1.0 and desat == 0.0 and tuple(tint) == (1, 1, 1):  # type: ignore[arg-type]
        return surf
    arr = pygame.surfarray.pixels3d(surf)    # (w, h, 3) view; locks the surface
    rgb = arr.astype(np.float32)
    luma = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    graded = rgb * (1.0 - desat) + luma[..., None] * desat
    graded *= np.array(tint, np.float32) * darken
    arr[:] = np.clip(graded, 0, 255).astype(np.uint8)
    del arr                                   # unlock the surface
    return surf

_TILES = os.path.join(os.path.dirname(__file__), "assets", "tiles")
# Kenney source dir (the repo's bundled asset library) as a fallback, so the
# spike runs even before the sheets are copied into assets/tiles/.
_KENNEY = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir,
    "Kenney Game Assets All-in-1", "2D assets",
)

# Where each logical sheet may be found, best first.
SHEET_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "base": (
        os.path.join(_TILES, "roguelike_base.png"),
        os.path.join(_KENNEY, "Roguelike Base Pack", "Spritesheet",
                     "roguelikeSheet_transparent.png"),
    ),
    "chars": (
        os.path.join(_TILES, "roguelike_chars.png"),
        os.path.join(_KENNEY, "Roguelike Characters Pack", "Spritesheet",
                     "roguelikeChar_transparent.png"),
    ),
}

# The nine spike keys -> (sheet, col, row). Hand-picked from the sheets; see the
# module docstring. Phase 1 turns this into the data-driven source of truth.
SPRITE_KEYS: Dict[str, Tuple[str, int, int]] = {
    # Terrain (Roguelike Base sheet)
    "grass": ("base", 5, 0),
    "road": ("base", 6, 0),     # bare dirt / trodden path
    "stone": ("base", 7, 0),    # grey paving — cobble / dungeon floor
    "wall": ("base", 30, 13),   # grey stone wall block
    "door": ("base", 34, 13),   # wooden door panel
    "tree": ("base", 13, 9),    # round broad-leaf tree
    # Characters (Roguelike Characters sheet)
    "townsman": ("chars", 0, 8),
    "orc": ("chars", 0, 3),     # green humanoid
    "ranger": ("chars", 0, 7),  # the player + hand-authored @-folk
}


def resolve_terrain(kind: int, light_cp: int) -> Optional[str]:
    """Sprite key for a terrain cell, from its semantic ``kind`` and lit glyph
    codepoint — or ``None`` when this spike has no tile for it (the cell then
    shows nothing, i.e. the ASCII fallback below it)."""
    if kind == tile_types.KIND_ROAD:
        return "road"
    if kind == tile_types.KIND_DOOR:
        return "door"
    ch = tile_glyphs.graphic_source_char(light_cp)
    return {
        "#": "wall",
        "T": "tree",
        "n": "grass",   # hill — a grassy rise; no bespoke tile in the spike
        '"': "grass",
        ",": "grass",
        ".": "stone",   # floor / cobble (road is caught by KIND_ROAD above)
        "%": "stone",   # rubble
    }.get(ch or "")


def resolve_entity(char: str) -> Optional[str]:
    """Sprite key for an entity from its ASCII ``char`` — or ``None`` to skip it
    (dropped items and creatures this spike doesn't cover).

    The single-tile fallback: the render path prefers :func:`crowd_layers` for the
    race-lettered folk (so they vary), and only falls back to the flat
    ``townsman`` tile here if that returns nothing."""
    if char == "@":                       # player + hand-authored principals
        return "ranger"
    if char in ("o", "O"):                # orcs
        return "orc"
    if char in ("m", "h", "d"):           # the race-lettered crowd (ADR-0009)
        return "townsman"
    return None


# --- The layered crowd (mixing body + clothing + hair) --------------------
# The Kenney Characters sheet is a paper-doll: a plain body, then a clothing
# (torso) tile, then a hair/hat tile, each 16×16 and stacked with transparency.
# Rather than clone one finished figure, the race-lettered wanderers each pick a
# stack, so a Bree street reads as a varied crowd. Layers are ``(sheet, col,
# row)`` on the characters sheet; Phase 1 promotes these hand-picked sets into
# the race→sprite table (the way ADR-0009 maps race→letter).
Layer = Tuple[str, int, int]

_BODIES: Tuple[Layer, ...] = (
    ("chars", 0, 0),   # pale
    ("chars", 0, 1),   # tan
    ("chars", 0, 2),   # brown
)
# Torsos: tunics, coats, robes, and leathers across the colour range.
_CLOTHES: Tuple[Layer, ...] = (
    ("chars", 6, 0), ("chars", 10, 0), ("chars", 14, 0),   # orange, teal, purple
    ("chars", 5, 5), ("chars", 10, 4), ("chars", 14, 4),   # green, grey, brown
    ("chars", 5, 9), ("chars", 10, 6), ("chars", 14, 9),   # red, leather, amber
    ("chars", 6, 4),                                        # belted orange
)
# Hair/hats without a beard (hobbits, most men).
_HAIR_PLAIN: Tuple[Layer, ...] = (
    ("chars", 22, 1), ("chars", 25, 0), ("chars", 20, 4), ("chars", 24, 5),
    ("chars", 22, 2), ("chars", 25, 1), ("chars", 20, 1), ("chars", 24, 1),
)
# Beards and a weathered hood — the bearded folk (dwarves; some older men).
_HAIR_BEARD: Tuple[Layer, ...] = (
    ("chars", 24, 4), ("chars", 20, 10),
)

# Per-race wardrobe: (body pool, clothing pool, hair pool). Men draw from
# everything; hobbits skip beards; dwarves are always bearded and earthy-clad.
_EARTHY = (("chars", 5, 5), ("chars", 10, 4), ("chars", 14, 4),
           ("chars", 10, 6), ("chars", 5, 9))
_WARDROBE: Dict[str, Tuple[Tuple[Layer, ...], Tuple[Layer, ...], Tuple[Layer, ...]]] = {
    "m": (_BODIES, _CLOTHES, _HAIR_PLAIN + _HAIR_BEARD),
    "h": ((("chars", 0, 0), ("chars", 0, 1)), _CLOTHES, _HAIR_PLAIN),
    "d": ((("chars", 0, 1), ("chars", 0, 2)), _EARTHY, _HAIR_BEARD),
}


def crowd_layers(char: str, seed: int) -> Optional[Tuple[Layer, ...]]:
    """A deterministic body+clothing+hair stack for a race-lettered wanderer, or
    ``None`` for anything that isn't one (the player, orcs, items).

    ``seed`` fixes the choice, so a given wanderer keeps its look frame to frame;
    passing the entity's identity gives a varied but stable crowd. (Across
    save/load the look re-rolls — fine for the spike; Phase 1 seeds it from a
    persisted identity.)"""
    wardrobe = _WARDROBE.get(char)
    if wardrobe is None:
        return None
    bodies, clothes, hair = wardrobe
    rng = random.Random(seed)
    stack: List[Layer] = [rng.choice(bodies), rng.choice(clothes)]
    # A few folk go bare-headed — but a dwarf is never beardless.
    bare = char != "d" and rng.random() < 0.12
    if hair and not bare:
        stack.append(rng.choice(hair))
    return tuple(stack)


class SpriteMap:
    """Loads the spike's sheets and blits a two-layer sprite map at a fixed
    square cell size. Rebuilt (a new instance) when the cell size changes, like
    :class:`lonelands.fonts.GlyphAtlas`."""

    def __init__(self, cell: int):
        self.cell = cell
        self._sheets: Dict[str, Optional[pygame.Surface]] = {
            name: self._load(paths) for name, paths in SHEET_CANDIDATES.items()
        }
        # Cache of composited cell-sized surfaces, keyed by (layer stack, dimmed?).
        self._cache: Dict[Tuple[Tuple[Layer, ...], bool], Optional[pygame.Surface]] = {}

    @staticmethod
    def _load(paths: Tuple[str, ...]) -> Optional[pygame.Surface]:
        for path in paths:
            if os.path.exists(path):
                try:
                    # Unlike fonts._load_tilesheet (which reads only alpha and so
                    # loads raw), we blit these sheets full-colour, so convert_alpha
                    # is worth its display-mode dependency — the Display always has
                    # a mode set before it builds a SpriteMap, and rebuilds on resize.
                    return pygame.image.load(path).convert_alpha()
                except Exception:  # noqa: BLE001 - any load failure -> no sheet
                    continue
        return None

    @property
    def ready(self) -> bool:
        """True if at least the terrain sheet loaded (so the overlay is worth
        drawing at all)."""
        return self._sheets.get("base") is not None

    def _tile(self, key: str, dim: bool) -> Optional[pygame.Surface]:
        """The surface for a single sprite key (terrain or a flat character)."""
        spec = SPRITE_KEYS.get(key)
        if spec is None:
            return None
        return self._composite((spec,), dim)

    def _composite(self, layers: Tuple[Layer, ...], dim: bool
                   ) -> Optional[pygame.Surface]:
        """One cell-sized surface built by stacking ``layers`` (bottom-first),
        cached by the stack. A single-element stack is a plain tile; a
        body+clothing+hair stack is a paper-doll character."""
        cache_key = (layers, dim)
        if cache_key in self._cache:
            return self._cache[cache_key]
        surf = self._build(layers, dim)
        self._cache[cache_key] = surf
        return surf

    def _build(self, layers: Tuple[Layer, ...], dim: bool
               ) -> Optional[pygame.Surface]:
        out: Optional[pygame.Surface] = None
        for sheet_name, col, row in layers:
            sheet = self._sheets.get(sheet_name)
            if sheet is None:
                continue
            src = sheet.subsurface((col * STEP, row * STEP, TILE, TILE))
            # transform.scale duplicates pixels (no smoothing) -> crisp at integer
            # multiples of 16, merely blocky otherwise. Copy so we own the pixels.
            tile = pygame.transform.scale(src.copy(), (self.cell, self.cell))
            if out is None:
                out = tile
            else:
                out.blit(tile, (0, 0))  # alpha-composite the layer over the stack
        if out is not None:
            _grade(out)                 # tone the assembled sprite (before FOV dim)
        if out is not None and dim:
            # Remembered tiles: the same sprite, darkened (ADR-0013's FOV-by-
            # dimming, not palette-swap). Multiply keeps the alpha shape.
            out.fill((110, 110, 110, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return out

    def render(self, screen: pygame.Surface, offset: Tuple[int, int],
               game_map: "GameMap") -> None:
        """Composite the map viewport as sprites onto ``screen``.

        Two passes over the viewport: terrain first (opaque, dimmed where the
        tile is remembered but out of sight), then the entity layer over it
        (only where currently visible). Unseen cells are skipped, so the black
        console shroud shows through."""
        if not self.ready:
            return
        ox, oy = offset
        cell = self.cell
        cols = min(game_map.width, config.MAP_WIDTH)
        rows = min(game_map.height, config.MAP_HEIGHT)
        tiles = game_map.tiles
        visible = game_map.visible
        explored = game_map.explored

        # --- terrain layer ---
        blits = []
        for x in range(cols):
            for y in range(rows):
                seen = bool(visible[x, y])
                if not seen and not bool(explored[x, y]):
                    continue  # unseen -> leave black
                cell_t = tiles[x, y]
                key = resolve_terrain(int(cell_t["kind"]), int(cell_t["light"]["ch"]))
                if key is None:
                    continue
                tile = self._tile(key, dim=not seen)
                if tile is not None:
                    blits.append((tile, (ox + x * cell, oy + y * cell)))
        if blits:
            screen.blits(blits, doreturn=False)

        # --- entity layer (visible cells only, painter-ordered) ---
        entities = sorted(game_map.entities, key=lambda e: e.render_order.value)
        ent_blits = []
        for e in entities:
            if not (0 <= e.x < cols and 0 <= e.y < rows):
                continue
            if not bool(visible[e.x, e.y]):
                continue
            # Prefer a mixed body+clothing+hair stack for the race-lettered crowd
            # (varied but stable per entity); fall back to a flat sprite key.
            layers = crowd_layers(e.char, id(e))
            if layers is not None:
                tile = self._composite(layers, dim=False)
            else:
                key = resolve_entity(e.char)
                tile = self._tile(key, dim=False) if key is not None else None
            if tile is not None:
                ent_blits.append((tile, (ox + e.x * cell, oy + e.y * cell)))
        if ent_blits:
            screen.blits(ent_blits, doreturn=False)
