"""Pure layout & navigation for a Path's tree (ADR 0011, Phase 2 — #74).

The Phase 2 tree screen draws a Path as a shared **trunk** at the top forking
into two **branches** with tiers descending. That geometry — where each node
sits and which node an arrow-key press moves to — is engine-free and lives here
so it can be reasoned about and unit-tested without a display; the handler in
:mod:`lonelands.input_handlers` turns a :class:`Placement`'s ``col``/``row`` into
pixels and paints the boxes.

Layout
------
Three columns — ``LEFT`` / ``CENTER`` / ``RIGHT``. Trunk nodes stack down the
centre from the top; the two branches (in the Path's declared branch order) fork
**left** and **right**, their nodes stacking below the trunk in declaration
order (which already runs shallow tiers first). A cell is one node; nothing
overlaps.

Navigation
----------
:func:`move` walks between placed nodes: vertical steps run within a column;
stepping down off the last trunk node drops into the topmost branch node, and
stepping up off a branch's top climbs back to the bottom of the trunk. Horizontal
steps cross to the neighbouring column at the nearest depth. Moves off an edge
stay put (the caller sees the same node id back).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from lonelands import perks

# Column lanes, left to right.
LEFT = 0
CENTER = 1
RIGHT = 2


@dataclass(frozen=True)
class Placement:
    node: "perks.Node"
    col: int
    row: int


def layout(path: "perks.Path") -> List[Placement]:
    """Place every node of ``path``: trunk down the centre, the two branches
    forking left and right below it. Returns placements in a stable order —
    trunk first, then the left branch, then the right — each tagged with its
    ``col`` and ``row``."""
    trunk = [n for n in path.nodes if n.branch == "trunk"]
    branch_ids = list(path.branches.keys())
    left_id = branch_ids[0] if branch_ids else None
    right_id = branch_ids[1] if len(branch_ids) > 1 else None

    placements: List[Placement] = []
    for row, node in enumerate(trunk):
        placements.append(Placement(node, CENTER, row))

    fork_row = len(trunk)
    for col, bid in ((LEFT, left_id), (RIGHT, right_id)):
        if bid is None:
            continue
        row = fork_row
        for node in path.nodes:
            if node.branch == bid:
                placements.append(Placement(node, col, row))
                row += 1
    return placements


def move(placements: List[Placement], current_id: str, dx: int, dy: int) -> str:
    """The node id reached by stepping ``(dx, dy)`` from ``current_id`` across the
    placed tree. Off-edge steps return ``current_id`` unchanged."""
    at = {p.node.id: p for p in placements}
    cur = at.get(current_id)
    if cur is None:
        return current_id

    if dy != 0:
        nxt = _vertical(placements, cur, dy)
    elif dx != 0:
        nxt = _horizontal(placements, cur, dx)
    else:
        nxt = None
    return nxt.node.id if nxt is not None else current_id


def _vertical(placements: List[Placement], cur: Placement, dy: int) -> Optional[Placement]:
    same_col = [p for p in placements if p.col == cur.col]
    # Nearest node in the same column in the direction of travel.
    ahead = [p for p in same_col if (p.row - cur.row) * dy > 0]
    if ahead:
        return min(ahead, key=lambda p: abs(p.row - cur.row))
    # Leaving the column: trunk <-> branches.
    branches = [p for p in placements if p.col in (LEFT, RIGHT)]
    trunk = [p for p in placements if p.col == CENTER]
    if dy > 0 and cur.col == CENTER and branches:
        # Off the bottom of the trunk into the topmost branch node.
        return min(branches, key=lambda p: (p.row, p.col))
    if dy < 0 and cur.col in (LEFT, RIGHT) and trunk:
        # Off the top of a branch back to the bottom of the trunk.
        return max(trunk, key=lambda p: p.row)
    return None


def _horizontal(placements: List[Placement], cur: Placement, dx: int) -> Optional[Placement]:
    # The nearest node anywhere to the side of travel, preferring the same depth
    # (so a branch step crosses straight to its opposite number, skipping the
    # empty trunk lane below the fork).
    side = [p for p in placements if (p.col - cur.col) * dx > 0]
    if not side:
        return None
    return min(side, key=lambda p: (abs(p.row - cur.row), abs(p.col - cur.col)))
