"""The pure Path-tree layout & navigation used by the tree screen (ADR 0011,
#74; fractional tidy-tree from the #77 redesign). Placement and arrow-walking are
engine-free, so they unit-test without a display."""
from __future__ import annotations

from lonelands import path_tree, perks

LW = perks.PATHS_BY_ID["long_watch"]
HP = perks.PATHS_BY_ID["hidden_path"]


def _by_id(placements):
    return {p.node.id: p for p in placements}


def test_every_node_is_placed_exactly_once():
    for path in perks.PATHS:
        placements = path_tree.layout(path)
        ids = [p.node.id for p in placements]
        assert sorted(ids) == sorted(n.id for n in path.nodes)
        assert len(ids) == len(set(ids))


def test_the_root_sits_at_the_top_centre():
    at = _by_id(path_tree.layout(HP))
    assert at["hp_stealth"].row == 0
    assert at["hp_stealth"].x == path_tree.CENTER


def test_children_fork_below_their_parent_into_left_and_right_slots():
    at = _by_id(path_tree.layout(HP))
    # Silent Tread forks into Ambush (left half) and Evasion (right half), one row
    # down, each centred in its slot.
    assert at["hp_ambush"].row == at["hp_evasion"].row == 1
    assert at["hp_ambush"].x < path_tree.CENTER < at["hp_evasion"].x


def test_a_forked_pair_splits_its_parents_slot_side_by_side():
    at = _by_id(path_tree.layout(HP))
    # Ambush's two children share a row, on opposite sides of Ambush's own x.
    assert at["hp_shadowstep"].row == at["hp_poison"].row
    assert at["hp_shadowstep"].x < at["hp_ambush"].x < at["hp_poison"].x


def test_a_lone_chain_drops_straight_down_one_column():
    at = _by_id(path_tree.layout(HP))
    # The Trapper branch is a single chain — every node shares one x, descending.
    chain = ["hp_evasion", "hp_snare", "hp_pinning", "hp_disengage", "hp_vanish"]
    xs = {at[i].x for i in chain}
    assert len(xs) == 1
    rows = [at[i].row for i in chain]
    assert rows == sorted(rows) and len(set(rows)) == len(rows)


def test_depth_packed_rows_let_capstones_float():
    at = _by_id(path_tree.layout(HP))
    # The two branches are unequal length: the capstones end on different rows.
    assert at["hp_deathblow"].row != at["hp_vanish"].row


def test_extra_childless_trunk_roots_stack_as_a_centre_stem():
    at = _by_id(path_tree.layout(LW))
    # Long Watch has two parentless trunk roots; the childless one stems above the
    # branching one, both on the centre line.
    assert at["lw_wind"].x == at["lw_endure"].x == path_tree.CENTER
    assert at["lw_wind"].row < at["lw_endure"].row


def test_walk_down_from_the_root_enters_a_branch():
    placements = path_tree.layout(HP)
    nxt = path_tree.move(placements, "hp_stealth", 0, 1)
    assert _by_id(placements)[nxt].row == 1  # one of the fork children


def test_walk_left_and_right_between_the_forks():
    placements = path_tree.layout(HP)
    assert path_tree.move(placements, "hp_ambush", 1, 0) == "hp_evasion"
    assert path_tree.move(placements, "hp_evasion", -1, 0) == "hp_ambush"


def test_walk_down_a_chain_step_by_step():
    placements = path_tree.layout(HP)
    assert path_tree.move(placements, "hp_snare", 0, 1) == "hp_pinning"
    assert path_tree.move(placements, "hp_pinning", 0, 1) == "hp_disengage"


def test_move_off_the_edge_stays_put():
    placements = path_tree.layout(HP)
    assert path_tree.move(placements, "hp_stealth", 0, -1) == "hp_stealth"
    assert path_tree.move(placements, "hp_vanish", 0, 1) == "hp_vanish"
