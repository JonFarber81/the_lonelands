"""Cluster 2 — Bree & environs (issue #17): the hub around the crossroads.

The registry infra (ADR 0003) already makes every cell enterable with generic
placeholder terrain; this cluster gives its named anchors **lore-appropriate,
recognizable** terrain composed from the terrain toolkit (`procgen`), while
keeping the cluster's Definition of Done: every cell enterable from all present
neighbours, band-appropriate wandering beasts, roads threaded across seams,
diegetic barriers on closed edges, and save/load round-trips.
"""
from __future__ import annotations

import pytest

from lonelands import (
    content, overworld, procgen, savegame, setup_game, tile_types, world,
)
from lonelands.dice import set_seed

# The 3x3 box around Bree, plus the Old Forest that leans in at (-2, 1).
CLUSTER = [
    (-1, -1), (0, -1), (1, -1),
    (-1, 0), (0, 0), (1, 0),
    (-2, 1), (-1, 1), (0, 1), (1, 1),
]
# The named anchors this cluster authors (Bree & Barrow-downs are authored
# elsewhere; these five gain identity in this pass).
ANCHORS = {
    (0, -1): "Chetwood",
    (1, -1): "Midgewater",
    (-2, 1): "Old Forest",
    (-1, 1): "Sarn Ford",
    (0, 1): "South Downs",
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

def test_midgewater_reads_as_a_marsh(game):
    _, gw, _ = game
    marsh = _surface(gw, (1, -1))
    generic = procgen.generate_placeholder_surface(
        gw.engine, overworld.cell((1, 1)))     # a plain Wild filler for contrast
    # Standing water is the marsh's signature — far more than open country.
    assert _count(marsh, tile_types.water) > 60
    assert _count(marsh, tile_types.water) > _count(generic, tile_types.water)


def test_old_forest_is_densely_wooded(game):
    _, gw, _ = game
    forest = _surface(gw, (-2, 1))
    # An ancient wood: trees dominate the map far beyond ordinary scatter.
    assert _count(forest, tile_types.tree) > 500


def test_south_downs_rolls_with_hills(game):
    _, gw, _ = game
    downs = _surface(gw, (0, 1))
    assert _count(downs, tile_types.hill) > 80


def test_sarn_ford_has_a_ford_and_a_watch_post(game):
    _, gw, _ = game
    ford = _surface(gw, (-1, 1))
    assert _count(ford, tile_types.water) > 30, "the Brandywine should run through"
    assert _count(ford, tile_types.bridge) > 0, "no ford across the river"
    assert _count(ford, tile_types.building_wall) > 0, "no Rangers' watch-post"


def test_chetwood_is_wooded_and_carries_the_greenway(game):
    _, gw, _ = game
    wood = _surface(gw, (0, -1))
    assert _count(wood, tile_types.tree) > 450, "Chetwood should read as woodland"
    # The Greenway threads north-south through Chetwood; both edge midpoints road.
    for edge in ("n", "s"):
        mx, my = procgen._EDGE_MIDPOINT[edge]
        assert int(wood.tiles["kind"][mx, my]) == tile_types.KIND_ROAD


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


def test_cluster_cells_field_band_appropriate_beasts(game):
    _, gw, player = game
    # A Perilous anchor (Old Forest) must crawl with beasts; the shared model
    # ties count to band danger.
    forest = _surface(gw, (-2, 1))
    (lo, _), _ = content.BAND_BEASTS["Perilous"]
    beasts = sum(1 for a in forest.actors if a is not player)
    assert beasts >= lo


def test_cluster_region_round_trips_through_save_load(game, tmp_path):
    engine, gw, player = game
    gw.cross_edge(0, -1)                     # travel north into Chetwood
    assert gw.coord == (0, -1)
    path = tmp_path / "cluster.sav"
    savegame.save_game(engine, str(path))
    after = savegame.load_game(str(path))
    assert after.game_world.coord == (0, -1)
    # the visited Region is cached by coord and rebuilds its surface on demand
    assert (0, -1) in after.game_world.regions
    assert after.game_world.current_region.level(0) is not None
