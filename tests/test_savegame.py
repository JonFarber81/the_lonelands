"""Save/continue round-trip tests.

The whole game state is one object graph hung off the Engine; a save is a
pickle of it. The graph is riddled with lambdas the code rebuilds on load —
the world's Region factories, each Region's level builders, `Quest.on_complete`,
and every NPC's dialog `tree`. These tests drive a real headless game through
save -> load and assert both the *dynamic* state (positions, progress, coins)
and the *rebuilt* callables survive.
"""
from __future__ import annotations

import pytest

from lonelands import savegame, setup_game
from lonelands.dice import set_seed


@pytest.fixture
def saved(tmp_path):
    """A game with some travelled, mutated state, round-tripped through disk."""
    set_seed(1)
    engine = setup_game.new_game()
    engine.turn_count = 42
    engine.player.hero.coins = 99
    engine.quest_log.start("wolves")
    engine.quest_log.get("wolves").advance()
    engine.flags["herbwife_gift"] = True
    engine.game_world.cross_edge(-1, 0)           # travel west into the Barrow-downs
    engine.game_world.current_region.level(-1)    # build a barrow deep too

    path = tmp_path / "game.sav"
    savegame.save_game(engine, str(path))
    return engine, savegame.load_game(str(path))


def test_dynamic_state_survives(saved):
    before, after = saved
    assert after.turn_count == before.turn_count
    assert after.player.hero.coins == 99
    assert after.quest_log.get("wolves").progress == 1
    assert after.flags["herbwife_gift"] is True
    assert after.game_world.coord == before.game_world.coord
    assert sorted(after.game_world.regions) == sorted(before.game_world.regions)
    assert [i.name for i in after.player.inventory.items] == \
           [i.name for i in before.player.inventory.items]


def test_rebuilt_callables_are_restored(saved):
    _, after = saved
    assert after.game_world._defs is not None
    assert after.game_world.current_region._build_surface is not None
    assert after.quest_log.get("main_barrow").on_complete is not None


def test_npc_dialog_trees_are_restored(saved):
    _, after = saved
    bree = after.game_world.regions[(0, 0)].levels[0]
    npcs = [e for e in bree.entities if getattr(e, "npc", None)]
    assert npcs, "expected town NPCs in Bree"
    assert all(n.npc.tree for n in npcs)


def test_loaded_game_keeps_running(saved):
    """The restored graph must drive real gameplay: descend a level, take a turn."""
    _, after = saved
    after.game_world.current_region.level(-1)     # re-enter a deep from restored region
    after.handle_enemy_turns()                    # a full turn against live AI
    assert after.event_handler is not None


def test_quest_turn_in_uses_restored_callback(tmp_path):
    """on_complete must actually fire after a load, not just be non-None."""
    set_seed(2)
    engine = setup_game.new_game()
    engine.quest_log.start("main_barrow")
    q = engine.quest_log.get("main_barrow")
    q.advance()                                   # -> READY
    path = tmp_path / "g.sav"
    savegame.save_game(engine, str(path))
    after = savegame.load_game(str(path))
    n_items_before = len(after.player.inventory.items)
    assert after.quest_log.turn_in("main_barrow", after) is True
    # finish_main grants a Dúnedain sword straight into the pack.
    assert len(after.player.inventory.items) == n_items_before + 1
