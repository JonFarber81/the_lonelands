#!/usr/bin/env python3
"""The Lonelands — a Middle-earth roguelike. Entry point."""
from __future__ import annotations

import traceback

import tcod

from lonelands import color, config
from lonelands import input_handlers
from lonelands.exceptions import QuitWithoutSaving


def load_tileset() -> tcod.tileset.Tileset:
    path = config.find_font()
    if path is None:
        # Fall back to tcod's built-in tileset via a blank Tileset.
        return tcod.tileset.Tileset(config.TILE_WIDTH, config.TILE_HEIGHT)
    return tcod.tileset.load_truetype_font(
        path, config.TILE_WIDTH, config.TILE_HEIGHT
    )


def main() -> None:
    tileset = load_tileset()
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
                context.present(console)

                try:
                    for event in tcod.event.wait():
                        context.convert_event(event)
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
