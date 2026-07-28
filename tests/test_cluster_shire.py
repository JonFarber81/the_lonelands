"""Cluster 1 — The Shire & the green west (issue #16): the pastoral Free-Lands
from the Grey Havens to the Brandywine Bridge.

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

# The cluster box: x -7..-2, y -1..+1 (the cells present in the grid).
CLUSTER = [c for c in overworld.GRID
           if -7 <= c[0] <= -2 and -1 <= c[1] <= 1]
# The named anchors this cluster authors.
ANCHORS = {
    (-7, 0): "Grey Havens",
    (-6, 0): "White Towers",
    (-5, 0): "Far Downs",
    (-4, 0): "Michel Delving",
    (-3, -1): "Hobbiton",
    (-2, -1): "Brandywine Bridge",
    (-5, 1): "Tower Hills",
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

def test_grey_havens_is_a_harbour_with_elven_houses(game):
    _, gw, _ = game
    havens = _surface(gw, (-7, 0))
    generic = procgen.generate_placeholder_surface(
        gw.engine, overworld.cell((-5, 0)))         # a plain Free filler for contrast
    # The Gulf of Lune floods half the map — far more water than open country.
    assert _count(havens, tile_types.water) > 400
    assert _count(havens, tile_types.water) > _count(generic, tile_types.water)
    assert _count(havens, tile_types.building_wall) > 0, "no elven houses on the shore"


def test_white_towers_stand_on_the_green_hills(game):
    _, gw, _ = game
    towers = _surface(gw, (-6, 0))
    assert _count(towers, tile_types.building_wall) > 0, "no white towers"
    assert _count(towers, tile_types.hill) > 40, "the Emyn Beraid should rise green"


def test_far_downs_rolls_with_hills(game):
    _, gw, _ = game
    downs = _surface(gw, (-5, 0))
    assert _count(downs, tile_types.hill) > 80


def test_michel_delving_is_a_town_with_the_mathom_house(game):
    _, gw, _ = game
    town = _surface(gw, (-4, 0))
    # A cluster of houses about the great Mathom-house hall reads as a town.
    assert _count(town, tile_types.building_wall) > 60, "Michel Delving should read as a town"


def test_hobbiton_has_the_hill_and_smial_doors(game):
    _, gw, _ = game
    hobbiton = _surface(gw, (-3, -1))
    assert _count(hobbiton, tile_types.hill) > 30, "the Hill should rise over Hobbiton"
    assert _count(hobbiton, tile_types.door) > 4, "no round smial-doors (Bag End & co.)"


def test_brandywine_bridge_has_a_river_and_a_stone_bridge(game):
    _, gw, _ = game
    bridge = _surface(gw, (-2, -1))
    assert _count(bridge, tile_types.water) > 100, "the Brandywine should run through"
    assert _count(bridge, tile_types.bridge) > 0, "no stone bridge across the river"
    # The East Road threads east-west over the bridge; both edge midpoints road.
    for edge in ("e", "w"):
        mx, my = procgen._EDGE_MIDPOINT[edge]
        assert int(bridge.tiles["kind"][mx, my]) == tile_types.KIND_ROAD


def test_tower_hills_is_green_down_country(game):
    _, gw, _ = game
    hills = _surface(gw, (-5, 1))
    assert _count(hills, tile_types.hill) > 80


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
    # The whole cluster is Free-Lands: the shared model ties count to band, so a
    # peaceful green west simply reads as near-empty. Assert the model ran (a
    # Perilous cluster would crawl; Free is calm by design).
    (lo, hi), _ = content.BAND_THREATS["Free"]
    downs = _surface(gw, (-5, 0))
    beasts = sum(1 for a in downs.actors if a is not player)
    assert lo <= beasts <= hi


def test_cluster_region_round_trips_through_save_load(game, tmp_path):
    engine, gw, player = game
    gw.teleport_to((-4, 0))                  # jump to Michel Delving
    assert gw.coord == (-4, 0)
    path = tmp_path / "cluster.sav"
    savegame.save_game(engine, str(path))
    after = savegame.load_game(str(path))
    assert after.game_world.coord == (-4, 0)
    assert (-4, 0) in after.game_world.regions
    assert after.game_world.current_region.level(0) is not None
