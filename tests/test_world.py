"""World navigation tests: the grid of Regions, walk-the-edge crossing, and
Enter-the-Level descent. Built on a real headless game (`setup_game.new_game`
constructs the full engine + world without a display)."""
from __future__ import annotations

import pytest

from lonelands import setup_game, tile_types
from lonelands.dice import set_seed
from lonelands.game_map import GameMap
from lonelands.world import GameWorld, Region, _nearest_walkable


@pytest.fixture
def game():
    set_seed(1)
    engine = setup_game.new_game()
    return engine, engine.game_world, engine.player


def place_on_surface(engine, gw, coord, x, y):
    """Drop the player onto a given Region's Surface at (x, y)."""
    gw.coord = coord
    gw.level_index = 0
    gm = gw.current_region.level(0)
    engine.game_map = gm
    engine.player.x, engine.player.y = x, y
    return gm


# --- starting state ---------------------------------------------------------

def test_new_game_starts_in_bree_on_the_surface(game):
    engine, gw, player = game
    assert gw.coord == (0, 0)
    assert gw.level_index == 0
    assert engine.game_map.name.startswith("Bree")


# --- the adjacency graph ----------------------------------------------------

def test_the_grid_is_populated_and_named(game):
    engine, gw, player = game
    # Bree's four neighbours, on the full 15x9 grid (ADR 0003).
    assert gw.region((-1, 0)).name == "Barrow-downs"     # Tyrn Gorthad, west
    assert gw.region((0, -1)).name == "Chetwood"         # north
    assert gw.region((0, 1)).name == "South Downs"       # south
    assert gw.region((2, 0)).name == "Weathertop"        # Amon Sûl, east along the Road
    assert gw.region((1, 0)) is not None                 # wilderness filler now exists


def test_impassable_cells_are_absent(game):
    engine, gw, player = game
    # The Sea/Mountain frame is the *absence* of a Region (ADR 0002/0003).
    assert gw.region((-7, 2)) is None     # the Gulf of Lune
    assert gw.region((7, 2)) is None       # the Misty Mountains wall
    assert gw.region((-99, 0)) is None     # far off the grid entirely


@pytest.mark.parametrize("dx,dy,coord", [
    (1, 0, (1, 0)), (-1, 0, (-1, 0)), (0, -1, (0, -1)), (0, 1, (0, 1)),
])
def test_crossing_each_edge_and_back_is_symmetric(game, dx, dy, coord):
    engine, gw, player = game
    place_on_surface(engine, gw, (0, 0), 20, 15)
    assert gw.cross_edge(dx, dy) is True
    assert gw.coord == coord
    assert gw.level_index == 0
    # walking back the opposite way returns to Bree
    assert gw.cross_edge(-dx, -dy) is True
    assert gw.coord == (0, 0)


# --- crossing mechanics -----------------------------------------------------

def test_arrival_mirrors_the_crossing_row(game):
    engine, gw, player = game
    place_on_surface(engine, gw, (0, 0), 61, 22)  # on the east edge, row 22
    gw.cross_edge(1, 0)
    # east exit -> arrive on the west edge (col 0), same row (road there is walkable)
    assert player.x == 0
    assert player.y == 22


def test_no_neighbour_blocks_the_crossing(game):
    engine, gw, player = game
    place_on_surface(engine, gw, (6, 1), 61, 22)  # against the Misty Mountains wall
    assert gw.cross_edge(1, 0) is False           # nothing at (7, 1) — impassable
    assert gw.coord == (6, 1)                      # stayed put


def test_diagonal_corner_move_does_not_cross(game):
    engine, gw, player = game
    place_on_surface(engine, gw, (0, 0), 61, 43)
    assert gw.cross_edge(1, 1) is False            # would leave on both axes


def test_only_the_surface_edge_connects(game):
    engine, gw, player = game
    # Descend into the barrow first, then try to walk off its edge.
    surface = place_on_surface(engine, gw, (-1, 0), 0, 0)
    player.x, player.y = surface.ruin_entrance_xy
    gw.use_tile()
    assert gw.level_index == -1
    assert gw.cross_edge(1, 0) is False            # deeps never edge-connect


# --- vertical: Enter the Levels --------------------------------------------

def test_enter_descends_and_ascends_the_barrow(game):
    engine, gw, player = game
    surface = place_on_surface(engine, gw, (-1, 0), 0, 0)
    ex, ey = surface.ruin_entrance_xy
    player.x, player.y = ex, ey

    assert gw.use_tile() is not None               # into the deeps
    assert gw.level_index == -1

    player.x, player.y = engine.game_map.entry_xy  # the up-stair
    gw.use_tile()
    assert gw.level_index == 0                      # back on the Surface
    assert engine.game_map.name.startswith("The Barrow-downs")


def test_enter_does_nothing_on_plain_ground(game):
    engine, gw, player = game
    place_on_surface(engine, gw, (0, 0), 20, 15)    # Bree cobbles
    assert gw.use_tile() is None
    assert gw.level_index == 0


# --- persistence ------------------------------------------------------------

def test_regions_and_levels_are_cached(game):
    engine, gw, player = game
    assert gw.region((1, 0)) is gw.region((1, 0))
    region = gw.region((1, 0))
    assert region.level(0) is region.level(0)


def test_bree_all_edges_and_npcs_are_reachable_on_foot(game):
    """Bree's layout is hand-tuned; guard against an edit sealing a gate or
    stranding an NPC behind a wall."""
    from collections import deque
    engine, gw, player = game
    gm = place_on_surface(engine, gw, (0, 0), *engine.game_world.region((0, 0)).level(0).start_xy)
    W, H = gm.width, gm.height
    walk = gm.tiles["walkable"]

    seen = {gm.start_xy}
    q = deque([gm.start_xy])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in seen and walk[nx, ny]:
                seen.add((nx, ny))
                q.append((nx, ny))

    assert any((0, y) in seen for y in range(H)), "west edge unreachable"
    assert any((W - 1, y) in seen for y in range(H)), "east edge unreachable"
    assert any((x, 0) in seen for x in range(W)), "north edge unreachable"
    assert any((x, H - 1) in seen for x in range(W)), "south edge unreachable"

    npcs = [a for a in gm.actors if a is not player]
    assert len(npcs) == 4
    for npc in npcs:
        assert walk[npc.x, npc.y], f"{npc.name} stands on an unwalkable tile"
        assert (npc.x, npc.y) in seen, f"{npc.name} is unreachable"


def test_nearest_walkable_finds_an_open_tile():
    from lonelands.engine import Engine
    from lonelands import content
    e = Engine(content.make_player())
    gm = GameMap(e, 10, 10)
    gm.tiles[:] = tile_types.wall          # everything blocked...
    gm.tiles[5, 5] = tile_types.floor      # ...except one tile
    assert _nearest_walkable(gm, 0, 0) == (5, 5)
