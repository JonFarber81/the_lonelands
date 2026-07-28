"""Cluster 3 — The Lone-lands & the East-Road corridor (issue #18): the road
east to Rivendell, from the Weather Hills to Imladris.

The registry infra (ADR 0003) already makes every cell enterable with generic
placeholder terrain; this cluster gives its named anchors **lore-appropriate,
recognizable** terrain composed from the terrain toolkit (`procgen`), while
keeping the cluster's Definition of Done: every cell enterable from all present
neighbours, band-appropriate wandering beasts, roads threaded across seams,
diegetic barriers on closed edges, and save/load round-trips. (Weathertop at
(2,0) is authored in its own pass; this cluster fills the rest of the corridor.)
"""
from __future__ import annotations

import pytest

from lonelands import (
    content, overworld, procgen, savegame, setup_game, tile_types, world,
)
from lonelands.dice import set_seed

# The cluster box: x +2..+7, y -1..0, plus the Weather Hills at (2,-2).
CLUSTER = [c for c in overworld.GRID
           if 2 <= c[0] <= 7 and -1 <= c[1] <= 0] + [(2, -2)]
# The named anchors this cluster authors (Weathertop (2,0) is authored elsewhere).
ANCHORS = {
    (2, -2): "Weather Hills",
    (4, -1): "Last Bridge",
    (5, -1): "Trollshaws",
    (7, -1): "Fords of Bruinen",
    (6, 0): "Rivendell",
}


@pytest.fixture
def game():
    set_seed(1)
    engine = setup_game.new_game()
    return engine, engine.game_world, engine.player


def _count(gm, tile) -> int:
    return int((gm.tiles == tile).sum())


def _surface(gw, coord):
    return gw.region(coord).level(0)


# --- the anchors are authored, not generic placeholders ---------------------

def test_every_named_anchor_has_an_authored_surface():
    for coord in ANCHORS:
        assert coord in world._AUTHORED_SURFACES, \
            f"{ANCHORS[coord]} {coord} is still a placeholder"


# --- recognizable, lore-appropriate terrain (terrain by place, not band) ----

def test_weather_hills_is_a_stony_ridge(game):
    _, gw, _ = game
    hills = _surface(gw, (2, -2))
    assert _count(hills, tile_types.hill) > 100, "the ridge-line should read as stony hills"


def test_last_bridge_crosses_the_hoarwell(game):
    _, gw, _ = game
    bridge = _surface(gw, (4, -1))
    assert _count(bridge, tile_types.water) > 100, "the Hoarwell should run through"
    assert _count(bridge, tile_types.bridge) > 0, "no last bridge across the river"
    # The East Road threads east-west over the bridge; both edge midpoints road.
    for edge in ("e", "w"):
        mx, my = procgen._EDGE_MIDPOINT[edge]
        assert int(bridge.tiles["kind"][mx, my]) == tile_types.KIND_ROAD


def test_trollshaws_is_wooded_rock(game):
    _, gw, _ = game
    shaws = _surface(gw, (5, -1))
    assert _count(shaws, tile_types.tree) > 400, "the Trollshaws should read as woodland"
    assert _count(shaws, tile_types.hill) > 40, "stone-strewn rocky ridges are missing"


def test_fords_of_bruinen_has_a_ford_and_a_mountain_gate(game):
    _, gw, _ = game
    fords = _surface(gw, (7, -1))
    assert _count(fords, tile_types.water) > 80, "the Bruinen should run through"
    assert _count(fords, tile_types.bridge) > 0, "no ford across the river"
    # The Misty-Mountain wall stands to the north (diegetic Mountain = hills), and
    # the eastward gate cuts a road pass through the wall on the east edge.
    assert _count(fords, tile_types.hill) > 20, "no mountain wall to the north"
    east_col = fords.width - 1
    assert any(int(fords.tiles["kind"][east_col, y]) == tile_types.KIND_ROAD
               for y in range(fords.height)), "the gateway pass east is walled off"


def test_rivendell_is_the_last_homely_house_in_its_vale(game):
    _, gw, _ = game
    riven = _surface(gw, (6, 0))
    assert _count(riven, tile_types.building_wall) > 40, "no Last Homely House"
    assert _count(riven, tile_types.water) > 30, "the Bruinen should fall through the vale"
    assert _count(riven, tile_types.tree) > 200, "the wooded valley walls are missing"


# --- the Definition of Done -------------------------------------------------

def test_every_cluster_cell_is_enterable_from_all_present_neighbours(game):
    """Walk each shared edge into every cluster cell; arrival lands walkable."""
    engine, gw, player = game
    for coord in CLUSTER:
        for edge, (dx, dy) in overworld.EDGE_DELTA.items():
            src = (coord[0] - dx, coord[1] - dy)     # the neighbour we come from
            if src not in overworld.GRID:
                continue
            gw.coord, gw.level_index = src, 0
            engine.game_map = gw.current_region.level(0)
            # leave from a spot off the road row so we exercise nearest_walkable
            player.x, player.y = procgen._EDGE_MIDPOINT[edge]
            player.y = min(player.y + 3, procgen.MAP_HEIGHT - 1)
            assert gw.cross_edge(dx, dy) is True, f"blocked entering {coord} from {src}"
            assert gw.coord == coord
            landing = gw.current_region.level(0)
            assert landing.tiles["walkable"][player.x, player.y], \
                f"{coord} arrival from {src} is not walkable"


def test_perilous_anchor_crawls_with_beasts(game):
    _, gw, player = game
    # The Trollshaws is Perilous — the shared model ties count to band danger, so
    # it must field at least the band's low bound of wandering threats.
    shaws = _surface(gw, (5, -1))
    (lo, _), _ = content.BAND_THREATS["Perilous"]
    beasts = sum(1 for a in shaws.actors if a is not player)
    assert beasts >= lo


def test_cluster_region_round_trips_through_save_load(game, tmp_path):
    engine, gw, player = game
    gw.teleport_to((6, 0))                   # jump to Rivendell
    assert gw.coord == (6, 0)
    path = tmp_path / "cluster.sav"
    savegame.save_game(engine, str(path))
    after = savegame.load_game(str(path))
    assert after.game_world.coord == (6, 0)
    assert (6, 0) in after.game_world.regions
    assert after.game_world.current_region.level(0) is not None
