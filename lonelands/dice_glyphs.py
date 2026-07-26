"""Private-Use-Area codepoints for the baked die-face glyphs.

This is the single registry both sides of the seam agree on: ``fonts.py`` bakes
pixel art into these codepoints (see ADR 0001), and the dice-tray renderer prints
them by the same codepoint. Keep drawing routines out of here — this module is
pure constants so it can be imported from anywhere without pulling in FreeType.

Each die is drawn **two cells wide by two cells tall** (tcod renders one glyph
per cell), so every face occupies a 2×2 block of four consecutive codepoints in
row-major order: (top-left, top-right, bottom-left, bottom-right). The larger
block gives each face's numeral the pixels it needs to read clearly. Feat die
faces map value 1..12; 11 is the Eye of Sauron and 12 the Gandalf rune (drawn
specially, but still addressed by their face value). Success die faces map value
1..6; the 6 is the tengwar rune.
"""
from __future__ import annotations

FEAT_BASE = 0xE000     # feat face v -> block at 0xE000 + 4v,  v in 1..12
SUCCESS_BASE = 0xE040  # success face v -> block at 0xE040 + 4v, v in 1..6

FEAT_VALUES = range(1, 13)
SUCCESS_VALUES = range(1, 7)

# Each die spans this many cells: DIE_COLS wide, DIE_ROWS tall.
DIE_COLS = 2
DIE_ROWS = 2
DIE_CELLS = DIE_COLS  # width in cells; the tray advances x by this per die


def _block(base: int, value: int) -> tuple[int, int, int, int]:
    """The 2×2 codepoint block (TL, TR, BL, BR) for one die face."""
    b = base + value * 4
    return b, b + 1, b + 2, b + 3


def feat_codepoints(value: int) -> tuple[int, int, int, int]:
    return _block(FEAT_BASE, value)


def success_codepoints(value: int) -> tuple[int, int, int, int]:
    return _block(SUCCESS_BASE, value)


def _rows(codepoints: tuple[int, int, int, int]) -> tuple[str, str]:
    tl, tr, bl, br = codepoints
    return chr(tl) + chr(tr), chr(bl) + chr(br)


def feat_rows(value: int) -> tuple[str, str]:
    """(top, bottom) two-cell strings for a feat-die face."""
    return _rows(feat_codepoints(value))


def success_rows(value: int) -> tuple[str, str]:
    """(top, bottom) two-cell strings for a success-die face."""
    return _rows(success_codepoints(value))
