"""Private-Use-Area codepoints for the baked die-face glyphs.

This is the single registry both sides of the seam agree on: ``fonts.py`` bakes
pixel art into these codepoints (see ADR 0001), and the dice-tray renderer prints
them by the same codepoint. Keep drawing routines out of here — this module is
pure constants so it can be imported from anywhere without pulling in FreeType.

Each die spans **two cells** (tcod renders one glyph per cell), so every face
occupies a consecutive (left-half, right-half) codepoint pair. Feat die faces map
value 1..12; 11 is the Eye of Sauron and 12 the Gandalf rune (drawn specially,
but still addressed by their face value). Success die faces map value 1..6; the
6 is the tengwar rune.
"""
from __future__ import annotations

FEAT_BASE = 0xE000     # feat face v -> (0xE000 + 2v, +1),  v in 1..12
SUCCESS_BASE = 0xE040  # success face v -> (0xE040 + 2v, +1), v in 1..6

FEAT_VALUES = range(1, 13)
SUCCESS_VALUES = range(1, 7)

# Each die is this many cells wide.
DIE_CELLS = 2


def feat_codepoints(value: int) -> tuple[int, int]:
    base = FEAT_BASE + value * 2
    return base, base + 1


def success_codepoints(value: int) -> tuple[int, int]:
    base = SUCCESS_BASE + value * 2
    return base, base + 1


def feat_chars(value: int) -> str:
    left, right = feat_codepoints(value)
    return chr(left) + chr(right)


def success_chars(value: int) -> str:
    left, right = success_codepoints(value)
    return chr(left) + chr(right)
