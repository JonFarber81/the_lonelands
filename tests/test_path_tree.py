"""The pure Path-tree layout & navigation used by the Phase 2 tree screen
(ADR 0011, #74). Placement and arrow-walking are engine-free, so they unit-test
without a display."""
from __future__ import annotations

from lonelands import path_tree, perks

LW = perks.PATHS_BY_ID["long_watch"]


def _by_id(placements):
    return {p.node.id: p for p in placements}


def test_trunk_sits_in_the_centre_column_stacked_by_order():
    placements = path_tree.layout(LW)
    at = _by_id(placements)
    # Both trunk nodes are in the centre column, stacked from the top.
    assert at["lw_endure"].col == path_tree.CENTER
    assert at["lw_wind"].col == path_tree.CENTER
    assert at["lw_endure"].row == 0
    assert at["lw_wind"].row == 1


def test_branches_fork_left_and_right_below_the_trunk():
    placements = path_tree.layout(LW)
    at = _by_id(placements)
    trunk_rows = [p.row for p in placements if p.col == path_tree.CENTER]
    fork_row = max(trunk_rows) + 1
    # First branch (warden) forks left; second (reaver) forks right; both begin
    # below the trunk.
    assert at["lw_soak"].col == path_tree.LEFT
    assert at["lw_hone"].col == path_tree.RIGHT
    assert at["lw_soak"].row == fork_row
    assert at["lw_hone"].row == fork_row


def test_every_node_is_placed_exactly_once():
    placements = path_tree.layout(LW)
    ids = [p.node.id for p in placements]
    assert sorted(ids) == sorted(n.id for n in LW.nodes)
    assert len(ids) == len(set(ids))


def test_walk_down_the_trunk_then_into_a_branch():
    placements = path_tree.layout(LW)
    # Down the trunk...
    assert path_tree.move(placements, "lw_endure", 0, 1) == "lw_wind"
    # ...off the last trunk node drops into the topmost branch node.
    nxt = path_tree.move(placements, "lw_wind", 0, 1)
    assert _by_id(placements)[nxt].row == 2  # first fork row


def test_walk_left_and_right_between_branches():
    placements = path_tree.layout(LW)
    # From the warden fork, right jumps to the reaver node at the same depth.
    assert path_tree.move(placements, "lw_soak", 1, 0) == "lw_hone"
    # ...and back left again.
    assert path_tree.move(placements, "lw_hone", -1, 0) == "lw_soak"


def test_walk_up_from_a_branch_top_returns_to_the_trunk():
    placements = path_tree.layout(LW)
    nxt = path_tree.move(placements, "lw_soak", 0, -1)
    assert nxt == "lw_wind"  # the bottom trunk node


def test_move_off_the_edge_stays_put():
    placements = path_tree.layout(LW)
    # Nothing above the first trunk node.
    assert path_tree.move(placements, "lw_endure", 0, -1) == "lw_endure"
    # Nothing left of the left branch.
    assert path_tree.move(placements, "lw_soak", -1, 0) == "lw_soak"
