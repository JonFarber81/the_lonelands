"""The Ranger's character model: the three attributes and the level/XP curve.

Attributes are small modifiers added to a d20 Check (higher is better). There
are no skills and no weapon proficiencies — specialisation lives in perks (a
later phase). Levelling is frequent and mostly automatic: each level grants
+HP, a periodic +to-hit, and a perk point every few levels. Data-only; the live
sheet lives on the Hero component."""
from __future__ import annotations

# The three attributes. Each is a small modifier added to a d20 Check.
#   Brawn — melee hit/damage, HP, athletics
#   Wits  — ranged, Defence, stealth, senses
#   Will  — morale, social, healing, Path abilities
ATTRIBUTES = ("Brawn", "Wits", "Will")

# --- Level curve ----------------------------------------------------------
MAX_LEVEL = 30
HP_PER_LEVEL = 4        # +max Endurance every level
TOHIT_EVERY = 2         # +1 attack bonus every this many levels (2, 4, 6, …)
PERK_POINT_EVERY = 3    # +1 perk point every this many levels (3, 6, 9, …)


def xp_to_next(level: int) -> int:
    """XP needed to advance *from* ``level`` to the next. A gentle linear ramp:
    early levels come thick and fast, later ones ask a little more."""
    return 20 + 10 * (level - 1)
