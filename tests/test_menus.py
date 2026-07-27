"""Phase 3 native menus: every migrated handler renders through the real
pipeline (console underlay + pixel overlay) without error, and grid-only
handlers keep the default no-op native pass."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from lonelands import config, display, input_handlers as ih, perks, setup_game  # noqa: E402


@pytest.fixture(scope="module")
def env():
    try:
        disp = display.Display()
    except Exception as exc:  # pragma: no cover - no video subsystem
        pytest.skip(f"no display: {exc}")
    console = display.Console(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    engine = setup_game.new_game()
    engine.update_fov()
    # Level up to earn Path points and commit a Path so the Paths/Character
    # screens have a committed tree with buyable nodes to render.
    engine.player.hero.path_points += 4
    engine.player.hero.commit_path("long_watch")
    engine.player.hero.buy_node(perks.ALL_NODES["lw_endure"])
    return disp, console, engine


def _render(env, handler) -> None:
    disp, console, _ = env
    console.clear()
    handler.on_render(console)          # grid underlay (game + scrim, or bg)
    disp.blit_console(console)
    handler.on_render_native(disp)       # native pixel overlay
    disp.flip()


def test_full_screen_menus_render(env):
    _render(env, ih.MainMenuHandler())
    _render(env, ih.DifficultySelectHandler())


def test_overlay_menus_render(env):
    _, _, engine = env
    for cls in (
        ih.InventoryActivateHandler,
        ih.InventoryDropHandler,
        ih.CharacterScreenHandler,
        ih.PathsHandler,
        ih.AbilitiesHandler,
        ih.QuestScreenHandler,
        ih.HelpHandler,
        ih.EscapeMenuHandler,
    ):
        _render(env, cls(engine))


def test_popup_dialog_shop_render(env):
    _, _, engine = env
    from lonelands import content
    _render(env, ih.PopupMessage(ih.MainMenuHandler(), "Failed to load:\nbad save"))
    _render(env, ih.ShopHandler(engine, "Barliman's Stall",
                                [content.short_sword, content.arrows]))
    npc = next((a for a in engine.game_map.actors if getattr(a, "npc", None)), None)
    if npc is not None:
        _render(env, ih.DialogHandler(engine, npc))


def test_paths_screen_fits_panel(env):
    # The committed Path's tree renders (boxes, prereq edges, pips, state).
    _, _, engine = env
    _render(env, ih.PathsHandler(engine))


def test_path_chooser_and_confirm_render(env):
    # A fresh, pathless hero opens the level-2 chooser; the tabbed tree browse
    # and the permanent-choice confirm both render without error.
    disp, console, _ = env
    fresh = setup_game.new_game()
    fresh.update_fov()
    ph = ih.PathsHandler(fresh)
    assert ph._chooser()                       # pathless -> chooser mode
    _render((disp, console, fresh), ph)
    ph.view_idx = 2                            # browse to a different tree
    ph.cursor_id = perks.PATHS[2].nodes[0].id
    _render((disp, console, fresh), ph)
    _render((disp, console, fresh), ph._commit_viewed())  # the confirm modal


def test_chooser_commit_is_a_permanent_choice():
    # Acceptance (#74): commit throws a confirm; confirming locks the Path
    # permanently and drops into that committed tree.
    from lonelands import events
    engine = setup_game.new_game()
    engine.player.hero.path_points += 1
    ph = ih.PathsHandler(engine)
    ph.view_idx = 1                            # the Far Shot
    ph.cursor_id = perks.PATHS[1].nodes[0].id
    confirm = ph.ev_keydown(events.KeyDown(sym=ih.KeySym.RETURN, mod=0))
    assert isinstance(confirm, ih.ConfirmHandler)
    result = confirm.on_confirm()              # answer "yes"
    hero = engine.player.hero
    assert hero.path == "far_shot"
    assert isinstance(result, ih.PathsHandler) and not result._chooser()
    assert hero.commit_path("long_watch") is False   # no second commit


def test_chooser_arrows_switch_paths():
    # While pathless, ←/→ (and Tab) switch which Path is browsed — matching the
    # on-screen hint — rather than moving the node cursor.
    from lonelands import events
    engine = setup_game.new_game()
    ph = ih.PathsHandler(engine)
    assert ph._chooser() and ph.view_idx == 0
    ph.ev_keydown(events.KeyDown(sym=ih.KeySym.RIGHT, mod=0))
    assert ph.view_idx == 1
    ph.ev_keydown(events.KeyDown(sym=ih.KeySym.LEFT, mod=0))
    assert ph.view_idx == 0
    ph.ev_keydown(events.KeyDown(sym=ih.KeySym.TAB, mod=0))
    assert ph.view_idx == 1


def test_tree_cursor_walks_and_buys():
    # Arrow keys walk the tree; Enter buys the cursor node in committed mode.
    from lonelands import events
    engine = setup_game.new_game()
    hero = engine.player.hero
    hero.path_points += 3
    hero.commit_path("long_watch")
    ph = ih.PathsHandler(engine)
    assert ph.cursor_id == "lw_endure"         # the branching trunk root
    ph.ev_keydown(events.KeyDown(sym=ih.KeySym.UP, mod=0))
    assert ph.cursor_id == "lw_wind"           # up the stem to the other trunk root
    ph.cursor_id = "lw_endure"
    ph.ev_keydown(events.KeyDown(sym=ih.KeySym.RETURN, mod=0))
    assert hero.has_node("lw_endure")          # bought at the cursor


def test_hotbar_fires_a_ready_deed_and_renders(env):
    # Owned actives auto-bind to keys 1–5; the number fires, an empty slot no-ops,
    # and the sidebar hotbar renders (ADR 0011, #74).
    from lonelands import events
    from lonelands.actions import ActivateAbilityAction
    disp, console, _ = env
    engine = setup_game.new_game()
    engine.update_fov()
    hero = engine.player.hero
    hero.path_points += 2
    hero.commit_path("long_watch")
    hero.buy_node(perks.ALL_NODES["lw_wind"])        # Second Wind -> slot 1
    assert [n.id for n in hero.hotbar()] == ["lw_wind"]
    mgh = ih.MainGameEventHandler(engine)
    action = mgh.ev_keydown(events.KeyDown(sym=ih.KeySym.N1, mod=0))
    assert isinstance(action, ActivateAbilityAction) and action.node_id == "lw_wind"
    assert mgh.ev_keydown(events.KeyDown(sym=ih.KeySym.N5, mod=0)) is None  # empty slot
    _render((disp, console, engine), ih.MainGameEventHandler(engine))


def test_prop_fit_rows_fit_available_height(env):
    # prop_fit must size rows so n_lines * step never exceeds the budget.
    disp, _, _ = env
    for n, h in [(30, 900), (10, 400), (60, 800)]:
        _font, step = disp.ui.prop_fit(n, h)
        assert step * n <= h


def test_main_game_renders_native_hud(env):
    # The map draws to the console grid; the sidebar + Chronicle + banner render
    # on the native layer (the HUD). Both passes must run without error.
    disp, console, engine = env
    from lonelands import color, dice
    engine.message_log.add_message("A test line of prose for the Chronicle.", color.white)
    engine.last_roll = dice.RollResult(die=18, mod=3, tn=15, dice=[18], damage=6)
    _render(env, ih.MainGameEventHandler(engine))


def test_overworld_atlas_opts_out_of_hud_backdrop(env):
    # The full-screen atlas is a grid page; its native pass is a deliberate no-op
    # so the HUD backdrop doesn't paint over it.
    _, _, engine = env
    assert ih.OverworldMapHandler.on_render_native is not \
        ih.AskUserHandler.on_render_native
    _render(env, ih.OverworldMapHandler(engine))
