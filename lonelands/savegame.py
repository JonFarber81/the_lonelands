"""Single-slot save/continue.

The game state is one object graph hanging off the `Engine`, so a save is just
a pickled Engine, compressed with lzma. Two things make that graph not-quite
picklable on its own, and both are pure *content* that the code can rebuild:

  * lambdas — the world's Region factories (`world.py`), each Region's level
    builders, `Quest.on_complete`, and every NPC's dialog `tree` (`story/`).
  * transient UI state — `Engine.event_handler`, `Engine.last_roll`.

Each of those classes drops its lambdas in `__getstate__` (see the respective
modules), so the pickle succeeds. On load we walk the restored graph once and
re-attach the callables from freshly-built content — matching regions by coord,
quests by id, and NPCs by name. Nothing dynamic (positions, explored tiles,
slain foes, quest progress, inventory) is reconstructed; only the code-defined
behaviour is grafted back on.
"""
from __future__ import annotations

import lzma
import os
import pickle
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from lonelands.engine import Engine

# One slot, beside the package so it travels with an install.
SAVE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "savegame.sav")


def has_save() -> bool:
    return os.path.exists(SAVE_PATH)


def delete_save() -> None:
    try:
        os.remove(SAVE_PATH)
    except FileNotFoundError:
        pass


def save_game(engine: "Engine", path: str = SAVE_PATH) -> None:
    data = lzma.compress(pickle.dumps(engine))
    with open(path, "wb") as f:
        f.write(data)


def load_game(path: str = SAVE_PATH) -> "Engine":
    with open(path, "rb") as f:
        engine = pickle.loads(lzma.decompress(f.read()))
    _rehydrate(engine)
    return engine


# ---------------------------------------------------------------------------
# Post-load fixup: graft the code-defined callables back onto the graph.
# Done as one pass here (not in __setstate__) so we don't depend on the order
# pickle happens to restore cross-referencing objects in.
# ---------------------------------------------------------------------------
def _rehydrate(engine: "Engine") -> None:
    from lonelands import input_handlers, story
    from lonelands.quests import QuestLog

    # --- world: rebuild the Region factory table, then each cached Region's
    #     level builders (matched by coord against a fresh table).
    world = engine.game_world
    world._defs = world._region_defs()
    for coord, region in world.regions.items():
        make = world._defs.get(coord)
        if make is None:
            continue
        fresh = make()
        region._build_surface = fresh._build_surface
        region._build_deep = fresh._build_deep

    # --- quests: restore on_complete by id from a throwaway fresh log.
    saved_log = engine.quest_log
    fresh_log = QuestLog()
    engine.quest_log = fresh_log
    story.build_quests(engine)
    engine.quest_log = saved_log
    for qid, quest in saved_log.quests.items():
        fresh_q = fresh_log.get(qid)
        if fresh_q is not None:
            quest.on_complete = fresh_q.on_complete

    # --- NPCs: restore dialog trees by name across every built map. Spans every
    #     location (not just Bree), so a save made in a hamlet keeps its dialog.
    trees = {npc.name: npc.npc.tree for npc in story.all_speaking_npcs()}
    for region in world.regions.values():
        for gamemap in region.levels.values():
            for entity in gamemap.entities:
                npc = getattr(entity, "npc", None)
                if npc is not None and getattr(npc, "tree", None) is None:
                    npc.tree = trees.get(entity.name, {})

    # --- transient UI state.
    engine.last_roll = None
    engine.event_handler = input_handlers.MainGameEventHandler(engine)
