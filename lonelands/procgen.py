"""Map generation for the Regions of the overworld grid (`overworld.py`,
ADR 0003). Authored Surfaces have their own `generate_*`; every other walkable
cell is built by `generate_placeholder_surface` from its plan `Cell`. Bree is
the hub; the barrow-wight deeps lie west under the **Barrow-downs** (Tyrn
Gorthad) and the watch-vaults east under **Weathertop** (Amon Sûl).

Each `generate_*` returns the **Surface** of one Region. A Surface is edge-open:
the player leaves it by walking off any edge (see `world.GameWorld.cross_edge`),
so no map carries a "gate" tile any more — Enter is reserved for stairs and the
barrow entrance (the vertical axis)."""
from __future__ import annotations

import math
from typing import List, Tuple

from lonelands import affixes, content, overworld, story, tile_types
from lonelands.config import MAP_HEIGHT, MAP_WIDTH
from lonelands.dice import rng
from lonelands.entity import Item
from lonelands.game_map import GameMap, nearest_walkable

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


def building(gm: GameMap, x0: int, y0: int, x1: int, y1: int, door) -> None:
    """A rectangular stone building: four walls, a floored interior, and a door
    in the wall at `door`. Shared by the Bree houses and the wayside posts."""
    gm.tiles[x0:x1 + 1, y0] = tile_types.building_wall
    gm.tiles[x0:x1 + 1, y1] = tile_types.building_wall
    gm.tiles[x0, y0:y1 + 1] = tile_types.building_wall
    gm.tiles[x1, y0:y1 + 1] = tile_types.building_wall
    gm.tiles[x0 + 1:x1, y0 + 1:y1] = tile_types.floor
    gm.tiles[door] = tile_types.door


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

    # --- The Prancing Pony: an inn hall with a walled stable-yard ---------
    building(gm, 11, 9, 20, 20, door=(15, 20))   # outer walls; archway on the Road
    gm.tiles[12:20, 15:20] = T.cobble            # the coach-yard (open, cobbled)
    gm.tiles[15, 14] = T.door                    # hall door, yard -> common-room
    gm.tiles[15, 20] = T.door                    # the great archway onto the street

    # --- the moot-hall and the houses of the Bree-folk --------------------
    building(gm, 28, 6, 38, 13, door=(33, 13))   # the moot-hall (civic, large)
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
        building(gm, x0, y0, x1, y1, door)

    # the herb-wife's cot, with a physic-garden beside it
    building(gm, 6, 27, 11, 31, door=(11, 29))
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
    elder, healer, halbarad, innkeeper, fletcher = story.make_town_npcs()
    innkeeper.spawn(gm, 15, 17)     # Butterbur, in the Pony's coach-yard
    elder.spawn(gm, 17, 17)         # Dírhael, lodging at the Pony
    halbarad.spawn(gm, 6, 20)       # Halbarad, keeping watch by the West-gate
    healer.spawn(gm, 12, 29)        # Mistress Rushlight, in her physic-garden
    fletcher.spawn(gm, 22, 22)      # Cob, at his stall by the market square

    gm.entry_xy = (cx, cy)          # fallback landing = the market square
    gm.start_xy = (cx, cy)          # a new game begins at the crossing
    return gm


# ---------------------------------------------------------------------------
# The Weather Hills — the east Region, holding the barrow entrance
# ---------------------------------------------------------------------------
def generate_weathertop(engine) -> GameMap:
    """Weathertop (Amon Sûl): the ruined watchtower on its hill, with the old
    road climbing to a broken arch — Enter it to descend into the watch-vaults."""
    w, h = MAP_WIDTH, MAP_HEIGHT
    gm = GameMap(engine, w, h, name="Weathertop (Amon Sûl)", outdoors=True)
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

    # The Great East Road runs west-edge -> ford -> past the ruin to the east
    # edge, so it threads continuously through Weathertop across both seams and
    # the player can follow it on toward the Trollshaws (issue #14).
    for x in range(0, river_x - 1):
        gm.tiles[x, ford_y] = tile_types.road
    for x in range(river_x + 3, w):
        gm.tiles[x, ford_y] = tile_types.road

    # The watchtower entrance (Enter here to descend into the watch-vaults).
    gm.tiles[ruin_xy] = tile_types.ruin_entrance
    gm.ruin_entrance_xy = ruin_xy
    gm.barrow_entrance_xy = ruin_xy   # where the player surfaces from the deeps

    apply_band_beasts(gm, "Wild")     # Weathertop lies in the Wild-Lands band

    gm.entry_xy = (1, ford_y)   # fallback landing = just inside the west edge
    return gm


# ---------------------------------------------------------------------------
# Terrain-primitive toolkit
# ---------------------------------------------------------------------------
# Small, reusable painters the Region generators compose. Each mutates `gm` in
# place. Together with `apply_band_beasts` they generalize the old `_open_surface`
# so any cell of the overworld grid can be built from its plan `Cell` (ADR 0003).
def scatter(gm: GameMap, tile, chance: float, *, over=None) -> None:
    """Sprinkle `tile` across the map with per-cell probability `chance`,
    optionally only over tiles whose current kind is in `over`."""
    for x in range(gm.width):
        for y in range(gm.height):
            if over is not None and int(gm.tiles["kind"][x, y]) not in over:
                continue
            if rng.random() < chance:
                gm.tiles[x, y] = tile


def edge_belt(gm: GameMap, tile, side: str, depth: int, chance: float) -> None:
    """Paint a ragged belt of `tile` `depth` tiles deep along one edge
    (`'n'|'s'|'e'|'w'`) — forest fringes, and the diegetic Sea/Mountain border
    the plan asks bordering Regions to paint where a neighbour is missing."""
    w, h = gm.width, gm.height
    for d in range(depth):
        fade = chance * (1.0 - d / max(depth, 1))
        if side == "n":
            band = [(x, d) for x in range(w)]
        elif side == "s":
            band = [(x, h - 1 - d) for x in range(w)]
        elif side == "w":
            band = [(d, y) for y in range(h)]
        else:  # 'e'
            band = [(w - 1 - d, y) for y in range(h)]
        for x, y in band:
            if rng.random() < fade:
                gm.tiles[x, y] = tile


def patch(gm: GameMap, tile, cx: int, cy: int, radius: int, chance: float) -> None:
    """A soft round blob of `tile` centred on (cx, cy): each tile within
    `radius` is painted with probability `chance`, fading toward the rim — a
    copse, a fen, a rockfall, as opposed to `scatter`'s even sprinkle."""
    for x in range(max(0, cx - radius), min(gm.width, cx + radius + 1)):
        for y in range(max(0, cy - radius), min(gm.height, cy + radius + 1)):
            dist = max(abs(x - cx), abs(y - cy))
            if dist <= radius and rng.random() < chance * (1.0 - dist / (radius + 1)):
                gm.tiles[x, y] = tile


def patches(gm: GameMap, tile, count: int, radius: int, chance: float) -> None:
    """Scatter `count` `patch`es of `tile` at random centres."""
    for _ in range(count):
        cx = rng.randint(radius, gm.width - 1 - radius)
        cy = rng.randint(radius, gm.height - 1 - radius)
        patch(gm, tile, cx, cy, radius, chance)


def apply_band_beasts(gm: GameMap, band: str) -> None:
    """Seed wandering beasts from the Region's band (content.BAND_BEASTS),
    regardless of terrain — the plan's Free/Wild/Dark/Perilous beast model."""
    (lo, hi), table = content.BAND_BEASTS[band]
    for _ in range(rng.randint(lo, hi)):
        for _try in range(24):     # retry so dense terrain (a wood, a fen) still fills
            bx, by = rng.randint(2, gm.width - 3), rng.randint(2, gm.height - 3)
            if gm.tiles["walkable"][bx, by] and gm.get_blocking_entity_at(bx, by) is None:
                _weighted(table).spawn(gm, bx, by)
                break


# Per-band terrain feel for placeholder surfaces: (tree, low-grass) chances,
# keyed by the band constants so the names stay in step with `overworld`.
_BAND_TERRAIN = {
    overworld.FREE:     (0.05, 0.20),   # green, settled
    overworld.WILD:     (0.10, 0.16),   # mixed open country
    overworld.DARK:     (0.05, 0.10),   # sparse, harsh
    overworld.PERILOUS: (0.07, 0.10),   # broken, ill-kept
}


# ---------------------------------------------------------------------------
# Road threading — lay the meandering roads of the plan across cell seams.
# ---------------------------------------------------------------------------
# The plan's roads are per-edge metadata (`overworld.ROAD_EDGES`, ADR 0003). A
# road enters and leaves a cell at the **midpoint of the edge it crosses**, so
# the shared midpoint is the same tile on both sides of a seam and the road meets
# its neighbour there. Between edges the line bows through the cell centre with a
# half-sine offset, so it meanders like the journey-map rather than running dead
# straight. Where the line falls on water it lays a bridge/ford instead of
# drowning. Endpoints (edge midpoint, centre) carry zero offset, keeping seams
# tile-exact regardless of the meander.
ROAD_ROW = MAP_HEIGHT // 2
ROAD_COL = MAP_WIDTH // 2
_EDGE_MIDPOINT = {
    "w": (0, ROAD_ROW),
    "e": (MAP_WIDTH - 1, ROAD_ROW),
    "n": (ROAD_COL, 0),
    "s": (ROAD_COL, MAP_HEIGHT - 1),
}
_ROAD_MEANDER = 4      # peak perpendicular bow, in tiles


def _lay_road(gm: GameMap, x: int, y: int) -> None:
    if not gm.in_bounds(x, y):
        return
    if int(gm.tiles["kind"][x, y]) == tile_types.KIND_WATER:
        gm.tiles[x, y] = tile_types.bridge      # a ford/bridge over the water
    else:
        gm.tiles[x, y] = tile_types.road


def _road_route(x0, y0, x1, y1, sign):
    """A 4-connected tile path from (x0,y0) to (x1,y1), bowed perpendicular by a
    half-sine (peak `_ROAD_MEANDER`, direction `sign`) so the road meanders."""
    dx, dy = x1 - x0, y1 - y0
    steps = max(abs(dx), abs(dy)) or 1
    length = math.hypot(dx, dy) or 1.0
    perp = (-dy / length, dx / length)
    out: List[Tuple[int, int]] = []
    last = None
    for i in range(steps + 1):
        t = i / steps
        off = sign * _ROAD_MEANDER * math.sin(math.pi * t)
        x = round(x0 + dx * t + perp[0] * off)
        y = round(y0 + dy * t + perp[1] * off)
        if last is not None and x != last[0] and y != last[1]:
            out.append((last[0], y))    # a knee, so the run stays 4-connected
        out.append((x, y))
        last = (x, y)
    return out


def thread_road(gm: GameMap, coord: overworld.Coord) -> None:
    """Paint the meandering road of the cell at `coord` onto its Surface, from
    each crossed edge midpoint through the cell centre so it meets the
    neighbouring Region's road across every seam (`overworld.ROAD_EDGES`)."""
    edges = overworld.road_edges(coord)
    if not edges:
        return
    tiles = set()
    for i, edge in enumerate(sorted(edges)):
        mx, my = _EDGE_MIDPOINT[edge]
        sign = 1 if i % 2 == 0 else -1     # alternate the bow for an S-weave
        tiles.update(_road_route(mx, my, ROAD_COL, ROAD_ROW, sign))
    for x, y in tiles:                     # paint each once, off the original terrain,
        _lay_road(gm, x, y)                # so a fording tile is not re-laid as dry road


# ---------------------------------------------------------------------------
# Diegetic borders — paint the plan's in-world barrier on every closed edge.
# ---------------------------------------------------------------------------
# The overworld plan makes a missing neighbour read *in-world* rather than as an
# invisible wall (`overworld.border_edges`, ADR 0003 / issue #15): open water for
# the Sea, a mountain ridge for the Misty-Mountain wall, a dense wood for the soft
# cut-off land borders, and a visible pass where a Gateway Region fronts the wall.
# The belt each hard/soft frame paints, as (tile, depth, chance) — one table so
# the barrier's look lives in a single place (GATE is painted by _gateway_pass).
_BORDER_BELT = {
    overworld.SEA:      (tile_types.water, 3, 0.85),   # open water, hard
    overworld.MOUNTAIN: (tile_types.hill, 3, 0.85),    # a mountain ridge, hard
    overworld.WOOD:     (tile_types.tree, 2, 0.70),    # a dense wood, soft
}
_GATE_PASS = 3   # width of the road pass cut through a gateway's mountain ridge


def _gateway_pass(gm: GameMap, edge: str) -> None:
    """A mountain ridge with a road pass cut through its middle: a Gateway
    Region's wall-facing edge reads as a crossing you could take, not masonry.
    The ridge is the plain Mountain belt, so a gate looks like the wall it pierces."""
    tile, depth, chance = _BORDER_BELT[overworld.MOUNTAIN]
    edge_belt(gm, tile, edge, depth, chance)
    mx, my = _EDGE_MIDPOINT[edge]
    half = _GATE_PASS // 2
    for d in range(depth):
        if edge == "n":
            cells = [(mx + o, d) for o in range(-half, half + 1)]
        elif edge == "s":
            cells = [(mx + o, gm.height - 1 - d) for o in range(-half, half + 1)]
        elif edge == "w":
            cells = [(d, my + o) for o in range(-half, half + 1)]
        else:  # 'e'
            cells = [(gm.width - 1 - d, my + o) for o in range(-half, half + 1)]
        for cx, cy in cells:
            if gm.in_bounds(cx, cy):
                gm.tiles[cx, cy] = tile_types.road


def diegetic_borders(gm: GameMap, coord: overworld.Coord) -> None:
    """Paint the plan's diegetic barrier along every closed edge of the cell at
    `coord` (`overworld.border_edges`), so no edge of the playable map reads as an
    invisible wall (issue #15). The shared helper every surface generator calls;
    a cell with all four neighbours present is a no-op."""
    for edge, kind in overworld.border_edges(coord).items():
        if kind == overworld.GATE:
            _gateway_pass(gm, edge)                             # a crossing in the wall
        else:
            tile, depth, chance = _BORDER_BELT[kind]
            edge_belt(gm, tile, edge, depth, chance)


def snap_to_road(gm: GameMap, edge: str, near: Tuple[int, int]):
    """The road/bridge tile on `edge` ('n'|'s'|'e'|'w') nearest to `near`, or
    None if that edge carries no road — where a crossing player lands so they
    arrive on the road (issue #14)."""
    w, h = gm.width, gm.height
    if edge in ("e", "w"):
        col = w - 1 if edge == "e" else 0
        line = [(col, y) for y in range(h)]
    else:
        row = h - 1 if edge == "s" else 0
        line = [(x, row) for x in range(w)]
    roads = [(x, y) for (x, y) in line
             if int(gm.tiles["kind"][x, y]) == tile_types.KIND_ROAD]
    if not roads:
        return None
    nx, ny = near
    return min(roads, key=lambda p: abs(p[0] - nx) + abs(p[1] - ny))


def _open_surface(engine, cell) -> GameMap:
    """A blank grass Surface for the cell — the common canvas every open-country
    generator paints onto before `_finish_surface` seals it."""
    gm = GameMap(engine, MAP_WIDTH, MAP_HEIGHT, name=cell.region_name, outdoors=True)
    gm.tiles[:] = tile_types.grass
    return gm


def _finish_surface(gm: GameMap, cell) -> GameMap:
    """The shared tail of every open-country Surface: paint the diegetic border
    on each closed edge (issue #15), thread the plan's roads across the seams on
    top of the terrain (issue #14), seed band-appropriate wandering beasts
    (ADR 0003), and land the player on a walkable centre tile. Terrain is painted
    by the caller *before* this — the roads and borders read over it."""
    diegetic_borders(gm, cell.coord)
    thread_road(gm, cell.coord)
    apply_band_beasts(gm, cell.band)
    gm.entry_xy = nearest_walkable(gm, gm.width // 2, gm.height // 2)
    gm.start_xy = gm.entry_xy
    return gm


def generate_placeholder_surface(engine, cell) -> GameMap:
    """A walkable Surface built straight from a plan `Cell` — the generic filler
    that makes any un-authored grid cell enterable before its cluster refines it.

    Bands drive both the terrain feel and the wandering beasts. Where a
    neighbour is missing (Sea to the west, Mountain-wall to the east/edges),
    paint the barrier diegetically so the uncrossable edge reads in-world."""
    gm = _open_surface(engine, cell)

    tree_chance, low_chance = _BAND_TERRAIN[cell.band]
    scatter(gm, tile_types.grass_low, low_chance)
    scatter(gm, tile_types.tree, tree_chance)
    if cell.band == overworld.DARK:
        patches(gm, tile_types.hill, 3, 3, 0.7)     # bare rock breaking the ground
    elif cell.band == overworld.PERILOUS:
        patches(gm, tile_types.water, 3, 2, 0.7)    # fen and standing water

    return _finish_surface(gm, cell)


# ---------------------------------------------------------------------------
# Cluster 2 — Bree & environs (issue #17). Lore-appropriate terrain for the
# named anchors around the crossroads (terrain by *place*, not by band), mostly
# composed from the terrain toolkit above, with hand-placed set-pieces where a
# landmark needs one (Sarn Ford's river, ford, and watch-post). Bree and the
# Barrow-downs are authored elsewhere; these give identity to the wilderness and
# landmark cells that ring them, each sealed by `_finish_surface` (borders,
# roads, beasts).
# ---------------------------------------------------------------------------
def generate_chetwood(engine) -> GameMap:
    """Chetwood (0,-1): the wooded country north of Bree the Greenway climbs
    through — close-grown trees and copses, denser than open Wild-Lands. The
    woodwrights' hamlet of **Archet** sits in a cleared fold at the south eaves
    (story/chetwood.py); the old felling-axe of its main quest lies dropped deep
    in the north wood."""
    cell = overworld.cell((0, -1))
    gm = _open_surface(engine, cell)
    scatter(gm, tile_types.grass_low, 0.18)         # undergrowth
    scatter(gm, tile_types.tree, 0.24)              # the wood proper
    patches(gm, tile_types.tree, 6, 4, 0.6)         # thicker copses within it

    # --- Archet: a small hamlet in a cleared fold at the south eaves -------
    ax0, ay0, ax1, ay1 = 13, 30, 31, 41
    gm.tiles[ax0:ax1 + 1, ay0:ay1 + 1] = tile_types.grass   # clear the coppice
    for gx in range(ax0, ax1 + 1):
        for gy in range(ay0, ay1 + 1):
            if rng.random() < 0.15:
                gm.tiles[gx, gy] = tile_types.grass_low
    for b in [(15, 32, 20, 36, (17, 36)),
              (23, 31, 28, 35, (25, 35)),
              (18, 37, 23, 40, (20, 37))]:
        building(gm, *b)

    woodwright = story.chetwood.make_archet_woodwright()
    (coppicer,) = story.chetwood.make_bystanders()
    (path_post,) = story.chetwood.make_signposts()
    woodwright.spawn(gm, 22, 34)        # Baldo, before the timber hall
    coppicer.spawn(gm, 26, 37)          # a young coppicer by the wood-stacks
    path_post.spawn(gm, 22, 30)         # the path-post at the clearing's north edge

    # --- the woodwright's lost felling-axe, deep in the north wood ---------
    fx, fy = 46, 8
    gm.tiles[fx - 1:fx + 2, fy - 1:fy + 2] = tile_types.grass   # a reachable spot
    axe = content.felling_axe.spawn(gm, fx, fy)
    axe.pickup_event = "archet_axe"

    return _finish_surface(gm, cell)


def generate_midgewater(engine) -> GameMap:
    """Midgewater (1,-1): the biting fen where it is easy to lose the Road — a
    marsh of standing meres and reed-beds, a few stunted alders on the tussocks."""
    cell = overworld.cell((1, -1))
    gm = _open_surface(engine, cell)
    scatter(gm, tile_types.grass_low, 0.35)         # reed-beds and sedge
    patches(gm, tile_types.water, 12, 3, 0.75)      # meres and standing pools
    scatter(gm, tile_types.tree, 0.04)              # stunted alders on the tussocks
    return _finish_surface(gm, cell)


def generate_old_forest(engine) -> GameMap:
    """Old Forest (-2,1): the ancient wood whose trees are awake and
    ill-disposed — near-solid timber, with a single grassed heart-glade kept
    open so a traveller can win through."""
    cell = overworld.cell((-2, 1))
    gm = _open_surface(engine, cell)
    scatter(gm, tile_types.grass_low, 0.14)
    scatter(gm, tile_types.tree, 0.42)              # a close-grown ancient wood
    patches(gm, tile_types.tree, 8, 5, 0.7)         # brakes and thickets
    patch(gm, tile_types.grass, gm.width // 2, gm.height // 2, 4, 1.0)  # heart-glade
    return _finish_surface(gm, cell)


def generate_sarn_ford(engine) -> GameMap:
    """Sarn Ford (-1,1): the Brandywine crossing kept by the Rangers — the river
    runs the map north-south, forded at its heart, with a small stone watch-post
    on the east bank above the ford."""
    cell = overworld.cell((-1, 1))
    gm = _open_surface(engine, cell)
    scatter(gm, tile_types.grass_low, 0.16)
    scatter(gm, tile_types.tree, 0.05)

    river_x, ford_y = gm.width // 2, gm.height // 2
    for y in range(gm.height):                      # the Brandywine, three wide
        for dx in range(-1, 2):
            gm.tiles[river_x + dx, y] = tile_types.water
    for dx in range(-2, 3):                         # the ford (stony shallows)
        gm.tiles[river_x + dx, ford_y] = tile_types.bridge
    for x in list(range(river_x - 7, river_x - 1)) + list(range(river_x + 3, river_x + 9)):
        gm.tiles[x, ford_y] = tile_types.road       # the track down to each bank
    for wy in (ford_y - 1, ford_y, ford_y + 1):     # willows crowding the banks
        gm.tiles[river_x - 2, wy] = tile_types.tree
        gm.tiles[river_x + 2, wy] = tile_types.tree

    # the Rangers' watch-post: a small stone hut above the east landing
    px0, py0, px1, py1 = river_x + 4, ford_y - 5, river_x + 8, ford_y - 2
    building(gm, px0, py0, px1, py1, door=((px0 + px1) // 2, py1))

    return _finish_surface(gm, cell)


def generate_south_downs(engine) -> GameMap:
    """South Downs (0,1): the low rolling downs south of the Great Road the
    Greenway crosses — close-cropped turf heaped into grassy hills, a lone thorn
    here and there."""
    cell = overworld.cell((0, 1))
    gm = _open_surface(engine, cell)
    scatter(gm, tile_types.grass_low, 0.22)         # close-cropped down-turf
    patches(gm, tile_types.hill, 8, 4, 0.55)        # the rolling downs
    scatter(gm, tile_types.tree, 0.03)              # a lone thorn on the skyline
    return _finish_surface(gm, cell)


def generate_breeland(engine) -> GameMap:
    """The Bree-land east of the Hill (1,0): the hamlets of **Combe** (a
    woodsman-village in a northern fold) and **Staddle** (hobbit-holes on the
    sunny south slope), and the lonely **Forsaken Inn** out east along the Great
    East Road, where a Blue-Mountain Dwarf keeps a trading-stall (story/breeland.py).

    Bree-hill's shoulder rises along the west edge, continuous with Bree's own
    eastern hill; the plan's East Road is threaded first, so hamlet walls can't
    be carved by its meander, and lanes connect each hamlet to it. Settled
    country: *no wandering beasts* stalk the villages — the wargs and spiders the
    folk speak of roam the wild cells around (the Chetwood north, the moors east)."""
    cell = overworld.cell((1, 0))
    gm = _open_surface(engine, cell)
    gm.name = "The Bree-land, east of the Hill"   # a name for the once-blank cell
    T = tile_types

    # --- ground: pasture, with Bree-hill's shoulder heaped along the west --
    scatter(gm, T.grass_low, 0.10)
    scatter(gm, T.tree, 0.05)
    for x in range(0, 9):
        for y in range(gm.height):
            if rng.random() < 0.30 - 0.03 * x:      # the hill fades eastward
                gm.tiles[x, y] = T.hill
    patches(gm, T.tree, 4, 3, 0.5)                  # copses toward the Chetwood

    # --- the Great East Road first, then borders (so walls survive) --------
    thread_road(gm, cell.coord)
    diegetic_borders(gm, cell.coord)

    # --- Combe: a woodsman-hamlet in a northern fold ----------------------
    for b in [(17, 7, 22, 11, (19, 11)),
              (25, 6, 30, 10, (27, 10)),
              (20, 13, 25, 17, (22, 13))]:
        building(gm, *b)
    for gx in range(18, 31):                        # a beaten green between them
        gm.tiles[gx, 12] = T.grass_low
    for y in range(12, ROAD_ROW):                   # a lane down to the Road
        gm.tiles[27, y] = T.road

    # --- Staddle: hobbit-holes on the sunny south slope -------------------
    for b in [(16, 31, 20, 35, (18, 31)),
              (26, 32, 31, 36, (28, 32))]:
        building(gm, *b)
    for sx in (21, 23, 25):                         # smial-doors in a low rise
        gm.tiles[sx, 34] = T.door
        gm.tiles[sx, 35] = T.floor
    for x in range(30, 36):                         # rows of Southlinch pipe-weed
        for y in range(33, 37):
            if rng.random() < 0.5:
                gm.tiles[x, y] = T.grass_low
    for y in range(ROAD_ROW + 1, 32):               # a lane up to the Road
        gm.tiles[23, y] = T.road

    # --- The Forsaken Inn: a lone hall out east on the Road ---------------
    building(gm, 47, 24, 55, 30, door=(51, 24))     # door faces north onto the Road
    for y in range(ROAD_ROW, 24):                   # a short spur from the Road
        gm.tiles[51, y] = T.road

    # --- the folk of the Bree-land ----------------------------------------
    woodsman = story.breeland.make_combe_woodsman()
    provisioner = story.breeland.make_staddle_provisioner()
    innkeeper = story.breeland.make_forsaken_innkeeper()
    dwarf = story.breeland.make_dwarf_trader()
    hobbit, farmer, pedlar = story.breeland.make_bystanders()
    crossroads_post, milestone = story.breeland.make_signposts()

    woodsman.spawn(gm, 22, 12)          # Todi Heathertoes, on the Combe green
    farmer.spawn(gm, 25, 12)            # Mattock Mugwort, by the fence-line
    provisioner.spawn(gm, 28, 34)       # Rollo Tunnelly, in his larder-door
    hobbit.spawn(gm, 32, 34)            # Nib Sandheaver, among the pipe-weed
    innkeeper.spawn(gm, 50, 26)         # Mat Ferny, within the inn
    dwarf.spawn(gm, 53, 28)             # Thulin, at his corner stall
    pedlar.spawn(gm, 48, 28)            # the lean pedlar, in a dark corner
    crossroads_post.spawn(gm, 29, ROAD_ROW - 2)   # the fingerpost by the crossing
    milestone.spawn(gm, 44, ROAD_ROW + 1)         # the milestone, east on the Road

    gm.entry_xy = nearest_walkable(gm, 3, ROAD_ROW)   # arriving from Bree in the west
    gm.start_xy = gm.entry_xy
    return gm


# ---------------------------------------------------------------------------
# Tyrn Gorthad — the Barrow-downs (the main quest's barrow, re-homed here from
# the Weather Hills to match the geography of ADR 0003).
# ---------------------------------------------------------------------------
def generate_barrow_downs(engine) -> GameMap:
    cell = overworld.cell((-1, 0))
    gm = generate_placeholder_surface(engine, cell)
    gm.name = "The Barrow-downs (Tyrn Gorthad)"

    # A broken barrow-arch stands among the mounds: Enter here to descend into
    # the deep barrow where the star-brooch and the wights lie.
    bx, by = MAP_WIDTH // 2 + 6, MAP_HEIGHT // 2
    bx, by = nearest_walkable(gm, bx, by)
    gm.tiles[bx, by] = tile_types.ruin_entrance
    gm.ruin_entrance_xy = (bx, by)
    gm.barrow_entrance_xy = (bx, by)   # where the player surfaces from the deeps
    return gm


# ---------------------------------------------------------------------------
# Room-and-corridor deeps — the shared dungeon under a barrow or watchtower.
# ---------------------------------------------------------------------------
def generate_ruin(
    engine, depth: int, *,
    name: str = "The Barrows of Tyrn Gorthad",
    max_depth: int = MAX_RUIN_DEPTH,
    treasure: bool = True,
) -> GameMap:
    """One Level of a deeps. The deepest Level (`depth == max_depth`) either
    holds the quest `treasure` (the star-brooch) or, for a treasure-less ruin
    such as the Amon Sûl watch-vaults, simply ends."""
    w, h = MAP_WIDTH, MAP_HEIGHT
    gm = GameMap(engine, w, h, name=f"{name} — depth {depth}")
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

    # Down stair to the next Level, or — at the bottom — the quest treasure.
    last = rooms[-1].center
    if depth < max_depth:
        gm.tiles[last] = tile_types.down_stairs
        gm.down_xy = last
    elif treasure:
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
            dropped = _weighted(i_table).spawn(gm, *spot)
            # Ordinary gear rolls a rarity and its affixes here (ADR 0005, #40);
            # consumables and hand-authored Uniques are passed over untouched.
            affixes.apply_affixes(dropped, depth=depth)
