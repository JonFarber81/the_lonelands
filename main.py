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

from lonelands import color, config, display, events
from lonelands import input_handlers
from lonelands.exceptions import QuitWithoutSaving


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="the-lonelands", description="The Lonelands — a Middle-earth roguelike."
    )
    parser.add_argument(
        "-d", "--debug", action="store_true",
        help="enable debug mode: the F12 cheat menu (god, level, teleport…). "
             "Runtime only — never written to a save (ADR 0012).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config.DEBUG = args.debug
    disp = display.Display()
    console = display.Console(config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
    handler: events.BaseEventHandler = input_handlers.MainMenuHandler()

    try:
        while True:
            console.clear()
            handler.on_render(console)          # the cell-grid layer (map + HUD)
            disp.blit_console(console)
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
