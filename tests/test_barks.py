"""Ambient barks (issue #54): the pure selection/throttle seam.

``BarkField.choose`` is deterministic given ``roll`` and ``pick`` stubs, so the
"which source, which line, or nothing" decision is exercised here without an
engine. The integration wiring (a field on the map, emitted on player move) is
covered in test_cluster_breeland.py.
"""
from __future__ import annotations

from lonelands import color
from lonelands.barks import BarkField, BarkSource


def _field(**kw):
    src = BarkSource(x=10, y=10, radius=3, lines=["a bark", "a howl"], cadence=10)
    return BarkField([src], **kw), src


# roll stubs: always-speak vs never-speak (chance default is 0.3)
def _yes():
    return 0.0


def _no():
    return 0.99


def _first(seq):
    return seq[0]


# --- range -----------------------------------------------------------------

def test_source_out_of_range_never_barks():
    field, _ = _field()
    # Chebyshev distance 4 > radius 3
    assert field.choose(10, 14, 100, roll=_yes, pick=_first) is None


def test_source_in_range_barks_when_the_roll_passes():
    field, src = _field()
    chosen = field.choose(11, 12, 100, roll=_yes, pick=_first)
    assert chosen is not None
    got_src, line = chosen
    assert got_src is src and line == "a bark"


def test_in_range_but_the_roll_declines():
    field, _ = _field()
    assert field.choose(10, 10, 100, roll=_no, pick=_first) is None


# --- per-source cadence ----------------------------------------------------

def test_a_source_stays_quiet_until_its_cadence_elapses():
    field, src = _field()
    chosen = field.choose(10, 10, 100, roll=_yes, pick=_first)
    assert chosen is not None
    field.commit(chosen[0], 100)
    # too soon: cadence is 10, only 5 turns on
    assert field.eligible(10, 10, 105) == []
    # ...and ready again once it has elapsed
    assert field.eligible(10, 10, 110) == [src]


# --- global throttle -------------------------------------------------------

def test_global_cadence_gates_any_second_bark():
    field, _ = _field(global_cadence=5)
    first = field.choose(10, 10, 100, roll=_yes, pick=_first)
    field.commit(first[0], 100)
    # a different, in-range, ready source exists...
    field.sources.append(BarkSource(x=10, y=10, radius=3, lines=["woof"], cadence=1))
    # ...but the field-wide throttle still silences everything for global_cadence
    assert field.choose(10, 10, 102, roll=_yes, pick=_first) is None
    assert field.choose(10, 10, 105, roll=_yes, pick=_first) is not None


# --- nothing eligible ------------------------------------------------------

def test_empty_field_is_silent():
    field = BarkField([])
    assert field.choose(0, 0, 100, roll=_yes, pick=_first) is None


# --- defaults --------------------------------------------------------------

def test_source_defaults_to_the_ambient_colour_and_never_fired():
    src = BarkSource(x=0, y=0, radius=1, lines=["x"])
    assert src.fg == color.ambient
    # a fresh source is immediately eligible whatever the turn count
    assert BarkField([src]).eligible(0, 0, 0) == [src]
