"""Tile definitions backed by numpy structured arrays.

Every tile carries two graphics: `light` (currently in view) and `dark`
(remembered but out of sight), which is what gives the map that soft,
memory-shaded Brogue look."""
from __future__ import annotations

from typing import Tuple

import numpy as np

from lonelands import color, sprites

graphic_dt = np.dtype(
    [
        ("ch", np.int32),
        ("fg", "3B"),
        ("bg", "3B"),
        ("sprite", np.int32),  # ADR 0016: sprites.sprite_id(key), 0 = ASCII only
    ]
)

tile_dt = np.dtype(
    [
        ("walkable", np.bool_),
        ("transparent", np.bool_),
        ("dark", graphic_dt),
        ("light", graphic_dt),
        ("kind", np.int8),  # semantic id, see KIND_* below
    ]
)

# Semantic kinds so game logic can ask "is this a stair / door / water?"
KIND_GENERIC = 0
KIND_DOWN = 1
KIND_UP = 2
KIND_DOOR = 3
KIND_WATER = 4
KIND_RUIN_ENTRANCE = 5
# (6 was KIND_TOWN_EXIT — retired: Regions are left by walking off an edge,
#  not by standing on a gate tile. Enter is now reserved for vertical Levels.)
KIND_ROAD = 7  # road / bridge / ford — the tile arrival-mirroring snaps onto


def new_tile(
    *,
    walkable: bool,
    transparent: bool,
    dark: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
    light: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
    kind: int = KIND_GENERIC,
    sprite: str = "",
) -> np.ndarray:
    """``sprite`` is a key into ``sprites.SPRITE_KEYS`` (ADR 0016) — the same
    tile art for both the ``dark``/``light`` memory-shading variants, only the
    tint differs. Empty means "no sprite; ASCII always" (a bespoke tile)."""
    sid = sprites.sprite_id(sprite)
    return np.array((walkable, transparent, (*dark, sid), (*light, sid), kind), dtype=tile_dt)


# Unexplored / out-of-knowledge tiles.
SHROUD = np.array((ord(" "), color.black, color.black, 0), dtype=graphic_dt)

# --- Ruin / dungeon --------------------------------------------------------
floor = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord("."), color.floor_dark, color.black),
    light=(ord("."), color.floor_light, (0x1A, 0x18, 0x14)),
    sprite="floor",
)
wall = new_tile(
    walkable=False,
    transparent=False,
    dark=(ord("#"), color.wall_dark, color.black),
    light=(ord("#"), color.wall_light, (0x22, 0x1E, 0x18)),
    sprite="wall",
)
rubble = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord("%"), (0x3A, 0x36, 0x30), color.black),
    light=(ord("%"), (0x74, 0x6A, 0x58), (0x1A, 0x18, 0x14)),
    sprite="rubble",
)
down_stairs = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord(">"), (0x5A, 0x54, 0x48), color.black),
    light=(ord(">"), (0xE0, 0xD0, 0x90), (0x22, 0x1E, 0x18)),
    kind=KIND_DOWN,
    sprite="down_stairs",
)
up_stairs = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord("<"), (0x5A, 0x54, 0x48), color.black),
    light=(ord("<"), (0xE0, 0xD0, 0x90), (0x22, 0x1E, 0x18)),
    kind=KIND_UP,
    sprite="up_stairs",
)
door = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord("+"), (0x6A, 0x50, 0x34), color.black),
    light=(ord("+"), (0xB0, 0x86, 0x4A), (0x22, 0x1E, 0x18)),
    kind=KIND_DOOR,
    sprite="door",
)

# --- Wilderness (overworld) -----------------------------------------------
grass = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord('"'), color.grass_dark, color.black),
    light=(ord('"'), color.grass_light, (0x18, 0x1E, 0x12)),
    sprite="grass",
)
grass_low = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord(","), color.grass_dark, color.black),
    light=(ord(","), (0x4E, 0x64, 0x3A), (0x16, 0x1C, 0x10)),
    sprite="grass_low",
)
tree = new_tile(
    walkable=False,
    transparent=False,
    dark=(ord("T"), color.tree_dark, color.black),
    light=(ord("T"), color.tree_light, (0x14, 0x1C, 0x10)),
    sprite="tree",
)
water = new_tile(
    walkable=False,
    transparent=True,
    dark=(ord("~"), color.water_dark, (0x10, 0x18, 0x22)),
    light=(ord("~"), color.water_light, (0x18, 0x28, 0x3A)),
    kind=KIND_WATER,
    sprite="water",
)
road = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord("."), color.road_dark, color.black),
    light=(ord("."), color.road_light, (0x22, 0x1E, 0x16)),
    kind=KIND_ROAD,
    sprite="road",
)
bridge = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord("="), (0x5A, 0x46, 0x30), color.black),
    light=(ord("="), (0x9A, 0x78, 0x4E), (0x22, 0x1E, 0x16)),
    kind=KIND_ROAD,   # a road that carries over water — snappable like any road
    sprite="bridge",
)
hill = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord("n"), (0x40, 0x3A, 0x2E), color.black),
    light=(ord("n"), (0x7A, 0x6E, 0x54), (0x1C, 0x1A, 0x14)),
    sprite="hill",
)

# --- Town ------------------------------------------------------------------
cobble = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord("."), (0x38, 0x34, 0x2E), color.black),
    light=(ord("."), (0x7C, 0x74, 0x64), (0x20, 0x1E, 0x1A)),
    sprite="cobble",
)
building_wall = new_tile(
    walkable=False,
    transparent=False,
    dark=(ord("#"), (0x4A, 0x3E, 0x30), color.black),
    light=(ord("#"), (0x8C, 0x74, 0x52), (0x24, 0x1E, 0x16)),
    sprite="building_wall",
)
ruin_entrance = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord(">"), (0x5A, 0x54, 0x48), color.black),
    light=(ord(">"), (0xE0, 0xC0, 0x70), (0x22, 0x1E, 0x18)),
    kind=KIND_RUIN_ENTRANCE,
    sprite="ruin_entrance",
)

# --- Furniture -------------------------------------------------------------
# Wood props for building interiors (the Prancing Pony common room, etc.). No
# sprite key yet: Terrain_Objects.png has furniture, but the cells aren't
# owner-confirmed and the art isn't committed, so these stay ASCII-only (a
# warm oak brown) for now — a table blocks the tile, a stool is walkable so a
# patron can stand on it as if seated.
table = new_tile(
    walkable=False,
    transparent=True,
    dark=(0x03C0, (0x5A, 0x42, 0x2A), color.black),        # 'π' — a table
    light=(0x03C0, (0x9C, 0x76, 0x48), (0x22, 0x1E, 0x16)),
    sprite="",
)
stool = new_tile(
    walkable=True,
    transparent=True,
    dark=(0x2022, (0x52, 0x3C, 0x26), color.black),        # '•' — a stool
    light=(0x2022, (0x88, 0x66, 0x42), (0x22, 0x1E, 0x16)),
    sprite="",
)
