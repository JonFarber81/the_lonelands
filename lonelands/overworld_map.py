"""The **Overworld Map** as a pure character buffer (issue #63; CONTEXT.md →
*World & navigation*).

This module turns the plan-as-data (`overworld.GRID`, `ROAD_EDGES`, the
`_impassable_frame`) into an in-memory grid of glyphs + colours — the whole 15×9
Region atlas at once, full-reveal, no fog. It is deliberately free of tcod: the
handler (`input_handlers.OverworldMapHandler`) blits the buffer to a console and
drives the cursor, but every placement decision lives here so it can be reasoned
about — and unit-tested — in isolation.

Layout: each Region is a blocky ``CELL_W``×``CELL_H`` cell; the Great Roads draw
as connected ASCII line-glyphs (`- | +`) along the shared seams through the edge
midpoints, so a road reads as one unbroken line across the map. Colour is by
**band** (danger), the centre glyph is by **role**; deeps carry a ``v`` mark and
the player's Region an ``@``. Town/Landmark names overrun the blank wilderness
around them, Towns winning any contest for a strip and any name that cannot be
laid without clobbering a glyph simply dropped (still read off the cursor)."""
from __future__ import annotations

from typing import Dict, FrozenSet, List, NamedTuple, Optional, Set, Tuple

from lonelands import color, overworld

Coord = Tuple[int, int]
Rgb = Tuple[int, int, int]

# --- geometry ---------------------------------------------------------------
# The playable window is x in -7..+7 (15 cols) and y in -4..+4 (9 rows). Each
# Region is a 4×3 block: 15×4 = 60 cols, 9×3 = 27 rows — the terrain grid fits
# inside the 61×36 console with the rows beneath free for the legend and the
# cursor footer. (Region *names* are no longer stamped into these cells; the
# handler draws them natively in a proportional font, so the block only has to
# hold the band tint, roads, and the role/deeps/@ markers — see ``render_map``.)
X_MIN, X_MAX = -7, 7
Y_MIN, Y_MAX = -4, 4
COLS = X_MAX - X_MIN + 1          # 15
ROWS = Y_MAX - Y_MIN + 1         # 9
CELL_W, CELL_H = 4, 3
GRID_W = COLS * CELL_W           # 60
GRID_H = ROWS * CELL_H           # 27

# --- glyphs -----------------------------------------------------------------
ROAD_H, ROAD_V, ROAD_CROSS = "-", "|", "+"   # ASCII road segments
DEEPS_GLYPH = "v"
PLAYER_GLYPH = "@"
ROLE_GLYPH = {
    overworld.TOWN: "#",         # a cluster of dwellings
    overworld.LANDMARK: "*",     # a ruin, tower, or marked site
    overworld.GATEWAY: "‡",      # a threshold onward — pass, ford, or gate
    overworld.WILDERNESS: "·",   # open country
}
SEA_GLYPH, MOUNTAIN_GLYPH = "≈", "^"

# --- palette (band tint = bg, glyph = fg) -----------------------------------
# Muted so the printed names and the @ still read on top.
BAND_BG: Dict[str, Rgb] = {
    overworld.FREE: (0x1C, 0x28, 0x1A),
    overworld.WILD: (0x2A, 0x27, 0x1A),
    overworld.DARK: (0x2A, 0x1A, 0x1E),
    overworld.PERILOUS: (0x30, 0x20, 0x14),
}
BAND_FG: Dict[str, Rgb] = {
    overworld.FREE: (0x7C, 0xA0, 0x66),
    overworld.WILD: (0xA6, 0x96, 0x66),
    overworld.DARK: (0xB6, 0x74, 0x70),
    overworld.PERILOUS: (0xCE, 0x84, 0x48),
}
SEA_BG, SEA_FG = (0x12, 0x20, 0x2E), (0x3C, 0x62, 0x88)
MOUNTAIN_BG, MOUNTAIN_FG = (0x24, 0x22, 0x20), (0x86, 0x7E, 0x72)
ROAD_FG = color.road_light
DEEPS_FG = (0x9A, 0x88, 0xB8)
PLAYER_FG = color.player_c
TOWN_NAME_FG = color.menu_title
LANDMARK_NAME_FG = color.light_gray
CURSOR_BG = color.bar_accent


# ---------------------------------------------------------------------------
# Coordinate ↔ buffer geometry
# ---------------------------------------------------------------------------
def in_window(coord: Coord) -> bool:
    """Whether `coord` lies inside the drawn 15×9 window (grid or frame)."""
    x, y = coord
    return X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX


def cell_origin(coord: Coord) -> Coord:
    """Top-left (col, row) of the block that draws Region `coord`."""
    x, y = coord
    return ((x - X_MIN) * CELL_W, (y - Y_MIN) * CELL_H)


def cell_center(coord: Coord) -> Coord:
    """The (col, row) at the middle of `coord`'s block — where its role glyph,
    the ``@``, or a road crossing sits."""
    ox, oy = cell_origin(coord)
    return (ox + CELL_W // 2, oy + CELL_H // 2)


# ---------------------------------------------------------------------------
# The two pure seams the tests pin down
# ---------------------------------------------------------------------------
def seam_glyph(edges: FrozenSet[str]) -> str:
    """The line-glyph for a road threading a cell whose road crosses `edges`
    (a subset of `overworld.EDGES`): horizontal for an E/W run, vertical for
    N/S, a crossing where both axes meet, and "" for a cell with no road."""
    horiz = bool(edges & {"e", "w"})
    vert = bool(edges & {"n", "s"})
    if horiz and vert:
        return ROAD_CROSS
    if vert:
        return ROAD_V
    if horiz:
        return ROAD_H
    return ""


class Label(NamedTuple):
    """A Region name to lay on the map, anchored at its Region's centre cell."""
    col: int
    row: int
    text: str
    role: str


class Placed(NamedTuple):
    """A laid-down name: where its first character starts, and the role it names
    (which drives its colour)."""
    col: int
    row: int
    text: str
    role: str

    @property
    def fg(self) -> Rgb:
        """The colour this name draws in — Towns in gold, everything else pale."""
        return TOWN_NAME_FG if self.role == overworld.TOWN else LANDMARK_NAME_FG


def _label_candidates(col: int, row: int, text: str):
    """Yield candidate (start_col, start_row) placements for a name anchored at
    Region-centre (col, row), best first: centred on the row just below the
    glyph, then just above, then running off to the right, then the left. The
    centre row itself is never offered — a name must not bury its own glyph.
    (`place_labels` bounds- and collision-checks each candidate.)"""
    half = len(text) // 2
    yield (col - half, row + 1)
    yield (col - half, row - 1)
    yield (col + 1, row)
    yield (col - len(text), row)


def place_labels(
    labels: List[Label],
    protected: Set[Coord],
    width: int,
    height: int,
) -> Tuple[List[Placed], List[Label]]:
    """Lay Region names onto blank map space without ever overwriting a glyph.

    `labels` are `Label`s anchored at their Region centre; `protected` is the set
    of buffer cells already holding a glyph (roads, role markers, ``v``, ``@``,
    frame). Towns are placed first so they win any contested strip; each name
    takes the first candidate run (see `_label_candidates`) that is in-bounds and
    clear of both protected cells and names already placed. A name with nowhere
    to go is dropped — still legible via the cursor footer.

    Returns ``(placements, dropped)``: placements carry the role forward so the
    caller can colour Town vs Landmark names without re-deriving it; dropped are
    the untouched input labels."""
    taken: Set[Coord] = set(protected)
    placements: List[Placed] = []
    dropped: List[Label] = []
    ordered = sorted(
        (Label(*lab) for lab in labels),
        key=lambda lab: 0 if lab.role == overworld.TOWN else 1)
    for lab in ordered:
        for scol, srow in _label_candidates(lab.col, lab.row, lab.text):
            cells = [(scol + i, srow) for i in range(len(lab.text))]
            if all(0 <= c < width and 0 <= r < height for c, r in cells) \
                    and not any(cell in taken for cell in cells):
                placements.append(Placed(scol, srow, lab.text, lab.role))
                taken.update(cells)
                break
        else:
            dropped.append(lab)
    return placements, dropped


# ---------------------------------------------------------------------------
# The buffer
# ---------------------------------------------------------------------------
class Buffer:
    """A grid of glyphs the handler blits to a console. Each cell carries a
    character and an fg/bg colour, all drawn from the prose TTF."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.ch: List[List[str]] = [[" "] * width for _ in range(height)]
        self.fg: List[List[Optional[Rgb]]] = [[None] * width for _ in range(height)]
        self.bg: List[List[Optional[Rgb]]] = [[None] * width for _ in range(height)]
        # Cells holding a glyph a printed name must not clobber.
        self.protected: Set[Coord] = set()
        # Region-name placements, laid out clear of every glyph but drawn by the
        # handler in a proportional font (not baked into these cells).
        self.placements: List["Placed"] = []

    def put(self, col: int, row: int, ch: str, fg: Optional[Rgb] = None,
            bg: Optional[Rgb] = None, protect: bool = False) -> None:
        if not (0 <= col < self.width and 0 <= row < self.height):
            return
        self.ch[row][col] = ch
        self.fg[row][col] = fg
        if bg is not None:
            self.bg[row][col] = bg
        if protect:
            self.protected.add((col, row))

    def fill(self, col0: int, row0: int, w: int, h: int, bg: Rgb) -> None:
        for r in range(row0, row0 + h):
            for c in range(col0, col0 + w):
                if 0 <= c < self.width and 0 <= r < self.height:
                    self.bg[r][c] = bg


def _draw_roads(buf: Buffer, coord: Coord) -> None:
    """Thread the road segments through a cell's block: a half-line from the
    centre out to each crossed edge's midpoint, so it meets the neighbour's half
    at the shared seam and the Great Roads read as one continuous line."""
    edges = overworld.road_edges(coord)
    if not edges:
        return
    ox, oy = cell_origin(coord)
    cx, cy = cell_center(coord)
    if "e" in edges:
        for c in range(cx + 1, ox + CELL_W):
            buf.put(c, cy, ROAD_H, ROAD_FG, protect=True)
    if "w" in edges:
        for c in range(ox, cx):
            buf.put(c, cy, ROAD_H, ROAD_FG, protect=True)
    if "n" in edges:
        for r in range(oy, cy):
            buf.put(cx, r, ROAD_V, ROAD_FG, protect=True)
    if "s" in edges:
        for r in range(cy + 1, oy + CELL_H):
            buf.put(cx, r, ROAD_V, ROAD_FG, protect=True)
    # The centre glyph — but a named Region's role marker (drawn later) wins it.
    cell = overworld.cell(coord)
    if cell is None or not cell.name:
        buf.put(cx, cy, seam_glyph(edges), ROAD_FG, protect=True)


def render_map(player_coord: Coord, cursor_coord: Coord) -> Buffer:
    """Build the whole atlas buffer: band-tinted Region blocks with role glyphs,
    the Sea/Mountain frame, the threaded Great Roads, ``▼`` deeps marks, printed
    Town/Landmark names, the player's ``@``, and the cursor highlight on top."""
    buf = Buffer(GRID_W, GRID_H)

    # 1) terrain: every window cell is either a Region (band tint + role glyph)
    #    or a frame square (Sea / Mountain), painted as its whole block.
    labels: List[Label] = []
    for y in range(Y_MIN, Y_MAX + 1):
        for x in range(X_MIN, X_MAX + 1):
            coord = (x, y)
            ox, oy = cell_origin(coord)
            cx, cy = cell_center(coord)
            cell = overworld.cell(coord)
            if cell is None:
                frame = overworld.frame_at(x, y)
                if frame == overworld.SEA:
                    buf.fill(ox, oy, CELL_W, CELL_H, SEA_BG)
                    buf.put(cx, cy, SEA_GLYPH, SEA_FG, protect=True)
                elif frame == overworld.MOUNTAIN:
                    buf.fill(ox, oy, CELL_W, CELL_H, MOUNTAIN_BG)
                    buf.put(cx, cy, MOUNTAIN_GLYPH, MOUNTAIN_FG, protect=True)
                continue
            buf.fill(ox, oy, CELL_W, CELL_H, BAND_BG[cell.band])
            buf.put(cx, cy, ROLE_GLYPH[cell.role], BAND_FG[cell.band], protect=True)
            if cell.name:
                labels.append(Label(cx, cy, cell.name, cell.role))

    # 2) roads over the terrain (a knee cell may have no name, so its centre
    #    takes the seam glyph; a named Region keeps its role marker).
    for coord in overworld.GRID:
        if in_window(coord):
            _draw_roads(buf, coord)

    # 3) deeps mark in the block's SE corner, clear of the centre + road rows.
    for coord, cell in overworld.GRID.items():
        if cell.deeps and in_window(coord):
            ox, oy = cell_origin(coord)
            buf.put(ox + CELL_W - 1, oy + CELL_H - 1, DEEPS_GLYPH,
                    DEEPS_FG, protect=True)

    # 4) the player's Region — an @ over its centre (also while below ground: it
    #    marks the Region the deeps lie beneath).
    if in_window(player_coord):
        pcx, pcy = cell_center(player_coord)
        buf.put(pcx, pcy, PLAYER_GLYPH, PLAYER_FG, protect=True)

    # 5) region names: laid out clear of every glyph, but *not* baked into the
    #    cells — the handler draws them natively in a proportional font (so a name
    #    reads as a word, not one wide grid glyph per letter). place_labels still
    #    reserves each name a clear run; the handler maps the anchor cell to pixels.
    buf.placements, _ = place_labels(labels, buf.protected, buf.width, buf.height)

    # 6) the cursor highlight on the very top.
    if in_window(cursor_coord):
        ox, oy = cell_origin(cursor_coord)
        for r in range(oy, oy + CELL_H):
            for c in range(ox, ox + CELL_W):
                buf.bg[r][c] = CURSOR_BG
    return buf


# ---------------------------------------------------------------------------
# Legend — the key the handler prints below the map. Kept here so the glyph and
# colour vocabulary lives in one place beside the map it describes.
# ---------------------------------------------------------------------------
class LegendEntry(NamedTuple):
    glyph: str
    label: str
    fg: Rgb


def band_legend() -> List[LegendEntry]:
    """The danger-band colour key, each shown as a coloured swatch."""
    return [LegendEntry("•", band, BAND_FG[band]) for band in overworld.BANDS]


def role_legend() -> List[LegendEntry]:
    """The marker key: what each glyph drawn on the map means."""
    return [
        LegendEntry(ROLE_GLYPH[overworld.TOWN], "town", BAND_FG[overworld.FREE]),
        LegendEntry(ROLE_GLYPH[overworld.LANDMARK], "landmark", LANDMARK_NAME_FG),
        LegendEntry(ROLE_GLYPH[overworld.GATEWAY], "gateway", LANDMARK_NAME_FG),
        LegendEntry(DEEPS_GLYPH, "deeps", DEEPS_FG),
        LegendEntry(PLAYER_GLYPH, "you", PLAYER_FG),
    ]


# ---------------------------------------------------------------------------
# Cursor footer
# ---------------------------------------------------------------------------
class Description(NamedTuple):
    title: str
    note: str
    deeps: int
    off_grid: bool


def describe(coord: Coord) -> Description:
    """What the footer says about the cell under the cursor: a Region's name,
    note, and deeps count — or, for an off-grid frame square, the Sea or the
    Misty Mountains it reads as."""
    cell = overworld.cell(coord)
    if cell is None:
        frame = overworld._impassable_frame(*coord)
        if frame == overworld.SEA:
            return Description(
                "The Sea", "The grey waters of the Gulf of Lune; no road runs here.",
                0, True)
        if frame == overworld.MOUNTAIN:
            return Description(
                "The Misty Mountains",
                "The great wall of Hithaeglir; uncrossable but at the guarded passes.",
                0, True)
        return Description("Uncharted", "Beyond the edge of the Ranger's atlas.", 0, True)
    return Description(cell.region_name, cell.note, cell.deeps, False)
