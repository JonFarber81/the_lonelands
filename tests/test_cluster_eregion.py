"""Cluster 7 — Eregion & the Mountain-gates (issue #22): the SE gates under the
Misty Mountains — the holly-country of Hollin, ruined Ost-in-Edhil of the
Elven-smiths, the Hollin gate of Khazad-dûm with the Watcher's pool, and the
Redhorn Pass over Caradhras.

The registry infra (ADR 0003) already makes every cell enterable with generic
placeholder terrain; this cluster gives its named anchors **lore-appropriate,
recognizable** terrain composed from the terrain toolkit (`procgen`), while keeping
the cluster's Definition of Done: every cell enterable from all present neighbours,
band-appropriate beasts (Wild → Perilous → Dark), the diegetic mountain/gate wall on
the cut-off east and south edges, and save/load round-trips. (No roads are drawn
here; the Ost-in-Edhil and Moria deeps are plan markers dug in a later pass — out of
scope.)
"""
from __future__ import annotations

import pytest

from lonelands import (
    content, overworld, procgen, savegame, setup_game, tile_types, world,
)
from lonelands.dice import set_seed

# The cluster box: x +4..+6, y +2..+3 (Eregion under the mountain wall).
CLUSTER = [c for c in overworld.GRID if 4 <= c[0] <= 6 and 2 <= c[1] <= 3]
# The named anchors this cluster authors.
ANCHORS = {
    (4, 3): "Ost-in-Edhil",
    (5, 3): "Moria West-gate",
    (6, 2): "Redhorn Pass",
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

def test_ost_in_edhil_is_a_ruined_smith_city_in_holly_country(game):
    _, gw, _ = game
    city = _surface(gw, (4, 3))
    assert _count(city, tile_types.building_wall) > 40, "the ruined halls should read as a city"
    assert _count(city, tile_types.cobble) > 30, "no cobbled smith-plaza at the centre"
    assert _count(city, tile_types.tree) > 100, "no holly of Hollin crowding the stone"


def test_moria_gate_shows_the_doors_and_the_watchers_pool(game):
    _, gw, _ = game
    gate = _surface(gw, (5, 3))
    assert _count(gate, tile_types.building_wall) > 8, "no Doors of Durin set in the cliff"
    assert _count(gate, tile_types.door) > 0, "no West-door itself"
    assert _count(gate, tile_types.water) > 40, "no Watcher's pool before the doors"
    assert _count(gate, tile_types.hill) > 150, "no mountain cliff rearing along the east"


def test_redhorn_pass_is_bare_mountain_rock(game):
    _, gw, _ = game
    pass_ = _surface(gw, (6, 2))
    assert _count(pass_, tile_types.hill) > 250, "the high pass should read as bare rock"


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


def test_dark_gateway_carries_band_beasts(game):
    _, gw, player = game
    # Redhorn Pass is Dark — the meanest table. The shared model ties count to band
    # danger, so it fields at least the band's low bound of threats.
    pass_ = _surface(gw, (6, 2))
    (lo, _), _ = content.BAND_THREATS["Dark"]
    beasts = sum(1 for a in pass_.actors if a is not player)
    assert beasts >= lo


def test_redhorn_gate_is_a_pass_cut_through_the_mountain_wall(game):
    """The east 'gate' edge reads as a crossing in the wall, not masonry (#15):
    a mountain ridge with a road pass cut through its middle."""
    _, gw, _ = game
    pass_ = _surface(gw, (6, 2))
    east_col = pass_.width - 1
    hills = sum(1 for y in range(pass_.height)
                if pass_.tiles[east_col, y] == tile_types.hill)
    roads = sum(1 for y in range(pass_.height)
                if pass_.tiles["kind"][east_col, y] == tile_types.KIND_ROAD)
    assert hills > 6, "no mountain ridge along the gated east edge"
    assert roads > 0, "no road pass cut through the ridge"


def test_south_edge_shows_the_mountain_wall_barrier(game):
    """The cut-off south is the Misty-Mountain wall, painted diegetically (#15)."""
    _, gw, _ = game
    # (6,3) has no southern neighbour: the wall (diegetic Mountain = hills) stands.
    corner = _surface(gw, (6, 3))
    south_row = corner.height - 1
    hills = sum(1 for x in range(corner.width)
                if corner.tiles[x, south_row] == tile_types.hill)
    assert hills > 6, "no diegetic mountain wall along the cut-off south edge"


def test_cluster_region_round_trips_through_save_load(game, tmp_path):
    engine, gw, player = game
    gw.teleport_to((5, 3))                     # jump to the Moria gate
    assert gw.coord == (5, 3)
    path = tmp_path / "cluster.sav"
    savegame.save_game(engine, str(path))
    after = savegame.load_game(str(path))
    assert after.game_world.coord == (5, 3)
    assert (5, 3) in after.game_world.regions
    assert after.game_world.current_region.level(0) is not None
