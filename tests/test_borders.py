"""Diegetic-border tests (Infra D, issue #15): the per-edge barrier model
(`overworld.border_edges`) and the tile pass (`procgen.diegetic_borders`) that
paints it, so no edge of the playable map reads as an invisible wall — hard
walls for the Sea/Mountain frame, soft wood for the cut-off land borders, and a
visible pass where a Gateway Region fronts the wall."""
from __future__ import annotations

import pytest

from lonelands import overworld, procgen, setup_game, tile_types
from lonelands.dice import set_seed


@pytest.fixture
def game():
    set_seed(1)
    engine = setup_game.new_game()
    return engine, engine.game_world, engine.player


# --- the per-edge model -----------------------------------------------------

def test_the_frame_classifies_sea_mountain_and_soft_land():
    # West wall and SW gulf are the Sea; the east wall is the Mountains; every
    # other missing neighbour is a cut-off land border (soft wood).
    assert overworld._frame((-8, 0)) == overworld.SEA        # off the west wall
    assert overworld._frame((-6, 2)) == overworld.SEA        # the Gulf of Lune (SW)
    assert overworld._frame((7, 1)) == overworld.MOUNTAIN    # the Misty-Mountain wall
    assert overworld._frame((8, 0)) == overworld.MOUNTAIN    # far east, past the wall's gap
    assert overworld._frame((6, 4)) == overworld.MOUNTAIN    # the wall's southern foot
    assert overworld._frame((0, -5)) == overworld.WOOD       # off the north edge
    assert overworld._frame((0, 5)) == overworld.WOOD        # off the south edge


def test_wall_and_water_cells_border_their_frame():
    assert overworld.border_edges((-7, 0))["w"] == overworld.SEA       # Grey Havens on the Sea
    assert overworld.border_edges((-6, 1))["s"] == overworld.SEA       # the Gulf of Lune, south
    assert overworld.border_edges((6, 1))["e"] == overworld.MOUNTAIN   # the eastern wall
    assert overworld.border_edges((0, -4))["n"] == overworld.WOOD      # the northern land edge
    assert overworld.border_edges((0, 4))["s"] == overworld.WOOD       # the southern land edge


def test_gateway_in_the_wall_reads_as_a_gate_not_a_wall():
    # The named gateways cross the Misty-Mountain wall *eastward*; that edge is a
    # crossing, not masonry (issue #15). Their other wall edges stay walled — the
    # range simply runs on. Moria's gate is vertical (its deeps), so it has no
    # closed wall edge to paint.
    assert overworld.border_edges((6, 2))["e"] == overworld.GATE       # Redhorn Pass, east
    assert overworld.border_edges((7, -1))["e"] == overworld.GATE      # Fords of Bruinen, east
    # ...but the Fords' *north* edge is just the wall carrying on, not a second pass.
    assert overworld.border_edges((7, -1))["n"] == overworld.MOUNTAIN
    # Moria West-gate (5,3) is ringed by real neighbours — nothing to wall or gate.
    assert overworld.border_edges((5, 3)) == {}


def test_an_interior_cell_has_no_closed_edges():
    # Bree and its ring of neighbours are all real Regions — nothing to border.
    assert overworld.border_edges((0, 0)) == {}


def test_every_closed_edge_is_classified_exactly_once():
    kinds = {overworld.SEA, overworld.MOUNTAIN, overworld.WOOD, overworld.GATE}
    for coord in overworld.GRID:
        edges = overworld.border_edges(coord)
        for edge, kind in edges.items():
            # a closed edge really has no neighbour, and gets one valid kind
            dx, dy = overworld.EDGE_DELTA[edge]
            nb = (coord[0] + dx, coord[1] + dy)
            assert nb not in overworld.GRID, f"{coord}-{edge} borders real {nb}"
            assert kind in kinds


# --- the tile pass ----------------------------------------------------------

def _edge_line(gm, edge):
    if edge in ("e", "w"):
        col = gm.width - 1 if edge == "e" else 0
        return [(col, y) for y in range(gm.height)]
    row = gm.height - 1 if edge == "s" else 0
    return [(x, row) for x in range(gm.width)]


def _count_kind(gm, cells, kind):
    return sum(1 for x, y in cells if int(gm.tiles["kind"][x, y]) == kind)


def _count_glyph(gm, cells, tile):
    ch = tile["light"]["ch"]
    return sum(1 for x, y in cells if gm.tiles["light"][x, y]["ch"] == ch)


def test_west_wall_paints_open_water(game):
    engine, gw, player = game
    gm = gw.region((-7, 0)).level(0)                  # Grey Havens, on the Sea
    assert _count_kind(gm, _edge_line(gm, "w"), tile_types.KIND_WATER) >= 5


def test_east_wall_paints_a_mountain_ridge(game):
    engine, gw, player = game
    gm = gw.region((6, 1)).level(0)                   # against the Misty-Mountain wall
    assert _count_glyph(gm, _edge_line(gm, "e"), tile_types.hill) >= 5


def test_soft_land_border_is_dense_wood_not_a_wall(game):
    engine, gw, player = game
    gm = gw.region((0, -4)).level(0)                  # the northern land edge
    north = _edge_line(gm, "n")
    assert _count_glyph(gm, north, tile_types.tree) >= 5     # a dense wood
    # ...and it is wood, not the Mountain-wall's stone ridge.
    assert _count_glyph(gm, north, tile_types.hill) == 0


def test_gateway_wall_has_a_visible_pass_through_the_ridge(game):
    engine, gw, player = game
    gm = gw.region((6, 2)).level(0)                   # Redhorn Pass, at the wall
    east = _edge_line(gm, "e")
    assert _count_glyph(gm, east, tile_types.hill) >= 5      # the ridge is there...
    assert _count_kind(gm, east, tile_types.KIND_ROAD) >= 1  # ...but a pass cuts through it


def test_no_closed_edge_reads_as_an_invisible_wall(game):
    """The Done-when: every closed edge of every walkable cell shows a visible
    cause — water, mountain, wood, or a gateway pass — never bare open ground."""
    engine, gw, player = game
    for coord, edges in (
        (c, overworld.border_edges(c)) for c in overworld.GRID
    ):
        if not edges:
            continue
        gm = gw.region(coord).level(0)
        for edge in edges:
            line = _edge_line(gm, edge)
            visible = _count_kind(gm, line, tile_types.KIND_WATER) \
                + _count_kind(gm, line, tile_types.KIND_ROAD) \
                + _count_glyph(gm, line, tile_types.hill) \
                + _count_glyph(gm, line, tile_types.tree)
            assert visible >= 3, \
                f"{coord}-{edge} reads as an invisible wall (only {visible} barrier tiles)"
