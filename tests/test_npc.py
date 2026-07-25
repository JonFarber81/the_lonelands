"""NPC dialog survival across cloning and saving.

Spawning an NPC deep-copies it (Entity.spawn); saving pickles it. The dialog
tree is full of lambdas: it must survive the *clone* (there is no rehydrate
after spawn) but be dropped on *pickle* (lambdas aren't picklable; savegame
restores it by name on load). Regression test for the "tree is None → talking
crashes" bug.
"""
from __future__ import annotations

import copy
import pickle

from lonelands import setup_game, story


def test_spawned_town_npcs_keep_their_dialog_tree():
    engine = setup_game.new_game()
    speakers = [e for e in engine.game_map.entities if getattr(e, "npc", None)]
    assert speakers, "expected town NPCs in the starting Region"
    for actor in speakers:
        assert actor.npc.tree, f"{actor.name} lost its dialog tree when spawned"
        # the entry node must resolve — this is exactly what DialogHandler does.
        assert actor.npc.start in actor.npc.tree


def test_deepcopy_preserves_tree_but_pickle_drops_it():
    npc = story.make_innkeeper().npc
    assert copy.deepcopy(npc).tree is npc.tree      # clone keeps the static tree
    assert pickle.loads(pickle.dumps(npc)).tree is None  # save drops it (rehydrated on load)
