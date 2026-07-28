"""Cluster 5 — The North-East marches (Dark) (issue #20): the bleak fells running
north-east toward Angmar — Mt Gram's orc-hold and the troll-fells of the
Ettenmoors, broken highland darkening toward the shadow.

The registry infra (ADR 0003) already makes every cell enterable with generic
placeholder terrain; this cluster gives its named anchors **lore-appropriate,
recognizable** terrain composed from the terrain toolkit (`procgen`), while
keeping the cluster's Definition of Done: every cell enterable from all present
neighbours, the meanest (Dark/Perilous) band beasts, diegetic wood/mountain
barriers on the cut-off north and east edges, and save/load round-trips. (The
East-Road corridor cells on the y=-1 row belong to Cluster 3; the Mt Gram deeps
are a plan marker dug in a later pass — out of scope here.)
"""
from __future__ import annotations

import pytest

from lonelands import (
    content, overworld, procgen, savegame, setup_game, tile_types, world,
)
from lonelands.dice import set_seed

# The cluster box: x +4..+6, y -4..-1 (the Dark band north-east).
CLUSTER = [c for c in overworld.GRID if 4 <= c[0] <= 6 and -4 <= c[1] <= -1]
# The named anchors this cluster authors (the y=-1 corridor is Cluster 3's).
ANCHORS = {
    (4, -4): "Mt Gram",
    (5, -4): "Ettenmoors",
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

def test_mt_gram_is_a_broken_orc_hold(game):
    _, gw, _ = game
    gram = _surface(gw, (4, -4))
    assert _count(gram, tile_types.hill) > 150, "the broken highland should read as rock"
    assert _count(gram, tile_types.building_wall) > 0, "no orc-stockade of piled stone"
    assert _count(gram, tile_types.rubble) > 40, "no fallen stone about the delving"


def test_ettenmoors_is_a_fell_of_tors_and_tarns(game):
    _, gw, _ = game
    moors = _surface(gw, (5, -4))
    assert _count(moors, tile_types.hill) > 150, "the troll-fells should read as tors"
    assert _count(moors, tile_types.water) > 15, "no boggy tarns in the hollows"


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


def test_dark_anchor_crawls_with_the_meanest_beasts(game):
    _, gw, player = game
    # Mt Gram is Dark — the meanest table of the build. The shared model ties
    # count to band danger, so it fields at least the band's low bound of threats.
    gram = _surface(gw, (4, -4))
    (lo, _), _ = content.BAND_THREATS["Dark"]
    beasts = sum(1 for a in gram.actors if a is not player)
    assert beasts >= lo


def test_east_edge_shows_the_mountain_wall_barrier(game):
    """The cut-off east is the Misty-Mountain wall, painted diegetically (#15)."""
    _, gw, _ = game
    # (6,-3) has no eastern neighbour: the wall (diegetic Mountain = hills) stands.
    marches = _surface(gw, (6, -3))
    east_col = marches.width - 1
    hills = sum(1 for y in range(marches.height)
                if marches.tiles[east_col, y] == tile_types.hill)
    assert hills > 6, "no diegetic mountain wall along the cut-off east edge"


def test_cluster_region_round_trips_through_save_load(game, tmp_path):
    engine, gw, player = game
    gw.teleport_to((4, -4))                   # jump to Mt Gram
    assert gw.coord == (4, -4)
    path = tmp_path / "cluster.sav"
    savegame.save_game(engine, str(path))
    after = savegame.load_game(str(path))
    assert after.game_world.coord == (4, -4)
    assert (4, -4) in after.game_world.regions
    assert after.game_world.current_region.level(0) is not None
