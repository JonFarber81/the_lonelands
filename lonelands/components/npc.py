from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Dict

from lonelands.components.base_component import BaseComponent

if TYPE_CHECKING:
    from lonelands.entity import Actor


class NPC(BaseComponent):
    """A speaking, non-combatant character. Dialog is a node graph (see
    lonelands/dialog.py). Nodes and options may carry callables that read/mutate
    engine state (quests, inventory, hope)."""

    parent: "Actor"

    def __init__(self, title: str, tree: Dict[str, Any], start: str = "root",
                 keep_tree: bool = False):
        self.title = title
        self.tree = tree
        self.start = start
        # Authored NPCs drop their tree on save (it holds lambdas) and are
        # rehydrated by name. A *generated* wandering Bystander has no authored
        # twin to rehydrate from, but its tree is a single self-contained text
        # node with no lambdas — so it pickles cleanly and we keep it instead.
        self.keep_tree = keep_tree

    def __getstate__(self) -> Dict[str, Any]:
        """Drop the dialog tree — it is full of lambdas and is static content.
        savegame._rehydrate restores it by the speaker's name on load. A tree
        flagged `keep_tree` (a generated patron's) is lambda-free and kept."""
        state = self.__dict__.copy()
        if not getattr(self, "keep_tree", False):
            state["tree"] = None
        return state

    def __deepcopy__(self, memo: Dict[int, Any]) -> "NPC":
        """Preserve the dialog tree when an NPC is cloned (Entity.spawn).

        deepcopy would otherwise route through __getstate__ and drop the tree —
        that dropping is only wanted for *pickling* (saves), where _rehydrate
        restores it by name. A spawned NPC has no such rehydrate, so we keep the
        tree, shared by reference: it is static content and its lambdas must not
        be copied."""
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        for key, value in self.__dict__.items():
            setattr(new, key, self.tree if key == "tree" else copy.deepcopy(value, memo))
        return new
