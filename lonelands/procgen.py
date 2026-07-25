"""Map generation for the Regions of the starting grid — Bree at the centre,
the Weather Hills (with the descending barrow) to the east, and the near-empty
Barrow-downs, Chetwood, and South Downs around it.

Each `generate_*` returns the **Surface** of one Region. A Surface is edge-open:
the player leaves it by walking off any edge (see `world.GameWorld.cross_edge`),
so no map carries a "gate" tile any more — Enter is reserved for stairs and the
barrow entrance (the vertical axis)."""
from __future__ import annotations

from typing import List, Tuple

from lonelands import content, story, tile_types
from lonelands.config import MAP_HEIGHT, MAP_WIDTH
from lonelands.dice import rng
from lonelands.entity import Item
from lonelands.game_map import GameMap

MAX_RUIN_DEPTH = 3


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
class RectRoom:
    def __init__(self, x: int, y: int, w: int, h: int):
        self.x1, self.y1 = x, y
        self.x2, self.y2 = x + w, y + h

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2

    @property
    def inner(self):
        return slice(self.x1 + 1, self.x2), slice(self.y1 + 1, self.y2)

    def intersects(self, other: "RectRoom") -> bool:
        return (
            self.x1 <= other.x2 and self.x2 >= other.x1
            and self.y1 <= other.y2 and self.y2 >= other.y1
        )


def _weighted(table):
    total = sum(w for _, w in table)
    r = rng.uniform(0, total)
    upto = 0
    for item, w in table:
        upto += w
        if r <= upto:
            return item
    return table[-1][0]


def _line(x1, y1, x2, y2):
    """Yield an L-shaped path of coordinates from (x1,y1) to (x2,y2)."""
    if rng.random() < 0.5:
        cx, cy = x2, y1
    else:
        cx, cy = x1, y2
    x, y = x1, y1
    while x != cx:
        x += 1 if cx > x else -1
        yield x, y
    while y != cy:
        y += 1 if cy > y else -1
        yield x, y
    while x != x2:
        x += 1 if x2 > x else -1
        yield x, y
    while y != y2:
        y += 1 if y2 > y else -1
        yield x, y


# ---------------------------------------------------------------------------
# Bree — the hub Region (TA 2965)
# ---------------------------------------------------------------------------
def generate_bree(engine) -> GameMap:
    """Bree at the meeting of the roads: a hedge-ringed town where the Great
    East Road (E–W) crosses the Greenway (N–S). Each of the four roads leaves
    through a gate-gap in the hedge, so the player can walk off any edge into
    the neighbouring Region."""
    w, h = MAP_WIDTH, MAP_HEIGHT
    gm = GameMap(engine, w, h, name="Bree, at the meeting of the roads", outdoors=True)
    gm.tiles[:] = tile_types.grass

    for x in range(w):
        for y in range(h):
            if rng.random() < 0.10:
                gm.tiles[x, y] = tile_types.grass_low

    # Bree-hill: a modest rise on the north-east skirts of the town (walkable
    # flavour, well clear of the roads and gates).
    for x in range(w - 5, w - 1):
        for y in range(1, 9):
            if rng.random() < 0.5:
                gm.tiles[x, y] = tile_types.hill

    gate_x, gate_y = w // 2, h // 2

    # The two great roads, laid first so the hedge can be punched through them.
    gm.tiles[:, gate_y] = tile_types.road          # the Great East Road (E–W)
    gm.tiles[gate_x, :] = tile_types.road          # the Greenway (N–S)

    # The hedge (dike-and-hedge), with a gate-gap where each road passes.
    hx0, hy0, hx1, hy1 = 5, 3, w - 6, h - 4
    gm.tiles[hx0:hx1 + 1, hy0] = tile_types.building_wall
    gm.tiles[hx0:hx1 + 1, hy1] = tile_types.building_wall
    gm.tiles[hx0, hy0:hy1 + 1] = tile_types.building_wall
    gm.tiles[hx1, hy0:hy1 + 1] = tile_types.building_wall
    gm.tiles[hx0 + 1:hx1, hy0 + 1:hy1] = tile_types.cobble
    # Re-lay the roads across the interior as cobble, and re-open the four gates.
    gm.tiles[hx0 + 1:hx1, gate_y] = tile_types.cobble
    gm.tiles[gate_x, hy0 + 1:hy1] = tile_types.cobble
    for gx, gy in ((gate_x, hy0), (gate_x, hy1), (hx0, gate_y), (hx1, gate_y)):
        gm.tiles[gx, gy] = tile_types.road

    def building(bx, by, bw, bh):
        gm.tiles[bx:bx + bw, by] = tile_types.building_wall
        gm.tiles[bx:bx + bw, by + bh - 1] = tile_types.building_wall
        gm.tiles[bx, by:by + bh] = tile_types.building_wall
        gm.tiles[bx + bw - 1, by:by + bh] = tile_types.building_wall
        gm.tiles[bx + 1:bx + bw - 1, by + 1:by + bh - 1] = tile_types.floor
        gm.tiles[bx + bw // 2, by + bh - 1] = tile_types.door

    building(14, 6, 12, 8)          # The Prancing Pony (the great inn)
    building(40, 7, 9, 6)           # the moot-hall
    building(9, 30, 9, 6)           # the herb-wife's cot
    building(42, 30, 9, 6)          # a Bree-folk home

    elder, healer, halbarad, innkeeper = story.make_town_npcs()
    elder.spawn(gm, 44, 14)         # Dírhael, by the moot-hall
    healer.spawn(gm, 13, 28)        # the herb-wife, by her cot
    halbarad.spawn(gm, 7, 20)       # Halbarad, near the West-gate
    innkeeper.spawn(gm, 19, 15)     # the Butterbur, before the Pony's door

    gm.entry_xy = (gate_x, gate_y)              # fallback landing = the crossroads
    gm.start_xy = (gate_x, gate_y)              # a new game begins in the square
    return gm


# ---------------------------------------------------------------------------
# The Weather Hills — the east Region, holding the barrow entrance
# ---------------------------------------------------------------------------
def generate_weather_hills(engine) -> GameMap:
    w, h = MAP_WIDTH, MAP_HEIGHT
    gm = GameMap(engine, w, h, name="The Weather Hills, east of Bree", outdoors=True)
    gm.tiles[:] = tile_types.grass

    for x in range(w):
        for y in range(h):
            r = rng.random()
            if r < 0.06:
                gm.tiles[x, y] = tile_types.tree
            elif r < 0.20:
                gm.tiles[x, y] = tile_types.grass_low

    # Forest belt along the north
    for x in range(w):
        for y in range(0, 4):
            if rng.random() < 0.6:
                gm.tiles[x, y] = tile_types.tree

    # A river running north-south, with a ford/bridge
    river_x = w // 2 - 3
    ford_y = h // 2
    for y in range(h):
        rx = river_x + (1 if (y % 6) < 3 else 0)
        for dx in range(-1, 2):
            gm.tiles[rx + dx, y] = tile_types.water
    for dx in range(-2, 3):
        gm.tiles[river_x + dx, ford_y] = tile_types.bridge

    # Hills in the east where the ruin lies
    for x in range(w - 20, w - 4):
        for y in range(6, h - 8):
            if rng.random() < 0.25:
                gm.tiles[x, y] = tile_types.hill

    ruin_xy = (w - 6, ford_y)

    # The old road runs west-edge -> ford -> the barrow, so the player arriving
    # from Bree on the west can follow it east to the ruin.
    for x in range(0, river_x - 1):
        gm.tiles[x, ford_y] = tile_types.road
    for x in range(river_x + 3, ruin_xy[0] + 1):
        gm.tiles[x, ford_y] = tile_types.road

    # The barrow entrance (Enter here to descend into the deeps).
    gm.tiles[ruin_xy] = tile_types.ruin_entrance
    gm.ruin_entrance_xy = ruin_xy
    gm.barrow_entrance_xy = ruin_xy   # where the player surfaces from the deeps

    # Wild beasts roam the open ground
    for _ in range(rng.randint(3, 5)):
        bx, by = rng.randint(6, w - 6), rng.randint(4, h - 4)
        if gm.tiles["walkable"][bx, by] and gm.get_blocking_entity_at(bx, by) is None:
            _weighted(content.WILD_BEASTS).spawn(gm, bx, by)

    gm.entry_xy = (1, ford_y)   # fallback landing = just inside the west edge
    return gm


# ---------------------------------------------------------------------------
# The near-empty neighbour Regions (proving out the grid; enrich later)
# ---------------------------------------------------------------------------
def _open_surface(engine, name, *, tree_chance, low_chance, beast_range=(2, 4)):
    """A sparse outdoor Surface: grass with scattered terrain and a wandering
    beast or two. Shared skeleton for the three empty neighbour Regions."""
    w, h = MAP_WIDTH, MAP_HEIGHT
    gm = GameMap(engine, w, h, name=name, outdoors=True)
    gm.tiles[:] = tile_types.grass
    for x in range(w):
        for y in range(h):
            r = rng.random()
            if r < tree_chance:
                gm.tiles[x, y] = tile_types.tree
            elif r < tree_chance + low_chance:
                gm.tiles[x, y] = tile_types.grass_low

    for _ in range(rng.randint(*beast_range)):
        bx, by = rng.randint(2, w - 3), rng.randint(2, h - 3)
        if gm.tiles["walkable"][bx, by] and gm.get_blocking_entity_at(bx, by) is None:
            _weighted(content.WILD_BEASTS).spawn(gm, bx, by)

    gm.entry_xy = (w // 2, h // 2)
    gm.start_xy = (w // 2, h // 2)
    return gm


def generate_barrow_downs(engine) -> GameMap:
    # Open, treeless downs south of the Old Forest — barrow-country (empty now).
    return _open_surface(engine, "The Barrow-downs", tree_chance=0.02, low_chance=0.22)


def generate_chetwood(engine) -> GameMap:
    # The wooded country north of Bree.
    return _open_surface(engine, "The Chetwood, north of Bree", tree_chance=0.16, low_chance=0.16)


def generate_south_downs(engine) -> GameMap:
    # Rolling downs along the Greenway, south of Bree.
    return _open_surface(engine, "The South Downs", tree_chance=0.04, low_chance=0.20)


# ---------------------------------------------------------------------------
# The Barrow of Amon Gûl (dungeon)
# ---------------------------------------------------------------------------
def generate_ruin(engine, depth: int) -> GameMap:
    w, h = MAP_WIDTH, MAP_HEIGHT
    gm = GameMap(engine, w, h, name=f"The Barrow of Amon Gûl — depth {depth}")
    gm.tiles[:] = tile_types.wall

    rooms: List[RectRoom] = []
    max_rooms = 14
    for _ in range(max_rooms):
        rw = rng.randint(6, 12)
        rh = rng.randint(4, 8)
        x = rng.randint(1, w - rw - 2)
        y = rng.randint(1, h - rh - 2)
        new_room = RectRoom(x, y, rw, rh)
        if any(new_room.intersects(other) for other in rooms):
            continue
        gm.tiles[new_room.inner] = tile_types.floor
        if rooms:
            for cx, cy in _line(*rooms[-1].center, *new_room.center):
                gm.tiles[cx, cy] = tile_types.floor
        rooms.append(new_room)

    if not rooms:  # degenerate safety
        rooms.append(RectRoom(10, 10, 8, 6))
        gm.tiles[rooms[0].inner] = tile_types.floor

    # Rubble flavour
    for room in rooms:
        for _ in range(rng.randint(0, 3)):
            rx = rng.randint(room.x1 + 1, room.x2 - 1)
            ry = rng.randint(room.y1 + 1, room.y2 - 1)
            gm.tiles[rx, ry] = tile_types.rubble

    # Up stair in the first room
    up = rooms[0].center
    gm.tiles[up] = tile_types.up_stairs
    gm.entry_xy = up

    # Down stair or the heirloom in the last room
    last = rooms[-1].center
    if depth < MAX_RUIN_DEPTH:
        gm.tiles[last] = tile_types.down_stairs
        gm.down_xy = last
    else:
        brooch = content.star_brooch.spawn(gm, *last)
        brooch.pickup_event = "heirloom"

    # Populate the middle rooms
    for room in rooms[1:]:
        _populate_room(gm, room, depth)

    return gm


def _populate_room(gm: GameMap, room: RectRoom, depth: int) -> None:
    n_monsters = rng.randint(0, 2 + depth // 2)
    n_items = rng.randint(0, 2)
    m_table = content.monsters_for_depth(depth)
    i_table = content.items_for_depth(depth)

    def free_spot():
        for _ in range(20):
            x = rng.randint(room.x1 + 1, room.x2 - 1)
            y = rng.randint(room.y1 + 1, room.y2 - 1)
            if gm.tiles["walkable"][x, y] and gm.get_blocking_entity_at(x, y) is None:
                if int(gm.tiles["kind"][x, y]) == 0:
                    return x, y
        return None

    for _ in range(n_monsters):
        spot = free_spot()
        if spot:
            _weighted(m_table).spawn(gm, *spot)

    for _ in range(n_items):
        spot = free_spot()
        if spot and any(it.x == spot[0] and it.y == spot[1] for it in gm.items) is False:
            _weighted(i_table).spawn(gm, *spot)
