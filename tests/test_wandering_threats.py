"""Wandering-threats model (ADR 0007): the three-kind band blend and the road
safety buffer. Every band is a *blend* of Brigand/Wild-animal/Monster kinds, and
`procgen.apply_band_threats` keeps animals and monsters clear of a radius-4 buffer
around road tiles while biasing brigands *toward* the road."""
from __future__ import annotations

import pytest

from lonelands import content, overworld, procgen, setup_game, tile_types
from lonelands.dice import set_seed
from lonelands.game_map import GameMap


@pytest.fixture
def engine():
    set_seed(1)
    return setup_game.new_game()


def _blank(engine) -> GameMap:
    gm = GameMap(engine, procgen.MAP_WIDTH, procgen.MAP_HEIGHT, outdoors=True)
    gm.tiles[:] = tile_types.grass
    return gm


def _names(kind) -> set:
    return {tmpl.name for tmpl, _ in content.BAND_MEMBERS[kind]}


BRIGAND_NAMES = _names(content.BRIGAND)
ANIMAL_NAMES = _names(content.WILD_ANIMAL)
MONSTER_NAMES = _names(content.MONSTER)


def _seed_many(engine, band: str, trials: int, *, road: bool = False):
    """Run `apply_band_threats` `trials` times on fresh maps, optionally with a
    horizontal road, and yield the (map, threat) pairs seeded."""
    for _ in range(trials):
        gm = _blank(engine)
        if road:
            gm.tiles[:, procgen.ROAD_ROW] = tile_types.road
        procgen.apply_band_threats(gm, band)
        for a in gm.actors:
            yield gm, a


def _min_road_dist(gm: GameMap, x: int, y: int) -> int:
    roads = [(rx, ry) for rx in range(gm.width) for ry in range(gm.height)
             if int(gm.tiles["kind"][rx, ry]) == tile_types.KIND_ROAD]
    return min(max(abs(x - rx), abs(y - ry)) for rx, ry in roads)


# --- the blend: which kinds each band spawns --------------------------------

def test_free_band_never_spawns_monsters(engine):
    # Free is animals-mostly with a rare lone footpad; a spider on Bree's
    # doorstep is exactly the bug ADR 0007 fixes.
    names = {a.name for _, a in _seed_many(engine, overworld.FREE, 400)}
    assert not (names & MONSTER_NAMES), f"monsters in Free band: {names & MONSTER_NAMES}"
    assert names & ANIMAL_NAMES, "Free band seeded no wild animals at all"


def test_free_band_brigands_are_footpads_only(engine):
    # Settled Free country sees only the weak lone footpad, never the highwayman
    # of the open road (ADR 0007).
    names = {a.name for _, a in _seed_many(engine, overworld.FREE, 600)}
    brigands = names & BRIGAND_NAMES
    assert brigands, "Free band never seeded a brigand at all over 600 trials"
    assert brigands == {"footpad"}, f"non-footpad brigand in Free: {brigands}"


def test_wild_band_monsters_are_rare_not_dominant(engine):
    # Wild is brigands + animals dominant, monsters ~10%.
    threats = [a for _, a in _seed_many(engine, overworld.WILD, 500)]
    total = len(threats)
    monsters = sum(1 for a in threats if a.name in MONSTER_NAMES)
    brigands = sum(1 for a in threats if a.name in BRIGAND_NAMES)
    assert total > 0
    assert monsters / total < 0.25, f"monsters not rare in Wild: {monsters}/{total}"
    assert brigands > monsters, "brigands should outnumber monsters in the Wild"


def test_dark_band_has_no_brigands(engine):
    # Brigands belong to settled land; the Dark is monster country.
    names = {a.name for _, a in _seed_many(engine, overworld.DARK, 300)}
    assert not (names & BRIGAND_NAMES), f"brigands in Dark band: {names & BRIGAND_NAMES}"
    assert names & MONSTER_NAMES, "Dark band seeded no monsters"


def test_perilous_band_is_monsters_only(engine):
    names = {a.name for _, a in _seed_many(engine, overworld.PERILOUS, 300)}
    assert names and names <= MONSTER_NAMES, f"non-monsters in Perilous: {names - MONSTER_NAMES}"


# --- the road safety buffer -------------------------------------------------

def test_animals_and_monsters_keep_clear_of_the_road_buffer(engine):
    # Across every band, no wild animal or monster may spawn within the buffer.
    for band in (overworld.WILD, overworld.DARK, overworld.PERILOUS):
        for gm, a in _seed_many(engine, band, 200, road=True):
            if a.name in ANIMAL_NAMES or a.name in MONSTER_NAMES:
                dist = _min_road_dist(gm, a.x, a.y)
                assert dist > procgen.ROAD_BUFFER, \
                    f"{band}: {a.name} spawned {dist} tiles from the road (buffer " \
                    f"{procgen.ROAD_BUFFER})"


def test_brigands_ignore_the_buffer_and_favour_the_road(engine):
    # Brigands are the exception: they may spawn inside the buffer, and are
    # biased toward it.
    inside = outside = 0
    for gm, a in _seed_many(engine, overworld.WILD, 400, road=True):
        if a.name in BRIGAND_NAMES:
            if _min_road_dist(gm, a.x, a.y) <= procgen.ROAD_BUFFER:
                inside += 1
            else:
                outside += 1
    assert inside > 0, "brigands never appeared near the road — bias is broken"
    assert inside > outside, \
        f"brigands not road-biased: {inside} near vs {outside} away"
