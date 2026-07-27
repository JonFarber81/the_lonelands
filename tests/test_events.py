"""The input shim (lonelands/events.py): KeySym/Modifier parity with the SDL
keycodes tcod reports, and BaseEventHandler dispatch."""
from __future__ import annotations

import tcod.event as te

from lonelands import events
from lonelands.events import KeySym, Modifier


def test_keysym_values_match_tcod():
    # Every vendored key must carry the same SDL keycode tcod (and pygame)
    # report, so MOVE_KEYS and friends keep matching real key events.
    for member in KeySym:
        assert int(member) == int(getattr(te.KeySym, member.name)), member.name


def test_modifier_values_match_tcod():
    for member in Modifier:
        assert int(member) == int(getattr(te.Modifier, member.name)), member.name
    # The mask test the shop handler relies on.
    assert (Modifier.LSHIFT & Modifier.SHIFT)
    assert not (Modifier.NONE & Modifier.SHIFT)


def test_alignment_matches_tcod():
    import tcod.constants as tc
    assert (events.LEFT, events.RIGHT, events.CENTER) == (
        int(tc.LEFT), int(tc.RIGHT), int(tc.CENTER),
    )


class _Recorder(events.BaseEventHandler):
    def __init__(self):
        self.seen = None

    def ev_keydown(self, event):
        self.seen = ("key", event.sym, event.mod)
        return None

    def ev_mousemotion(self, event):
        self.seen = ("motion", event.tile.x, event.tile.y)
        return None


def test_dispatch_routes_by_type():
    h = _Recorder()
    h.dispatch(events.KeyDown(sym=KeySym.UP, mod=0))
    assert h.seen == ("key", KeySym.UP, 0)
    h.dispatch(events.MouseMotion(events.Point(3, 4)))
    assert h.seen == ("motion", 3, 4)


def test_quit_raises_system_exit():
    import pytest
    with pytest.raises(SystemExit):
        events.BaseEventHandler().dispatch(events.Quit())


def test_handle_events_returns_new_state_or_self():
    target = _Recorder()

    class Switch(events.BaseEventHandler):
        def ev_keydown(self, event):
            return target

    switch = Switch()
    assert switch.handle_events(events.KeyDown(sym=KeySym.a, mod=0)) is target
    # A handler that returns None keeps the current state.
    assert target.handle_events(events.KeyDown(sym=KeySym.a, mod=0)) is target
