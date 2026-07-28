#!/usr/bin/env python3
"""The Lonelands — a Middle-earth roguelike. Entry point.

Windowing, rendering, and input run on pygame (issue #66; ADR-0010 lands in the
migration's Phase 4). tcod is retained only as a headless library for FOV and
pathfinding. The render loop
paints a :class:`lonelands.display.Console` to the pygame window and feeds
translated pygame events to the same ``handle_events`` chain as before.
"""
from __future__ import annotations

import argparse
import traceback

import pygame

from lonelands import color, config, display, events, sprites
from lonelands import input_handlers
from lonelands.exceptions import QuitWithoutSaving


# SPIKE (#92): live sprite tone tuner, --debug + --sprites only. F5/F6 brightness,
# F7/F8 saturation, F9/F10 warm/cool, F11 reset; each nudge logs the paste-ready
# GRADE line to the Chronicle. Maps a key to (d_darken, d_desat, d_warmth).
_GRADE_KEYS = {
    events.KeySym.F5: (-0.05, 0.0, 0.0),   # darker
    events.KeySym.F6: (0.05, 0.0, 0.0),    # brighter
    events.KeySym.F7: (0.0, -0.04, 0.0),   # more colour (less grey)
    events.KeySym.F8: (0.0, 0.04, 0.0),    # more grey (desaturate)
    events.KeySym.F9: (0.0, 0.0, -0.03),   # cooler
    events.KeySym.F10: (0.0, 0.0, 0.03),   # warmer
}


def _tune_grade(event, disp, handler) -> bool:
    """Handle a debug tone-tuner keypress; return True if it was one (consumed).

    A no-op unless --debug and --sprites are both on and the map is showing."""
    if not (config.DEBUG and config.SPRITES):
        return False
    if not isinstance(event, events.KeyDown):
        return False
    if event.sym == events.KeySym.F11:
        msg = sprites.reset_grade()
    elif event.sym in _GRADE_KEYS:
        msg = sprites.nudge_grade(*_GRADE_KEYS[event.sym])
    else:
        return False
    if disp._sprites is not None:
        disp._sprites.invalidate()  # tone isn't in the cache key — force a re-bake
    engine = getattr(handler, "engine", None)
    if engine is not None:
        engine.message_log.add_message(msg, color.hope_gain)
    print(msg)  # also to stdout, for easy copy back into sprites.GRADE
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="the-lonelands", description="The Lonelands — a Middle-earth roguelike."
    )
    parser.add_argument(
        "-d", "--debug", action="store_true",
        help="enable debug mode: the F12 cheat menu (god, level, teleport…). "
             "Runtime only — never written to a save (ADR 0012).",
    )
    parser.add_argument(
        # SPIKE (issue #92): hidden vertical slice of the sprite path. Undocumented
        # on purpose — no data model, toggle UI, or coverage yet (ADR-0013 Phase 0).
        "--sprites", action="store_true", help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config.DEBUG = args.debug
    if args.sprites:
        config.SPRITES = True
        config.TILE_HEIGHT = config.TILE_WIDTH  # square cells for the sprite map
    disp = display.Display()
    console = display.Console(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    handler: events.BaseEventHandler = input_handlers.MainMenuHandler()

    try:
        while True:
            console.clear()
            handler.on_render(console)          # the cell-grid layer (map + HUD)
            disp.blit_console(console)
            # SPIKE (#92): composite sprites over the ASCII map viewport, but
            # under the native HUD/menus. Only for handlers that draw the region
            # map (not the overworld view or the main menu).
            if config.SPRITES and getattr(handler, "renders_region_map", False):
                engine = getattr(handler, "engine", None)
                if engine is not None:
                    disp.blit_sprite_map(engine.game_map)
            handler.on_render_native(disp)       # native pixel overlay (menus)
            disp.flip()

            try:
                # Block for the next event (no busy loop), then drain the rest
                # so a burst of mouse motion collapses into a single re-render.
                pending = [pygame.event.wait()]
                pending.extend(pygame.event.get())
                for pg_event in pending:
                    if pg_event.type == pygame.VIDEORESIZE:
                        # Replaces tcod's change_tileset on resize: refit whole
                        # cells and re-rasterize the glyph cache.
                        disp.resize(pg_event.w, pg_event.h)
                        continue
                    event = disp.translate(pg_event)
                    if event is None:
                        continue
                    if _tune_grade(event, disp, handler):
                        continue
                    handler = handler.handle_events(event)
            except Exception:  # keep the game alive on a stray error
                traceback.print_exc()
                if hasattr(handler, "engine"):
                    handler.engine.message_log.add_message(
                        traceback.format_exc().splitlines()[-1], color.error
                    )
    except QuitWithoutSaving:
        pygame.quit()
        raise SystemExit()
    except SystemExit:
        pygame.quit()
        raise


if __name__ == "__main__":
    main()
