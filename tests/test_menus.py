"""Phase 3 native menus: every migrated handler renders through the real
pipeline (console underlay + pixel overlay) without error, and grid-only
handlers keep the default no-op native pass."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from lonelands import config, display, events, input_handlers as ih, setup_game  # noqa: E402


@pytest.fixture(scope="module")
def env():
    try:
        disp = display.Display()
    except Exception as exc:  # pragma: no cover - no video subsystem
        pytest.skip(f"no display: {exc}")
    console = display.Console(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    engine = setup_game.new_game()
    engine.update_fov()
    engine.player.hero.perk_points += 2  # so Paths/Character show buyable perks
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
    # The densest screen: all five Paths + their perks must fit (regression on
    # the adaptive prop_fit sizing). Rendering without exception exercises the
    # truncation and fit paths.
    _, _, engine = env
    _render(env, ih.PathsHandler(engine))


def test_prop_fit_rows_fit_available_height(env):
    # prop_fit must size rows so n_lines * step never exceeds the budget.
    disp, _, _ = env
    for n, h in [(30, 900), (10, 400), (60, 800)]:
        _font, step = disp.ui.prop_fit(n, h)
        assert step * n <= h


def test_grid_handler_has_noop_native(env):
    # The map view draws only to the console grid; its native pass is a no-op.
    _, _, engine = env
    handler = ih.MainGameEventHandler(engine)
    assert type(handler).on_render_native is events.BaseEventHandler.on_render_native
