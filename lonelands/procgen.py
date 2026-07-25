"""Map generation: the village of Talbrún, the wilderness of the Weather Hills,
and the descending barrow-ruin of Amon Gûl."""
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
# Town
# ---------------------------------------------------------------------------
def generate_town(engine) -> GameMap:
    w, h = MAP_WIDTH, MAP_HEIGHT
    gm = GameMap(engine, w, h, name="Talbrún, a village of the Dúnedain", outdoors=True)
    gm.tiles[:] = tile_types.grass

    for x in range(w):
        for y in range(h):
            if rng.random() < 0.10:
                gm.tiles[x, y] = tile_types.grass_low

    # Palisade
    tx0, ty0, tx1, ty1 = 5, 3, w - 6, h - 4
    gm.tiles[tx0:tx1 + 1, ty0] = tile_types.building_wall
    gm.tiles[tx0:tx1 + 1, ty1] = tile_types.building_wall
    gm.tiles[tx0, ty0:ty1 + 1] = tile_types.building_wall
    gm.tiles[tx1, ty0:ty1 + 1] = tile_types.building_wall
    gm.tiles[tx0 + 1:tx1, ty0 + 1:ty1] = tile_types.cobble

    def building(bx, by, bw, bh):
        gm.tiles[bx:bx + bw, by] = tile_types.building_wall
        gm.tiles[bx:bx + bw, by + bh - 1] = tile_types.building_wall
        gm.tiles[bx, by:by + bh] = tile_types.building_wall
        gm.tiles[bx + bw - 1, by:by + bh] = tile_types.building_wall
        gm.tiles[bx + 1:bx + bw - 1, by + 1:by + bh - 1] = tile_types.floor
        gm.tiles[bx + bw // 2, by + bh - 1] = tile_types.door

    building(9, 7, 9, 6)          # the hall
    building(w - 18, 7, 9, 6)     # herbwife
    building(9, h - 13, 9, 6)     # stores
    building(w - 18, h - 13, 9, 6)  # a home

    gate_x = w // 2
    gm.tiles[gate_x, ty1] = tile_types.town_exit
    gm.tiles[gate_x, ty1 - 1] = tile_types.cobble
    gm.town_exit_xy = (gate_x, ty1)

    elder, healer, halbarad, watchman = story.make_town_npcs()
    elder.spawn(gm, 13, 14)              # by the hall
    healer.spawn(gm, w - 14, 14)         # by the herbwife's
    halbarad.spawn(gm, 13, h - 8)        # by the stores
    watchman.spawn(gm, gate_x, ty1 - 2)

    gm.entry_xy = (gate_x, ty1 - 2)      # arriving from the Wild
    gm.start_xy = (gate_x, h // 2)       # a new game begins in the square
    return gm


# ---------------------------------------------------------------------------
# Overworld — the Weather Hills
# ---------------------------------------------------------------------------
def generate_overworld(engine) -> GameMap:
    w, h = MAP_WIDTH, MAP_HEIGHT
    gm = GameMap(engine, w, h, name="The Weather Hills, east of Talbrún", outdoors=True)
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

    town_gate = (3, ford_y)
    ruin_xy = (w - 6, ford_y)

    # The old road, west gate -> ford -> ruin (drawn first)
    for x in range(town_gate[0], river_x - 1):
        gm.tiles[x, ford_y] = tile_types.road
    for x in range(river_x + 3, ruin_xy[0] + 1):
        gm.tiles[x, ford_y] = tile_types.road

    # Landmarks placed last so the road does not overwrite them.
    gm.tiles[town_gate] = tile_types.town_exit
    gm.town_gate_xy = town_gate
    gm.tiles[ruin_xy] = tile_types.ruin_entrance
    gm.ruin_entrance_xy = ruin_xy

    # Wild beasts roam the open ground
    for _ in range(rng.randint(3, 5)):
        bx, by = rng.randint(6, w - 6), rng.randint(4, h - 4)
        if gm.tiles["walkable"][bx, by] and gm.get_blocking_entity_at(bx, by) is None:
            _weighted(content.WILD_BEASTS).spawn(gm, bx, by)

    gm.entry_xy = (town_gate[0] + 1, town_gate[1])   # arriving from town
    gm.from_ruin_xy = (ruin_xy[0] - 1, ruin_xy[1])   # arriving from the ruin
    return gm


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
