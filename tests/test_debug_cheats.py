"""Debug-mode cheats (ADR 0012).

These cover the *logic* seams the F12 Debug menu drives — god-mode damage
absorption and weariness suppression, region teleport, and the runtime-only
nature of debug state (nothing leaks into a save). The menu handler itself is a
thin UI shell over these; the menu-open gate is covered in test_menus.py.
"""
from __future__ import annotations

import pytest

from lonelands import config, input_handlers as ih, savegame, setup_game
from lonelands.dice import set_seed
from lonelands.events import KeyDown, KeySym


@pytest.fixture
def game():
    set_seed(1)
    engine = setup_game.new_game()
    return engine, engine.game_world, engine.player


# --- runtime flag -----------------------------------------------------------

def test_debug_flag_defaults_off():
    assert config.DEBUG is False


def test_god_mode_defaults_off(game):
    engine, _, _ = game
    assert engine.god_mode is False


# --- god mode: damage -------------------------------------------------------

def test_god_mode_absorbs_player_damage(game):
    engine, _, player = game
    player.fighter.endurance = player.fighter.max_endurance
    engine.god_mode = True
    player.fighter.take_damage(9999)
    assert player.fighter.endurance == player.fighter.max_endurance


def test_without_god_mode_player_takes_damage(game):
    engine, _, player = game
    before = player.fighter.endurance
    player.fighter.take_damage(3)
    assert player.fighter.endurance < before


def test_god_mode_does_not_shield_foes(game):
    import copy

    from lonelands import content

    engine, gw, player = game
    engine.god_mode = True
    # A real foe placed on the player's map still takes its blow: god mode only
    # ever spares the player.
    foe = copy.deepcopy(content.wolf)
    engine.game_map.entities.add(foe)
    foe.parent = engine.game_map
    foe.x, foe.y = player.x, player.y
    before = foe.fighter.endurance
    foe.fighter.take_damage(3)
    assert foe.fighter.endurance < before


# --- god mode: weariness ----------------------------------------------------

def test_god_mode_suppresses_weariness(game):
    engine, _, player = game
    # Force the weary condition: endurance at or below carried load.
    player.fighter.endurance = 1
    assert player.hero.load >= 1  # the starting kit weighs something
    assert player.hero.is_weary is True
    engine.god_mode = True
    assert player.hero.is_weary is False


# --- teleport ---------------------------------------------------------------

def test_teleport_to_moves_to_region_surface(game):
    engine, gw, player = game
    assert gw.coord == (0, 0)
    moved = gw.teleport_to((2, 0))            # Weathertop, east
    assert moved is True
    assert gw.coord == (2, 0)
    assert gw.level_index == 0
    assert engine.game_map.name.startswith("Weathertop")
    # Landed on a walkable tile inside the map.
    assert engine.game_map.in_bounds(player.x, player.y)
    assert engine.game_map.tiles["walkable"][player.x, player.y]


def test_teleport_rejects_impassable_cell(game):
    engine, gw, player = game
    moved = gw.teleport_to((-7, 2))           # the Gulf of Lune — absent from grid
    assert moved is False
    assert gw.coord == (0, 0)                  # unmoved


def test_teleport_from_the_deeps_returns_to_surface(game):
    engine, gw, player = game
    gw.cross_edge(-1, 0)                       # into the Barrow-downs
    gw.current_region.level(-1)               # a deep exists
    gw.level_index = -1                        # pretend we're below
    moved = gw.teleport_to((0, 0))            # back to Bree
    assert moved is True
    assert gw.level_index == 0


# --- save/load: debug state is runtime-only ---------------------------------

def test_god_mode_resets_on_load(tmp_path, game):
    engine, _, _ = game
    engine.god_mode = True
    path = tmp_path / "g.sav"
    savegame.save_game(engine, str(path))
    reloaded = savegame.load_game(str(path))
    assert reloaded.god_mode is False


# --- F12 gate & menu actions ------------------------------------------------

@pytest.fixture
def debug_on():
    """config.DEBUG is a process global; flip it on for a test, restore after."""
    prev = config.DEBUG
    config.DEBUG = True
    yield
    config.DEBUG = prev


def _key(sym):
    return KeyDown(sym=sym, mod=0)


def test_f12_ignored_without_debug(game):
    engine, _, _ = game
    assert config.DEBUG is False
    handler = ih.MainGameEventHandler(engine)
    assert handler.ev_keydown(_key(KeySym.F12)) is None


def test_f12_opens_menu_under_debug(game, debug_on):
    engine, _, _ = game
    handler = ih.MainGameEventHandler(engine)
    opened = handler.ev_keydown(_key(KeySym.F12))
    assert isinstance(opened, ih.DebugMenuHandler)


def test_menu_god_toggle_flips_and_stays_open(game, debug_on):
    engine, _, _ = game
    menu = ih.DebugMenuHandler(engine)
    result = menu.ev_keydown(_key(KeySym.g))
    assert engine.god_mode is True
    assert result is None                 # toggle keeps the panel open


def test_menu_kill_clears_hostiles(game, debug_on):
    import copy

    from lonelands import actions, content

    engine, _, player = game
    for _ in range(3):
        foe = copy.deepcopy(content.wolf)
        engine.game_map.entities.add(foe)
        foe.parent = engine.game_map
        foe.x, foe.y = player.x, player.y
        foe.fighter  # touch to ensure component wired
    assert [a for a in engine.game_map.actors if actions.is_hostile_actor(a)]
    ih.DebugMenuHandler(engine).ev_keydown(_key(KeySym.k))
    assert not [a for a in engine.game_map.actors if actions.is_hostile_actor(a)]


def test_menu_reveal_explores_whole_map(game, debug_on):
    engine, _, _ = game
    engine.game_map.explored[:] = False
    ih.DebugMenuHandler(engine).ev_keydown(_key(KeySym.r))
    assert engine.game_map.explored.all()


def test_granted_level_survives_load(tmp_path, game):
    engine, _, player = game
    before = player.hero.level
    player.hero.add_xp(player.hero.xp_to_next)   # the "gain a level" cheat's core
    leveled = player.hero.level
    assert leveled == before + 1
    path = tmp_path / "g.sav"
    savegame.save_game(engine, str(path))
    reloaded = savegame.load_game(str(path))
    assert reloaded.player.hero.level == leveled  # a real consequence persists
