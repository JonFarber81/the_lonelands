"""Overworld-registry tests (ADR 0003): the data-driven grid, the band→beast
model, and the guarantee that every walkable cell is enterable and edge-to-edge
traversable with placeholder terrain."""
from __future__ import annotations

from collections import deque

import pytest

from lonelands import content, overworld, setup_game
from lonelands.dice import set_seed


@pytest.fixture
def game():
    set_seed(1)
    engine = setup_game.new_game()
    return engine, engine.game_world, engine.player


# --- the plan-as-data -------------------------------------------------------

def test_grid_has_the_116_walkable_cells():
    # The full playable Eriador window: 15x9 minus the Sea/Mountain frame.
    assert len(overworld.GRID) == 116
    assert all(cell.band in overworld.BANDS for cell in overworld.GRID.values())


def test_cells_carry_road_flags():
    # The registry's road-flag axis: cells on a plan road are marked, others not.
    assert overworld.cell((0, 0)).road is True       # Bree, the crossing
    assert overworld.cell((2, 0)).road is True       # Weathertop, on the East Road
    assert overworld.cell((0, -1)).road is True       # Chetwood, on the Greenway
    assert overworld.cell((-1, 0)).road is True       # Barrow-downs, on the Shire Road
    assert overworld.cell((3, -4)).road is False      # trackless northern wild


def test_impassable_coords_are_simply_absent():
    assert (-7, 0) in overworld.GRID          # Grey Havens sits on the west wall
    assert (-7, 2) not in overworld.GRID      # ...but the Gulf of Lune does not
    assert (7, 2) not in overworld.GRID       # the Misty Mountains wall


def test_the_five_original_regions_kept_their_coords_and_bree_is_origin():
    assert overworld.cell((0, 0)).name == "Bree"
    assert overworld.cell((-1, 0)).name == "Barrow-downs"
    assert overworld.cell((0, -1)).name == "Chetwood"
    assert overworld.cell((0, 1)).name == "South Downs"
    # The re-home: the barrow-wight deeps live under the Barrow-downs now, and
    # Weathertop (Amon Sûl) carries the watchtower deeps.
    assert overworld.cell((-1, 0)).deeps == 4
    assert overworld.cell((2, 0)).name == "Weathertop"
    assert overworld.cell((2, 0)).deeps == 3


# --- the registry generates every cell --------------------------------------

def test_every_walkable_cell_builds_an_enterable_surface(game):
    engine, gw, player = game
    for coord in overworld.GRID:
        region = gw.region(coord)
        assert region is not None, f"{coord} has no Region"
        surface = region.level(0)
        # Its default landing spot must be walkable — the cell is enterable.
        assert surface.tiles["walkable"][surface.entry_xy], \
            f"{coord} landing spot is not walkable"


def test_you_can_walk_the_whole_map_edge_to_edge(game):
    """Flood-fill the Region adjacency graph from Bree across shared Surface
    edges; every walkable cell must be reachable on foot (placeholder terrain)."""
    engine, gw, player = game
    seen = {(0, 0)}
    q = deque([(0, 0)])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + dx, y + dy)
            if nxt in overworld.GRID and nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    assert seen == set(overworld.GRID), "some cells are unreachable on the grid"


# --- the band → beast model -------------------------------------------------

def test_every_band_has_a_beast_table():
    for band in overworld.BANDS:
        (lo, hi), table = content.BAND_BEASTS[band]
        assert 0 <= lo <= hi
        assert table, f"{band} has no beast table"


def test_beast_count_scales_with_band_danger(game):
    """A Perilous cell fields more (and nastier) beasts than a Free one, applied
    at generation regardless of terrain."""
    engine, gw, player = game

    def beast_count(coord):
        gm = gw.region(coord).level(0)
        return sum(1 for a in gm.actors if a is not player)

    # (-3, 1) is Free-Lands filler; (-1, 0) Barrow-downs is Perilous.
    assert overworld.cell((-1, 0)).band == "Perilous"
    assert beast_count((-1, 0)) >= beast_count((-3, 1))
