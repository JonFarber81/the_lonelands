from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from lonelands.components.base_component import BaseComponent

if TYPE_CHECKING:
    from lonelands.entity import Actor


class NPC(BaseComponent):
    """A speaking, non-combatant character. Dialog is a node graph (see
    lonelands/dialog.py). Nodes and options may carry callables that read/mutate
    engine state (quests, inventory, hope)."""

    parent: "Actor"

    def __init__(self, title: str, tree: Dict[str, Any], start: str = "root"):
        self.title = title
        self.tree = tree
        self.start = start
