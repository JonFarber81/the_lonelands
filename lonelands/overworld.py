"""The overworld **plan as data**: the 15×9 Region grid traced from the TOR
Eriador Journey Map (see `notes/overworld-map.md` and ADR 0003).

This is the single source of truth the `GameWorld` registry (`world.py`) is
built from. It is *pure data* — no engine, no tiles, no rendering — so it can be
imported anywhere and reasoned about in isolation. The artifact-rendering script
`notes/build_overworld.py` produces the same grid; this module is its runtime
twin, kept deliberately free of PIL/matplotlib/numpy.

Vocabulary (CONTEXT.md → *World & navigation*):
  * **coord** — `(x, y)`, x west→east in −7..+7, y north→south in −4..+4.
  * **role**  — what is authored: Town · Landmark · Wilderness · Gateway.
  * **band**  — danger/terrain, read off the map's legend colours:
                Free · Wild · Dark · Perilous. Drives the wandering-beast model.
  * **deeps** — number of dungeon Levels beneath the Surface (0 = none).

**Impassable = absence.** Sea and Mountain-wall cells are simply *not* in `GRID`;
`region(coord)` returns `None` and that edge is uncrossable (ADR 0002). The
bordering Region paints the barrier diegetically.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, List, NamedTuple, Set, Tuple

Coord = Tuple[int, int]

# --- bands -----------------------------------------------------------------
FREE = "Free"
WILD = "Wild"
DARK = "Dark"
PERILOUS = "Perilous"
BANDS = (FREE, WILD, DARK, PERILOUS)

# --- roles -----------------------------------------------------------------
TOWN = "Town"
LANDMARK = "Landmark"
WILDERNESS = "Wilderness"
GATEWAY = "Gateway"


class Cell(NamedTuple):
    """One walkable Region in the plan. Impassable coords have no Cell."""
    coord: Coord
    name: str          # "" for un-named wilderness filler
    role: str
    band: str
    deeps: int         # dungeon Levels below the Surface (0 = none)
    road: bool         # whether a road/track runs through this cell
    note: str

    @property
    def region_name(self) -> str:
        """The display name for the Region built from this cell — its authored
        name, or a band label for un-named wilderness filler."""
        return self.name or f"The {self.band} Lands"


# ---------------------------------------------------------------------------
# The window box in reference-jpeg pixels (mirrors notes/build_overworld.py so
# the runtime grid is identical to the rendered plan).
# ---------------------------------------------------------------------------
_X0, _X1, _Y0, _Y1 = 700, 1920, 330, 1070
_COLS, _ROWS = 15, 9              # x in -7..+7, y in -4..+4
_CW = (_X1 - _X0) / _COLS
_CH = (_Y1 - _Y0) / _ROWS
_CX0, _CY0 = 7, 4                 # grid index of coord (0,0)


def _cell_of(px: float, py: float) -> Coord:
    c = min(_COLS - 1, max(0, round((px - _X0) / _CW - 0.5)))
    r = min(_ROWS - 1, max(0, round((py - _Y0) / _CH - 0.5)))
    return (c - _CX0, r - _CY0)


# --- the authored anchors (name, px, py, role, band, deeps, note) ----------
# Ordered exactly as notes/build_overworld.py so the deterministic collision
# nudge resolves to the same cells.
_ANCHORS = [
    ("Bree", 1300, 700, TOWN, FREE, 0,
     "The hub, at the meeting of the roads; a Ranger is met here."),
    ("Michel Delving", 1010, 710, TOWN, FREE, 0,
     "Chief town of the Shire; the Mathom-house."),
    ("Hobbiton", 1100, 635, TOWN, FREE, 0,
     "Hobbit hamlet; the Hill and Bag End."),
    ("Brandywine Bridge", 1180, 640, LANDMARK, FREE, 0,
     "Stone bridge; the Shire's eastern gate onto the Road."),
    ("Grey Havens", 745, 660, TOWN, FREE, 0,
     "Mithlond; elven port. Western gateway (ships west, later)."),
    ("White Towers", 855, 690, LANDMARK, FREE, 0,
     "Elostirion; the palantír that looks only to the Sea."),
    ("Tower Hills", 870, 765, WILDERNESS, FREE, 0,
     "Emyn Beraid; green marches west of the Far Downs."),
    ("Far Downs", 945, 740, WILDERNESS, FREE, 0,
     "The Shire's western downs."),
    ("Annúminas", 1045, 545, LANDMARK, WILD, 3,
     "Ruined royal city on Lake Nenuial; deeps into the drowned halls."),
    ("Fornost", 1245, 515, LANDMARK, WILD, 2,
     "Norbury of the Kings; ruined Arnor capital, wight-haunted deeps."),
    ("North Downs", 1365, 390, LANDMARK, WILD, 0,
     "Rolling high downs; the road to the ruined north."),
    ("Chetwood", 1320, 640, WILDERNESS, WILD, 0,
     "Wooded country north of Bree."),
    ("Midgewater", 1405, 635, LANDMARK, PERILOUS, 0,
     "Midgewater Marshes; biting fen, easy to lose the Road."),
    ("Weather Hills", 1445, 570, WILDERNESS, WILD, 0,
     "The ridge-line running north from Weathertop."),
    ("Weathertop", 1500, 665, LANDMARK, WILD, 3,
     "Amon Sûl; ruined watchtower, deeps to the watch-chamber."),
    ("Barrow-downs", 1225, 730, LANDMARK, PERILOUS, 4,
     "Tyrn Gorthad; the barrow-wights and their deeps."),
    ("Old Forest", 1165, 745, LANDMARK, PERILOUS, 0,
     "Ancient wood; the trees are awake and ill-disposed."),
    ("Sarn Ford", 1230, 820, LANDMARK, WILD, 0,
     "The Brandywine ford; a Ranger watch-post on the south road."),
    ("South Downs", 1340, 785, WILDERNESS, WILD, 0,
     "Low downs south of the Great Road."),
    ("Cardolan", 1400, 870, WILDERNESS, WILD, 0,
     "Emptied old realm; barrows and broken keeps."),
    ("Tharbad", 1360, 1020, LANDMARK, WILD, 2,
     "Ruined river-city on the Greyflood; southern gateway. Silted deeps."),
    ("Last Bridge", 1625, 630, LANDMARK, WILD, 0,
     "The Mitheithel bridge on the East Road; the Road's last sure crossing."),
    ("Trollshaws", 1710, 620, LANDMARK, PERILOUS, 1,
     "Troll-country east of the Hoarwell; stone-trolls and their holes."),
    ("Fords of Bruinen", 1850, 645, GATEWAY, WILD, 0,
     "The Bruinen crossing; the guarded threshold of Rivendell."),
    ("Rivendell", 1805, 690, GATEWAY, FREE, 0,
     "Imladris; the Last Homely House. Eastern gateway (beyond, later)."),
    ("Ettenmoors", 1690, 410, LANDMARK, PERILOUS, 0,
     "Troll-fells; north-east gateway toward Angmar."),
    ("Mt Gram", 1650, 350, LANDMARK, DARK, 2,
     "Orc-hold of the northern hills; deeps into the goblin-warren."),
    ("Redhorn Pass", 1775, 885, GATEWAY, DARK, 0,
     "Caradhras pass over the Misty Mountains (beyond, later)."),
    ("Moria West-gate", 1730, 960, GATEWAY, PERILOUS, 5,
     "Hollin gate of Khazad-dûm; the Watcher and the long dark."),
    ("Ost-in-Edhil", 1620, 960, LANDMARK, WILD, 2,
     "Ruined Eregion city of the Elven-smiths; cellars and forges."),
]


# ---------------------------------------------------------------------------
# Roads — ordered cell-paths that follow the journey-map line (ADR 0003). The
# tiles are painted in a later pass; here they are per-cell registry metadata
# (Cell.road), the road-flag axis of the plan's cell taxonomy.
# ---------------------------------------------------------------------------
EAST_ROAD = [(0, 0), (1, 0), (2, 0), (3, 0), (3, -1), (4, -1),
             (5, -1), (6, -1), (7, -1), (7, 0), (6, 0)]     # Bree -> Rivendell
GREENWAY = [(0, -2), (0, -1), (0, 0), (0, 1), (0, 2),
            (1, 3), (1, 4)]                                 # Fornost -> Tharbad
SHIRE_ROAD = [(-4, 0), (-3, -1), (-2, -1), (-1, 0), (0, 0)]  # Michel Delving -> Bree
ROAD_CELLS: Set[Coord] = set(EAST_ROAD) | set(GREENWAY) | set(SHIRE_ROAD)


# --- the Impassable frame --------------------------------------------------
# What a cell/edge that is *not* a Region borders on: open water to the west and
# SW (the Great Sea / Gulf of Lune), the Misty-Mountain wall to the east, or —
# for a coord off the north/south of the window — cut-off land (soft). This is
# the single geometry both the grid's absent cells (`_default_cell`) and the
# diegetic border a neighbour paints (`border_edges`) read from (ADR 0003).
SEA = "sea"            # hard: open water — the Great Sea / Gulf of Lune (west/SW)
MOUNTAIN = "mountain"  # hard: the Misty Mountains wall (east)
WOOD = "wood"          # soft: dense wood — a cut-off land border (north/south)


def _impassable_frame(x: int, y: int):
    """The frame that makes `(x, y)` Impassable — `SEA` or `MOUNTAIN` — or None
    if it is walkable land within the window. `(7, 0)` is the wall's one gap (the
    East Road's run to the Fords), so the east wall is *every* `x >= 7` cell but
    that one; a neighbour off the far east (`x >= 8`) is Mountain all the same."""
    if x <= -7 or (x <= -6 and y >= 2):     # the west wall, and the SW Gulf of Lune
        return SEA
    if (x, y) == (6, 4):                    # the Misty-Mountain wall's southern foot
        return MOUNTAIN
    if x >= 7 and (x, y) != (7, 0):         # the east wall, save its one gap at (7,0)
        return MOUNTAIN
    return None


def frame_at(x: int, y: int):
    """The Impassable frame beyond `(x, y)` — `SEA` or `MOUNTAIN` — or None if it
    is walkable land within the window. The public twin of the internal geometry
    (cf. `road_edges`), for callers such as the Overworld Map that paint the
    Sea/Mountain frame around the grid."""
    return _impassable_frame(x, y)


def _default_cell(x: int, y: int):
    """Role/band/note for an un-authored cell, or None if it is Impassable
    (the Sea / Mountain-wall frame). Mirrors build_overworld.default_cell."""
    if _impassable_frame(x, y) is not None:
        return None
    if -6 <= x <= 0 and 0 <= y <= 1: band = FREE      # Shire / Arthedain green
    elif y <= -3 and x >= 4:         band = DARK       # Angmar / Rhudaur NE
    elif x >= 5 and y <= 0:          band = DARK       # Rhudaur east
    else:                            band = WILD
    note = ("Open country; encounters drawn from the %s table."
            % {FREE: "Free-Lands", WILD: "Wild-Lands", DARK: "Dark-Lands",
               PERILOUS: "Perilous"}[band])
    return (WILDERNESS, band, note)


def _build_grid() -> Dict[Coord, Cell]:
    # Resolve anchors to cells, nudging off collisions (deterministic order).
    placed: Dict[Coord, str] = {}
    cells: Dict[Coord, Cell] = {}
    for name, px, py, role, band, deeps, note in _ANCHORS:
        x, y = _cell_of(px, py)
        while (x, y) in placed:            # bump west, then north, to free a cell
            if (x - 1, y) not in placed and x - 1 >= -7:
                x -= 1
            elif (x, y - 1) not in placed and y - 1 >= -4:
                y -= 1
            else:
                x -= 1
        placed[(x, y)] = name
        cells[(x, y)] = Cell((x, y), name, role, band, deeps,
                             (x, y) in ROAD_CELLS, note)

    grid: Dict[Coord, Cell] = {}
    for r in range(_ROWS):
        for c in range(_COLS):
            x, y = c - _CX0, r - _CY0
            if (x, y) in cells:
                grid[(x, y)] = cells[(x, y)]
                continue
            default = _default_cell(x, y)
            if default is None:
                continue                  # Impassable: absent from the grid
            role, band, note = default
            grid[(x, y)] = Cell((x, y), "", role, band, 0,
                                (x, y) in ROAD_CELLS, note)
    return grid


GRID: Dict[Coord, Cell] = _build_grid()


def cell(coord: Coord):
    """The Cell at `coord`, or None if it is off-grid / Impassable."""
    return GRID.get(coord)


# ---------------------------------------------------------------------------
# Road edges — the per-border road model (ADR 0003: "roads are edge metadata").
# ---------------------------------------------------------------------------
# The ordered cell-paths above are *decoration-level* — they may step diagonally
# to trace the journey-map line. Movement is 4-neighbour (ADR 0002), so a road
# only truly *threads* across a shared N/S/E/W edge. `ROAD_EDGES` resolves each
# path into that reality: for every road cell, which of its four edges a road
# crosses. Diagonal hops staircase into an orthogonal knee cell so the line stays
# unbroken. The tile-painting pass (`procgen.thread_road`) and the arrival-snap
# (`world.cross_edge`) both read this — it is the single source of road truth.
# The step (dx, dy) you take to cross each edge (y grows south). One table, so
# edge<->delta truth lives in a single place the painter, snap, and tests share.
EDGE_DELTA = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}
EDGES = tuple(EDGE_DELTA)
_OPP = {"n": "s", "s": "n", "e": "w", "w": "e"}


def _edge_between(a: Coord, b: Coord):
    """The edge of `a` that borders orthogonally-adjacent `b` (y grows south),
    or None if they are not 4-neighbours."""
    delta = (b[0] - a[0], b[1] - a[1])
    for edge, step in EDGE_DELTA.items():
        if step == delta:
            return edge
    return None


def _orthogonalize(path: List[Coord]) -> List[Coord]:
    """A 4-neighbour-connected version of `path`: each diagonal step is split
    into a horizontal-then-vertical knee (falling back to vertical-first if the
    horizontal knee is off the grid), so every hop crosses one shared edge."""
    out = [path[0]]
    for a, b in zip(path, path[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx and dy:                       # diagonal: insert the knee cell
            knee = (a[0] + dx, a[1])
            if knee not in GRID:
                knee = (a[0], a[1] + dy)
            out.append(knee)
        out.append(b)
    return out


def _build_road_edges() -> Dict[Coord, FrozenSet[str]]:
    acc: Dict[Coord, Set[str]] = {}
    for path in (EAST_ROAD, GREENWAY, SHIRE_ROAD):
        ortho = _orthogonalize(path)
        for a, b in zip(ortho, ortho[1:]):
            edge = _edge_between(a, b)
            if edge is None:                # shouldn't happen post-orthogonalize
                continue
            acc.setdefault(a, set()).add(edge)
            acc.setdefault(b, set()).add(_OPP[edge])
    return {coord: frozenset(edges) for coord, edges in acc.items()}


ROAD_EDGES: Dict[Coord, FrozenSet[str]] = _build_road_edges()


def road_edges(coord: Coord) -> FrozenSet[str]:
    """The set of edges (subset of `EDGES`) a road crosses at `coord` — empty if
    the cell carries no road."""
    return ROAD_EDGES.get(coord, frozenset())


# ---------------------------------------------------------------------------
# Diegetic borders — the per-edge barrier model (Infra D, issue #15). Where a
# cell has no neighbour Region, the block reads *in-world*: the frame beyond the
# edge (`_impassable_frame`) decides what the bordering cell paints (ADR 0003's
# diegetic-border rule) — **hard walls** of Mountain (east) or Sea (west/SW),
# **soft** dense wood for the cut-off land borders (north/south), and a **gate**
# where a Gateway Region fronts the wall: a visible crossing, not masonry.
GATE = "gate"          # a crossing in the wall — a Gateway Region's threshold


def _frame(coord: Coord) -> str:
    """The frame an off-grid `coord` borders on — `SEA`, `MOUNTAIN`, or (for the
    cut-off land north/south) the soft `WOOD`. Only meaningful for coords absent
    from `GRID`; reads the same geometry as the grid's own Impassable rule."""
    return _impassable_frame(*coord) or WOOD


def border_edges(coord: Coord) -> Dict[str, str]:
    """For the cell at `coord`, the barrier each **closed** edge should paint,
    keyed by edge (subset of `EDGES`). An edge with no neighbour Region maps to
    `SEA` / `MOUNTAIN` / `WOOD` by the frame beyond it; a Gateway Region's
    *eastward* wall edge — the way through the Misty Mountains (Redhorn Pass, the
    Fords of Bruinen) — reads instead as a `GATE`, a crossing rather than a wall,
    so its threshold stays visibly enterable. Its other wall edges stay walled:
    the range simply runs on. A cell with all four neighbours present returns {}."""
    here = GRID.get(coord)
    if here is None:
        return {}
    out: Dict[str, str] = {}
    for edge, (dx, dy) in EDGE_DELTA.items():
        nb = (coord[0] + dx, coord[1] + dy)
        if nb in GRID:
            continue                        # a real neighbour — no barrier here
        kind = _frame(nb)
        if here.role == GATEWAY and kind == MOUNTAIN and edge == "e":
            kind = GATE                     # the pass/ford east through the wall
        out[edge] = kind
    return out
