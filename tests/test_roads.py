"""Road-threading tests (Infra C, issue #14): the per-edge road model
(`overworld.ROAD_EDGES`), the meandering tile pass (`procgen.thread_road`) that
enters/exits at the shared edge midpoints, ford/bridge crossings where a road
meets water, and arrival-mirroring landing the player on the road."""
from __future__ import annotations

from collections import deque

import pytest

from lonelands import overworld, procgen, setup_game, tile_types
from lonelands.dice import set_seed
from lonelands.game_map import GameMap


@pytest.fixture
def game():
    set_seed(1)
    engine = setup_game.new_game()
    return engine, engine.game_world, engine.player


# --- the per-edge model -----------------------------------------------------

def test_east_road_threads_east_west_along_row_zero():
    # The Great East Road runs Bree -> Rivendell; the first cells hop due-east.
    assert "e" in overworld.road_edges((0, 0))     # Bree, heading east
    assert overworld.road_edges((1, 0)) == frozenset({"w", "e"})
    assert overworld.road_edges((2, 0)) == frozenset({"w", "e"})


def test_road_edges_are_symmetric_across_every_seam():
    # If a cell's road crosses an edge, the neighbour's road crosses back.
    for coord, edges in overworld.ROAD_EDGES.items():
        for edge in edges:
            dx, dy = overworld.EDGE_DELTA[edge]
            nb = (coord[0] + dx, coord[1] + dy)
            assert nb in overworld.GRID, f"{coord} road runs off the grid at {edge}"
            opp = overworld._OPP[edge]
            assert opp in overworld.road_edges(nb), \
                f"{coord}-{edge} not mirrored by {nb}-{opp}"


def test_diagonal_path_steps_staircase_through_a_knee_cell():
    # The Greenway steps diagonally (0,2)->(1,3); the model routes it through the
    # orthogonal knee (1,2) so the line stays 4-connected.
    assert overworld.road_edges((1, 2)) == frozenset({"w", "s"})   # the knee
    assert "e" in overworld.road_edges((0, 2))     # (0,2) leaves east to the knee
    assert "n" in overworld.road_edges((1, 3))     # (1,3) receives it from the north


# --- the tile pass ----------------------------------------------------------

def _blank(engine):
    gm = GameMap(engine, procgen.MAP_WIDTH, procgen.MAP_HEIGHT, outdoors=True)
    gm.tiles[:] = tile_types.grass
    return gm


def test_thread_road_reaches_every_edge_midpoint(game):
    engine, gw, player = game
    for coord, edges in overworld.ROAD_EDGES.items():
        gm = _blank(engine)
        procgen.thread_road(gm, coord)
        for edge in edges:
            mx, my = procgen._EDGE_MIDPOINT[edge]
            assert int(gm.tiles["kind"][mx, my]) == tile_types.KIND_ROAD, \
                f"{coord} has no road at its {edge} edge midpoint {(mx, my)}"


def test_threaded_road_is_four_connected(game):
    engine, gw, player = game
    gm = _blank(engine)
    procgen.thread_road(gm, (1, 0))     # a straight east-west through-cell
    roads = {(x, y) for x in range(gm.width) for y in range(gm.height)
             if int(gm.tiles["kind"][x, y]) == tile_types.KIND_ROAD}
    # flood-fill from the west midpoint; the whole road must be one 4-connected run
    start = procgen._EDGE_MIDPOINT["w"]
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (x + dx, y + dy)
            if nb in roads and nb not in seen:
                seen.add(nb)
                q.append(nb)
    assert seen == roads, "the threaded road is not 4-connected"


def test_road_bridges_where_it_crosses_water(game):
    engine, gw, player = game
    gm = _blank(engine)
    # a river straight down the road's centre column
    for y in range(gm.height):
        gm.tiles[procgen.ROAD_COL, y] = tile_types.water
    procgen.thread_road(gm, (1, 0))     # its road runs along ROAD_ROW, crossing it
    x, y = procgen.ROAD_COL, procgen.ROAD_ROW
    # the crossing is a bridge/ford: a road-kind tile drawn with the bridge glyph
    assert int(gm.tiles["kind"][x, y]) == tile_types.KIND_ROAD
    assert gm.tiles["light"][x, y]["ch"] == tile_types.bridge["light"]["ch"], \
        "road did not ford the water"


# --- the whole system, on real Surfaces -------------------------------------

def test_placeholder_road_cell_gets_a_threaded_road(game):
    engine, gw, player = game
    gm = gw.region((1, 0)).level(0)     # East Road filler, threaded at generation
    assert int(gm.tiles["kind"][0, procgen.ROAD_ROW]) == tile_types.KIND_ROAD
    assert int(gm.tiles["kind"][gm.width - 1, procgen.ROAD_ROW]) == tile_types.KIND_ROAD


def test_crossing_a_road_edge_lands_the_player_on_the_road(game):
    engine, gw, player = game
    gw.coord, gw.level_index = (0, 0), 0
    gm = gw.current_region.level(0)
    engine.game_map = gm
    # step off Bree's east edge well away from the road row...
    player.x, player.y = gm.width - 1, 5
    assert gw.cross_edge(1, 0) is True
    assert gw.coord == (1, 0)
    landing = gw.current_region.level(0)
    assert int(landing.tiles["kind"][player.x, player.y]) == tile_types.KIND_ROAD, \
        "arrival did not land the player on the road"


@pytest.mark.parametrize("road,name", [
    (overworld.EAST_ROAD, "the Great East Road (Bree -> Rivendell)"),
    (overworld.GREENWAY, "the Greenway (Fornost -> Tharbad)"),
    (overworld.SHIRE_ROAD, "the Shire Road (Michel Delving -> Bree)"),
])
def test_walking_a_great_road_stays_on_a_continuous_road(game, road, name):
    """The Done-when: each road stays on a continuous, threaded road across every
    cluster seam — crossing a seam always lands the player back on the road."""
    engine, gw, player = game
    ortho = overworld._orthogonalize(road)
    gw.coord, gw.level_index = ortho[0], 0
    engine.game_map = gw.current_region.level(0)
    for a, b in zip(ortho, ortho[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        edge = overworld._edge_between(a, b)
        player.x, player.y = procgen._EDGE_MIDPOINT[edge]   # on this cell's road...
        assert gw.cross_edge(dx, dy) is True, f"{name}: blocked crossing {a}->{b}"
        assert gw.coord == b
        landed = gw.current_region.level(0)
        assert int(landed.tiles["kind"][player.x, player.y]) == tile_types.KIND_ROAD, \
            f"{name}: stepped off the road arriving at {b}"
