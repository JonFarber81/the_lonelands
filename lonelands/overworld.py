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

from typing import Dict, NamedTuple, Set, Tuple

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


def _default_cell(x: int, y: int):
    """Role/band/note for an un-authored cell, or None if it is Impassable
    (the Sea / Mountain-wall frame). Mirrors build_overworld.default_cell."""
    if x <= -7:                      return None
    if x >= 7 and y != 0:            return None
    if (x, y) == (6, 4):             return None
    if x <= -6 and y >= 2:           return None
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


def is_walkable(coord: Coord) -> bool:
    return coord in GRID
