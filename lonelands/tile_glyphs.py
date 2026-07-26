"""Private-Use codepoints for map/entity glyphs drawn from a graphical tileset.

The game is codepoint-based: a floor is ``.``, a wall ``#``, the player ``@``.
But those same characters also appear in *prose* (a full stop, a hash, an email
``@``), and prose must stay in the readable TrueType font — we do **not** want
Wanderlust's shaded floor-dot standing in for the period at the end of a
sentence.

So map terrain and entity glyphs are addressed by a **separate** Private-Use
codepoint, distinct from the ASCII character that names them. ``fonts.py`` bakes
the graphical tile (a Wanderlust cell, or the TTF glyph as a fallback) into
``graphic_cp(ch)``; the map/entity renderers print that codepoint. Text keeps the
plain ASCII codepoint and its TTF glyph. One character, two glyphs, chosen by
context.

Like :mod:`lonelands.dice_glyphs` this module is pure constants so ``tile_types``
can import it without pulling in FreeType. Its range is kept clear of the dice
codepoints (0xE000–0xE05B).
"""
from __future__ import annotations

# Base for the graphical map/entity glyphs. A printable-ASCII char ``ch`` maps to
# ``GRAPHIC_BASE + ord(ch)`` — e.g. ``#`` (0x23) -> 0xE123. This sits above the
# dice faces (see dice_glyphs.FEAT_BASE/SUCCESS_BASE) so the two never collide.
GRAPHIC_BASE = 0xE100

# The characters we back with tileset art: printable ASCII. Map tiles and entity
# glyphs all fall in this range; anything outside it (accented prose, typographic
# marks) is left on its own codepoint so it renders as text.
GRAPHIC_RANGE = range(0x20, 0x7F)


def graphic_cp(ch: str) -> int:
    """Codepoint of the graphical (tileset) glyph for ``ch``.

    Printable ASCII maps into the Private-Use graphic block; any other character
    is returned unchanged, so it falls through to its normal text glyph.
    """
    o = ord(ch)
    if o in GRAPHIC_RANGE:
        return GRAPHIC_BASE + o
    return o


def graphic_char(ch: str) -> str:
    """The one-character string that prints ``ch`` as a tileset glyph."""
    return chr(graphic_cp(ch))
