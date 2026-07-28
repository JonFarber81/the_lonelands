"""Input events and dispatch, independent of any windowing library.

This is the input half of the pygame migration (issue #66). It gives
the game its own tiny event vocabulary so handler bodies keep reading exactly as
they did under tcod — ``event.sym == KeySym.UP``, ``event.mod & Modifier.SHIFT``,
``event.tile.x`` — while the actual events are produced from pygame (see
:mod:`lonelands.display`).

``KeySym`` and ``Modifier`` are vendored here rather than imported from tcod so
the input path no longer depends on ``tcod.event``. Their integer values are the
SDL keycodes/keymods (the same numbers tcod and pygame both report), so the
``MOVE_KEYS`` tables and modifier masks in ``input_handlers`` are unchanged.
``tests/test_events.py`` cross-checks every member against tcod to guarantee
parity.
"""
from __future__ import annotations

import enum
from typing import NamedTuple, Optional


# --- Text alignment (matches tcod.constants) -------------------------------
LEFT = 0
RIGHT = 1
CENTER = 2


class KeySym(enum.IntEnum):
    """The subset of SDL keycodes the game binds. Values are the SDL keycodes,
    identical to ``tcod.event.KeySym`` and ``pygame.K_*`` so nothing downstream
    has to change."""

    # Printable ASCII letters (keycode == ord(lowercase))
    a = 97; b = 98; c = 99; d = 100; e = 101; f = 102; g = 103; h = 104
    i = 105; j = 106; k = 107; l = 108; m = 109; n = 110; o = 111; p = 112
    q = 113; r = 114; s = 115; t = 116; u = 117; v = 118; w = 119; x = 120
    y = 121; z = 122

    # Number row
    N1 = 49; N2 = 50; N3 = 51; N4 = 52; N5 = 53; N9 = 57

    # Punctuation (the shifted names GREATER/LESS/QUESTION are kept for the
    # constants the handlers reference; on a US layout the keydown actually
    # arrives as PERIOD/SLASH with a SHIFT modifier, exactly as under tcod).
    PERIOD = 46
    SLASH = 47
    LESS = 60
    GREATER = 62
    QUESTION = 63

    RETURN = 13
    ESCAPE = 27
    TAB = 9

    # Function keys (SDL2 keycodes, matching pygame.K_F*). F12 opens the debug
    # menu (ADR 0012); the rest are kept as a complete, tcod-cross-checked table.
    F5 = 1073741886
    F6 = 1073741887
    F7 = 1073741888
    F8 = 1073741889
    F9 = 1073741890
    F10 = 1073741891
    F11 = 1073741892
    F12 = 1073741893

    # Editing / navigation
    HOME = 1073741898
    PAGEUP = 1073741899
    END = 1073741901
    PAGEDOWN = 1073741902
    RIGHT = 1073741903
    LEFT = 1073741904
    DOWN = 1073741905
    UP = 1073741906
    CLEAR = 1073741980

    # Keypad
    KP_ENTER = 1073741912
    KP_1 = 1073741913
    KP_2 = 1073741914
    KP_3 = 1073741915
    KP_4 = 1073741916
    KP_5 = 1073741917
    KP_6 = 1073741918
    KP_7 = 1073741919
    KP_8 = 1073741920
    KP_9 = 1073741921
    KP_0 = 1073741922


class Modifier(enum.IntFlag):
    """Keyboard modifier bitmask (SDL keymod values, matching tcod/pygame)."""

    NONE = 0
    LSHIFT = 1
    RSHIFT = 2
    SHIFT = 3


# --- Events ----------------------------------------------------------------
class Point(NamedTuple):
    x: int
    y: int


class KeyDown(NamedTuple):
    sym: Optional[KeySym]
    mod: int  # SDL keymod bitmask; test with ``mod & Modifier.SHIFT``


class MouseMotion(NamedTuple):
    tile: Point  # cell coordinates on the console grid


class Quit:
    """The window-close request. A class (not a value) so ``isinstance`` works
    and matches how the old tcod ``ev_quit`` was dispatched."""


# --- Dispatch --------------------------------------------------------------
class BaseEventHandler:
    """Routes an event to the matching ``ev_*`` method.

    Replaces ``tcod.event.EventDispatch``: subclasses still define
    ``ev_keydown`` / ``ev_mousemotion`` / ``ev_quit`` and are dispatched here.
    Unhandled event types fall through to the no-op defaults below, so a handler
    only needs to implement the events it cares about.
    """

    def dispatch(self, event) -> "Optional[BaseEventHandler]":
        if isinstance(event, KeyDown):
            if event.sym is None:
                return None  # an unbound key (media key, etc.) — nothing binds it
            return self.ev_keydown(event)
        if isinstance(event, MouseMotion):
            return self.ev_mousemotion(event)
        if isinstance(event, Quit):
            return self.ev_quit(event)
        return None

    def handle_events(self, event) -> "BaseEventHandler":
        state = self.dispatch(event)
        if isinstance(state, BaseEventHandler):
            return state
        return self

    def on_render(self, console) -> None:
        raise NotImplementedError()

    def on_render_native(self, display) -> None:
        """Draw a pixel-space overlay (native menus, Phase 3) on top of the
        blitted console grid. Default: nothing — grid-only handlers (the map
        view, HUD, targeting) don't override it."""

    def ev_keydown(self, event: KeyDown) -> "Optional[BaseEventHandler]":
        return None

    def ev_mousemotion(self, event: MouseMotion) -> "Optional[BaseEventHandler]":
        return None

    def ev_quit(self, event: Quit) -> "Optional[BaseEventHandler]":
        raise SystemExit()
