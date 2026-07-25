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
    """Bree at the meeting of the roads. The Great East Road (E–W) and the
    Greenway (N–S) cross at a little market square; a green dike-and-hedge rings
    the town, pierced by four gates; the Prancing Pony stands at the crossing
    with its stable-yard, and Bree-hill rises to the east, hobbit-holes dug into
    its western face. The four roads run out to the map edges, so the player
    leaves for a neighbouring Region simply by walking off an edge."""
    w, h = MAP_WIDTH, MAP_HEIGHT
    gm = GameMap(engine, w, h, name="Bree, at the meeting of the roads", outdoors=True)
    T = tile_types

    # --- the ground: meadow, with Bree-hill heaped up in the east ---------
    gm.tiles[:] = T.grass
    for x in range(w):
        for y in range(h):
            if rng.random() < 0.09:
                gm.tiles[x, y] = T.grass_low
    for x in range(46, w):
        for y in range(h):
            # the hill climbs steeper (denser) toward the eastern skyline
            if rng.random() < 0.30 + 0.5 * (x - 46) / (w - 46):
                gm.tiles[x, y] = T.hill
            elif rng.random() < 0.12:
                gm.tiles[x, y] = T.tree

    RX0, RY0, RX1, RY1 = 21, 21, 23, 23    # the 3-wide road bands (the crossing)
    cx, cy = 22, 22                        # the heart of the market square

    # --- the dike-and-hedge, an octagon rather than a fort ----------------
    ex0, ey0, ex1, ey1 = 3, 3, 45, 40
    c = 4                                  # chamfer: rounds off the corners
    def hedge(x, y):
        if gm.in_bounds(x, y):
            gm.tiles[x, y] = T.tree
    for x in range(ex0 + c, ex1 - c + 1):
        hedge(x, ey0); hedge(x, ey1)
    for y in range(ey0 + c, ey1 - c + 1):
        hedge(ex0, y); hedge(ex1, y)
    for i in range(c + 1):                 # the four chamfered corners
        hedge(ex0 + c - i, ey0 + i); hedge(ex1 - c + i, ey0 + i)
        hedge(ex0 + c - i, ey1 - i); hedge(ex1 - c + i, ey1 - i)
    # a shallow dike (worn low grass) hugging the hedge on the outside
    for x in range(ex0 - 1, ex1 + 2):
        for y in range(ey0 - 1, ey1 + 2):
            if gm.in_bounds(x, y) and int(gm.tiles["kind"][x, y]) == 0 \
                    and gm.tiles[x, y] == T.grass \
                    and not (ex0 < x < ex1 and ey0 < y < ey1):
                gm.tiles[x, y] = T.grass_low

    # --- streets: the two roads, side lanes, and the market square --------
    gm.tiles[ex0 + 1:ex1, RY0:RY1 + 1] = T.cobble       # Great East Road (inside)
    gm.tiles[RX0:RX1 + 1, ey0 + 1:ey1] = T.cobble       # the Greenway (inside)
    gm.tiles[18:28, 18:28] = T.cobble                    # the market square
    gm.tiles[8:20, 12] = T.cobble                        # a north-side lane
    gm.tiles[8:41, 33] = T.cobble                        # a south-side lane
    gm.tiles[34, 7:34] = T.cobble                        # an east cross-lane

    def building(x0, y0, x1, y1, door):
        gm.tiles[x0:x1 + 1, y0] = T.building_wall
        gm.tiles[x0:x1 + 1, y1] = T.building_wall
        gm.tiles[x0, y0:y1 + 1] = T.building_wall
        gm.tiles[x1, y0:y1 + 1] = T.building_wall
        gm.tiles[x0 + 1:x1, y0 + 1:y1] = T.floor
        gm.tiles[door] = T.door

    # --- The Prancing Pony: an inn hall with a walled stable-yard ---------
    building(11, 9, 20, 20, door=(15, 20))       # outer walls; archway on the Road
    gm.tiles[12:20, 15:20] = T.cobble            # the coach-yard (open, cobbled)
    gm.tiles[15, 14] = T.door                    # hall door, yard -> common-room
    gm.tiles[15, 20] = T.door                    # the great archway onto the street

    # --- the moot-hall and the houses of the Bree-folk --------------------
    building(28, 6, 38, 13, door=(33, 13))       # the moot-hall (civic, large)
    houses = [
        (5, 6, 9, 10, (7, 10)),                  # north-west cottages
        (5, 14, 9, 18, (7, 18)),
        (24, 6, 27, 10, (25, 10)),
        (40, 7, 44, 12, (42, 12)),
        (30, 16, 35, 20, (32, 20)),
        (39, 15, 44, 20, (41, 20)),
        (14, 25, 19, 30, (16, 30)),              # south-side homes
        (6, 34, 11, 38, (8, 34)),
        (15, 33, 20, 37, (17, 33)),
        (27, 26, 32, 31, (29, 31)),
        (36, 25, 41, 30, (38, 30)),
        (30, 34, 36, 38, (33, 34)),
        (24, 34, 28, 38, (26, 34)),
        (39, 33, 43, 37, (41, 33)),
    ]
    for x0, y0, x1, y1, door in houses:
        building(x0, y0, x1, y1, door)

    # the herb-wife's cot, with a physic-garden beside it
    building(6, 27, 11, 31, door=(11, 29))
    for gx in range(12, 15):
        for gy in range(27, 32):
            if rng.random() < 0.6:
                gm.tiles[gx, gy] = T.grass_low
    gm.tiles[13, 28] = T.tree

    # --- the four gates: gaps in the hedge, flanked by stone posts --------
    def gate(gap, posts):
        for x, y in gap:
            gm.tiles[x, y] = T.road
        for x, y in posts:
            if gm.in_bounds(x, y):
                gm.tiles[x, y] = T.building_wall
    gate([(ex0, y) for y in (RY0, cy, RY1)], [(ex0, RY0 - 1), (ex0, RY1 + 1)])   # West-gate
    gate([(ex1, y) for y in (RY0, cy, RY1)], [(ex1, RY0 - 1), (ex1, RY1 + 1)])   # East-gate
    gate([(x, ey1) for x in (RX0, cx, RX1)], [(RX0 - 1, ey1), (RX1 + 1, ey1)])   # South-gate
    gate([(x, ey0) for x in (RX0, cx, RX1)], [(RX0 - 1, ey0), (RX1 + 1, ey0)])   # North-gate

    # roads run on out to the map edges (and east, up over Bree-hill)
    gm.tiles[0:ex0 + 1, RY0:RY1 + 1] = T.road
    gm.tiles[ex1:w, RY0:RY1 + 1] = T.road
    gm.tiles[RX0:RX1 + 1, 0:ey0 + 1] = T.road
    gm.tiles[RX0:RX1 + 1, ey1:h] = T.road

    # --- market props and hobbit-holes ------------------------------------
    gm.tiles[25, 19] = T.water                   # the town well
    gm.tiles[19, 25] = T.tree                    # the market oak
    for hy in (8, 13, 27, 32, 37):               # smials in the west face of the hill
        gm.tiles[47, hy] = T.door
        gm.tiles[48, hy] = T.floor

    # --- the folk of Bree -------------------------------------------------
    elder, healer, halbarad, innkeeper = story.make_town_npcs()
    innkeeper.spawn(gm, 15, 17)     # Butterbur, in the Pony's coach-yard
    elder.spawn(gm, 17, 17)         # Dírhael, lodging at the Pony
    halbarad.spawn(gm, 6, 20)       # Halbarad, keeping watch by the West-gate
    healer.spawn(gm, 12, 29)        # Mistress Rushlight, in her physic-garden

    gm.entry_xy = (cx, cy)          # fallback landing = the market square
    gm.start_xy = (cx, cy)          # a new game begins at the crossing
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
