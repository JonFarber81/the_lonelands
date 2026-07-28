"""Cluster 4 — The North (Arnor ruins) (issue #19): the ruined north above the
Road — the drowned royal city of Annúminas on Lake Nenuial, wight-haunted
Fornost on the North Downs, and the high North Downs on the northern rim.

The registry infra (ADR 0003) already makes every cell enterable with generic
placeholder terrain; this cluster gives its named anchors **lore-appropriate,
recognizable** terrain composed from the terrain toolkit (`procgen`), while
keeping the cluster's Definition of Done: every cell enterable from all present
neighbours, band-appropriate wandering beasts, the soft wood border on the
cut-off north edge, and save/load round-trips. (The Annúminas and Fornost deeps
are markers in the plan, dug in a later pass — out of scope here.)
"""
from __future__ import annotations

import pytest

from lonelands import (
    content, overworld, procgen, savegame, setup_game, tile_types, world,
)
from lonelands.dice import set_seed

# The cluster box: y -4..-2, west/centre (x .. +3; the NE marches are Cluster 5).
CLUSTER = [c for c in overworld.GRID if -4 <= c[1] <= -2 and c[0] <= 3]
# The named anchors this cluster authors.
ANCHORS = {
    (-3, -2): "Annúminas",
    (-1, -2): "Fornost",
    (1, -4): "North Downs",
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

def test_annuminas_is_a_drowned_ruin_on_the_lake(game):
    _, gw, _ = game
    city = _surface(gw, (-3, -2))
    assert _count(city, tile_types.water) > 400, "Lake Nenuial should flood the north"
    assert _count(city, tile_types.building_wall) > 60, "no broken royal stonework"
    assert _count(city, tile_types.rubble) > 40, "no fallen stone through the ruins"


def test_fornost_is_a_wight_haunted_ruin_on_the_downs(game):
    _, gw, _ = game
    norbury = _surface(gw, (-1, -2))
    assert _count(norbury, tile_types.building_wall) > 60, "no ruined keep and streets"
    assert _count(norbury, tile_types.rubble) > 40, "no fallen stone"
    assert _count(norbury, tile_types.hill) > 30, "the bare down-shoulder is missing"


def test_north_downs_is_high_rolling_hills(game):
    _, gw, _ = game
    downs = _surface(gw, (1, -4))
    assert _count(downs, tile_types.hill) > 150, "the high downs should read as hills"


def test_north_downs_shows_the_soft_wood_border_on_the_cut_off_north(game):
    """The cut-off north is a soft wood border, not an invisible wall (#15)."""
    _, gw, _ = game
    downs = _surface(gw, (1, -4))
    top = [int(downs.tiles["kind"][x, 0]) for x in range(downs.width)]
    # a ragged belt of trees (kind 0, but a wood belt) crowds the top edge; the
    # border is painted, so the whole edge is not open uniform grass.
    trees = sum(1 for x in range(downs.width)
                if downs.tiles[x, 0] == tile_types.tree)
    assert trees > 6, "no diegetic wood barrier along the cut-off north edge"


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


def test_wild_anchor_fields_wandering_beasts(game):
    _, gw, player = game
    # The North Downs is Wild — the shared model ties count to band danger, so it
    # must field at least the band's low bound of wandering threats.
    downs = _surface(gw, (1, -4))
    (lo, _), _ = content.BAND_THREATS["Wild"]
    beasts = sum(1 for a in downs.actors if a is not player)
    assert beasts >= lo


def test_cluster_region_round_trips_through_save_load(game, tmp_path):
    engine, gw, player = game
    gw.teleport_to((-3, -2))                  # jump to Annúminas
    assert gw.coord == (-3, -2)
    path = tmp_path / "cluster.sav"
    savegame.save_game(engine, str(path))
    after = savegame.load_game(str(path))
    assert after.game_world.coord == (-3, -2)
    assert (-3, -2) in after.game_world.regions
    assert after.game_world.current_region.level(0) is not None
