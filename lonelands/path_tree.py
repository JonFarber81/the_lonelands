"""Pure layout & navigation for a Path's tree (ADR 0011, Phase 2 — #74).

The tree screen draws a Path as a **tidy tree**: the shared root at the top
centre, forking down into its branches, a child always directly below (or
elbowed cleanly off) its parent. That geometry — where each node sits and which
node an arrow-key press moves to — is engine-free and lives here so it can be
reasoned about and unit-tested without a display; the handler in
:mod:`lonelands.input_handlers` turns a :class:`Placement`'s ``x``/``row`` into
pixels, draws orthogonal prereq connectors, and paints the cards.

Layout
------
Geometry follows the **parent graph**, not the ``branch`` tag: a node's children
(the nodes naming it as ``parent``) fork below it, each child subtree owning an
equal horizontal *slot* of its parent's slot and centred within it. So a lone
chain (Trapper) drops straight down one column, while a node with two children
(Ambush → Shadowstep + Poisoned Blade) splits its slot in half and forks. ``x``
is a fraction in ``[0, 1]`` across the tree's width; ``row`` is depth-packed
(child row = parent row + 1), so lanes are as short as the data allows and
capstones simply float at the bottom of their own branch.

A Path may declare **more than one trunk root** (a parentless node — e.g. the
Long Watch's Steady Endurance *and* Second Wind). The childless roots stack as a
centre **stem** above the single branching root, which then forks below them.

Navigation
----------
:func:`move` walks between placed nodes spatially: a step picks the nearest node
in the direction of travel — vertical steps prefer the nearest row then the
nearest column, horizontal steps the nearest column at the nearest row. Moves off
an edge stay put (the caller sees the same node id back).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

from lonelands import perks

# Horizontal centre of the tree, in the ``x`` fraction space below.
CENTER = 0.5


@dataclass(frozen=True)
class Placement:
    node: "perks.Node"
    x: float   # centre of the node's card, a fraction in [0, 1] across the tree
    row: int   # depth from the top (0 = the root row)


def layout(path: "perks.Path") -> List[Placement]:
    """Place every node of ``path`` as a tidy tree: the branching root centred at
    the top, its children forking below into equal horizontal slots, depth-packed.
    Extra childless trunk roots stack as a centre stem above it. Returns placements
    in a stable order (stem roots first, then the subtree pre-order), each tagged
    with its ``x`` fraction and ``row``."""
    children: Dict[Optional[str], List["perks.Node"]] = defaultdict(list)
    for node in path.nodes:
        children[node.parent].append(node)

    roots = children[None]
    branching = [r for r in roots if children[r.id]]
    childless = [r for r in roots if not children[r.id]]
    # The stem: childless trunk roots on top, the (single) branching root last so
    # its fork drops into open space below the stem rather than through a sibling.
    stem = childless + branching

    placements: List[Placement] = []
    row = 0
    for r in stem[:-1]:
        placements.append(Placement(r, CENTER, row))
        row += 1
    if stem:
        _place_subtree(stem[-1], 0.0, 1.0, row, children, placements)
    return placements


def _place_subtree(node: "perks.Node", x0: float, x1: float, row: int,
                   children: Dict[Optional[str], List["perks.Node"]],
                   out: List[Placement]) -> None:
    """Centre ``node`` in the slot ``[x0, x1]`` at ``row``, then split the slot
    evenly among its children and recurse one row down."""
    out.append(Placement(node, (x0 + x1) / 2, row))
    kids = children[node.id]
    if not kids:
        return
    span = (x1 - x0) / len(kids)
    for i, kid in enumerate(kids):
        _place_subtree(kid, x0 + i * span, x0 + (i + 1) * span, row + 1, children, out)


def move(placements: List[Placement], current_id: str, dx: int, dy: int) -> str:
    """The node id reached by stepping ``(dx, dy)`` from ``current_id`` across the
    placed tree, picking the nearest node in the direction of travel. Off-edge
    steps return ``current_id`` unchanged."""
    at = {p.node.id: p for p in placements}
    cur = at.get(current_id)
    if cur is None:
        return current_id

    if dy != 0:
        ahead = [p for p in placements if (p.row - cur.row) * dy > 0]
    elif dx != 0:
        ahead = [p for p in placements if (p.x - cur.x) * dx > 0]
    else:
        return current_id
    if not ahead:
        return current_id
    # Both axes rank by nearest row, then nearest column — so a vertical step lands
    # on the closest node straight below/above, and a horizontal step crosses to
    # the nearest node on (or nearest to) the same row.
    nxt = min(ahead, key=lambda p: (abs(p.row - cur.row), abs(p.x - cur.x)))
    return nxt.node.id
