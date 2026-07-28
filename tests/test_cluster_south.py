"""Cluster 6 — The South (Cardolan → Tharbad) (issue #21): the southern reach down
the Greenway — the emptied realm of Cardolan (barrows and broken keeps) giving way
to the Greyflood marsh-flats at ruined Tharbad, the southern gateway.

The registry infra (ADR 0003) already makes every cell enterable with generic
placeholder terrain; this cluster gives its named anchors **lore-appropriate,
recognizable** terrain composed from the terrain toolkit (`procgen`), while keeping
the cluster's Definition of Done: every cell enterable from all present neighbours,
Wild-band wandering beasts, the diegetic wood barrier on the cut-off south edge, the
Greenway threaded across the seams, and save/load round-trips. (Tharbad's silted
deeps are a plan marker dug in a later pass — out of scope here.)
"""
from __future__ import annotations

import pytest

from lonelands import (
    content, overworld, procgen, savegame, setup_game, tile_types, world,
)
from lonelands.dice import set_seed

# The cluster box: x 0..3, y +2..+4 (the centre-south down the Greenway).
CLUSTER = [c for c in overworld.GRID if 0 <= c[0] <= 3 and 2 <= c[1] <= 4]
# The named anchors this cluster authors.
ANCHORS = {
    (1, 2): "Cardolan",
    (1, 4): "Tharbad",
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

def test_cardolan_is_an_emptied_realm_of_downs_and_broken_keeps(game):
    _, gw, _ = game
    card = _surface(gw, (1, 2))
    assert _count(card, tile_types.hill) > 80, "the low downs and barrows should read as hills"
    assert _count(card, tile_types.building_wall) > 0, "no broken keeps of the fallen realm"
    assert _count(card, tile_types.rubble) > 20, "no tumbled stone about the keeps"


def test_tharbad_is_a_ruined_city_on_the_marsh_flats(game):
    _, gw, _ = game
    thar = _surface(gw, (1, 4))
    assert _count(thar, tile_types.water) > 200, "the Greyflood should silt into marsh-flats"
    assert _count(thar, tile_types.cobble) > 20, "no stone causeway carrying the Greenway"
    assert _count(thar, tile_types.building_wall) > 0, "no drowned stonework of the old town"


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


def test_wild_anchor_carries_band_beasts(game):
    _, gw, player = game
    # Cardolan is Wild: the shared model ties count to band danger, so it fields
    # at least the band's low bound of wandering threats.
    card = _surface(gw, (1, 2))
    (lo, _), _ = content.BAND_THREATS["Wild"]
    beasts = sum(1 for a in card.actors if a is not player)
    assert beasts >= lo


def test_greenway_threads_through_tharbad(game):
    """Tharbad carries the Greenway in from its northern seam (#14)."""
    _, gw, _ = game
    thar = _surface(gw, (1, 4))
    top_row = [thar.tiles["kind"][x, 0] for x in range(thar.width)]
    assert any(k == tile_types.KIND_ROAD for k in top_row), \
        "the Greenway should meet the northern neighbour at the seam"


def test_south_edge_shows_the_wood_barrier(game):
    """The cut-off south is a soft land border, painted as a dense wood (#15)."""
    _, gw, _ = game
    # (2,4) has no southern neighbour: the diegetic wood stands along the bottom.
    marsh = _surface(gw, (2, 4))
    south_row = marsh.height - 1
    trees = sum(1 for x in range(marsh.width)
                if marsh.tiles[x, south_row] == tile_types.tree)
    assert trees > 6, "no diegetic wood along the cut-off south edge"


def test_cluster_region_round_trips_through_save_load(game, tmp_path):
    engine, gw, player = game
    gw.teleport_to((1, 4))                     # jump to Tharbad
    assert gw.coord == (1, 4)
    path = tmp_path / "cluster.sav"
    savegame.save_game(engine, str(path))
    after = savegame.load_game(str(path))
    assert after.game_world.coord == (1, 4)
    assert (1, 4) in after.game_world.regions
    assert after.game_world.current_region.level(0) is not None
