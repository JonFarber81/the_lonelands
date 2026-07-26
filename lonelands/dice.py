"""The d20 resolution core.

Every action is a **Check**: roll a d20, add a modifier, and compare the total
to a Target Number (TN). Combat is the same primitive — an attack roll of
``d20 + attack bonus vs the foe's Defence``.

Special faces:
  * natural 20 -> a **Critical**: an automatic success (an auto-hit in combat)
    that also carries bonus damage / a Bleed.
  * natural 1  -> a **Fumble**: an automatic failure (an auto-miss).

Advantage / Disadvantage roll two d20 and keep the higher / lower face.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import List, Optional, Union

rng = random.Random()


def set_seed(seed: int) -> None:
    rng.seed(seed)


CRIT = 20  # natural face that means a Critical
FUMBLE = 1  # natural face that means a Fumble


@dataclass
class RollResult:
    die: int                 # the kept d20 face (1..20)
    mod: int                 # the modifier added to the die
    tn: int                  # target number the total is measured against
    dice: List[int] = field(default_factory=list)  # every d20 rolled (2 under adv/dis)
    damage: Optional[int] = None  # Endurance dealt, once a combat hit resolves it

    @property
    def total(self) -> int:
        return self.die + self.mod

    @property
    def is_crit(self) -> bool:
        return self.die == CRIT

    @property
    def is_fumble(self) -> bool:
        return self.die == FUMBLE

    @property
    def is_success(self) -> bool:
        if self.is_crit:
            return True
        if self.is_fumble:
            return False
        return self.total >= self.tn

    def describe(self) -> str:
        if self.is_crit:
            tag = "CRIT"
        elif self.is_fumble:
            tag = "FUMBLE"
        else:
            tag = "hit" if self.is_success else "miss"
        return f"[d20={self.die}{self.mod:+d}={self.total} vs {self.tn} {tag}]"


def roll_check(mod: int, tn: int, advantage: int = 0) -> RollResult:
    """Roll ``d20 + mod`` against ``tn``.

    ``advantage``: +1 rolls two d20 and keeps the higher, -1 keeps the lower,
    0 rolls a single die.
    """
    a = rng.randint(1, 20)
    dice = [a]
    if advantage > 0:
        b = rng.randint(1, 20)
        dice.append(b)
        die = max(a, b)
    elif advantage < 0:
        b = rng.randint(1, 20)
        dice.append(b)
        die = min(a, b)
    else:
        die = a
    return RollResult(die=die, mod=mod, tn=tn, dice=dice)


def roll_dice(number: int, sides: int) -> int:
    return sum(rng.randint(1, sides) for _ in range(number))


_DICE_RE = re.compile(r"^\s*(\d+)d(\d+)\s*([+-]\s*\d+)?\s*$", re.IGNORECASE)


def roll_damage(spec: Union[int, str]) -> int:
    """Roll a damage expression. Accepts a flat integer or dice notation like
    ``"1d6"`` / ``"2d4+1"``. Never returns below 0."""
    if isinstance(spec, int):
        return max(0, spec)
    m = _DICE_RE.match(spec)
    if not m:
        raise ValueError(f"bad damage spec: {spec!r}")
    number, sides, bonus = int(m.group(1)), int(m.group(2)), m.group(3)
    total = roll_dice(number, sides)
    if bonus:
        total += int(bonus.replace(" ", ""))
    return max(0, total)
