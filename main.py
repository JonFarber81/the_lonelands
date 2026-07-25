#!/usr/bin/env python3
"""The Lonelands — a Middle-earth roguelike. Entry point."""
from __future__ import annotations

import traceback

import tcod

from lonelands import color, config, fonts
from lonelands import input_handlers
from lonelands.exceptions import QuitWithoutSaving


def main() -> None:
    tileset = fonts.load_tileset()
    handler: input_handlers.BaseEventHandler = input_handlers.MainMenuHandler()

    with tcod.context.new(
        columns=config.SCREEN_WIDTH,
        rows=config.SCREEN_HEIGHT,
        tileset=tileset,
        title=config.WINDOW_TITLE,
        vsync=True,
    ) as context:
        console = tcod.console.Console(
            config.SCREEN_WIDTH, config.SCREEN_HEIGHT, order="F"
        )
        try:
            while True:
                console.clear()
                handler.on_render(console)
                # integer_scaling keeps whole-pixel glyphs (no blur); on resize
                # we regenerate the tileset at the window's pixel density so the
                # font stays crisp and legible at any size.
                context.present(console, integer_scaling=True)

                try:
                    for event in tcod.event.wait():
                        context.convert_event(event)
                        if isinstance(event, tcod.event.WindowResized):
                            cell_w = max(1, event.width // config.SCREEN_WIDTH)
                            cell_h = max(1, event.height // config.SCREEN_HEIGHT)
                            context.change_tileset(
                                fonts.load_tileset(cell_w, cell_h)
                            )
                        handler = handler.handle_events(event)
                except Exception:  # keep the game alive on a stray error
                    traceback.print_exc()
                    if hasattr(handler, "engine"):
                        handler.engine.message_log.add_message(
                            traceback.format_exc().splitlines()[-1], color.error
                        )
        except QuitWithoutSaving:
            raise SystemExit()
        except SystemExit:
            raise


if __name__ == "__main__":
    main()
