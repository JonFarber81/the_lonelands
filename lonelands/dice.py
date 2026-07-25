"""The One Ring dice engine.

A test rolls one **Feat die** (d12) plus a number of **Success dice** (d6) equal
to a skill/proficiency rank, sums them, and compares to a Target Number (TN).

Special faces:
  * Feat die 11  -> the Eye of Sauron: counts as 0 and invites ill fortune.
  * Feat die 12  -> the Gandalf rune (G): an automatic success regardless of TN.
  * Success die 6 -> a tengwar rune (great-success marker).

Conditions:
  * Favoured  (+1) rolls two Feat dice, keeps the higher; ill-favoured keeps lower.
  * Weary      makes Success dice showing 1-3 count as 0.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List

rng = random.Random()


def set_seed(seed: int) -> None:
    rng.seed(seed)


EYE = 11        # feat-die face value that means the Eye of Sauron
GANDALF = 12    # feat-die face value that means the Gandalf rune


@dataclass
class RollResult:
    total: int
    tn: int
    feat: int                 # the counted feat-die value (0 for Eye/Gandalf-as-0 shown separately)
    feat_raw: int             # the actual d12 face kept (1..12)
    success_dice: List[int] = field(default_factory=list)
    tengwar: int = 0          # number of 6s rolled on success dice
    is_gandalf: bool = False
    is_eye: bool = False
    weary: bool = False

    @property
    def is_success(self) -> bool:
        if self.is_gandalf:
            return True
        return self.total >= self.tn

    @property
    def is_great(self) -> bool:
        """Great success: a success with at least one tengwar (or the Gandalf rune)."""
        return self.is_success and (self.tengwar >= 1 or self.is_gandalf)

    @property
    def is_extraordinary(self) -> bool:
        return self.is_success and self.tengwar >= 2

    @property
    def quality(self) -> str:
        if not self.is_success:
            return "failure"
        if self.is_extraordinary:
            return "extraordinary"
        if self.is_great:
            return "great"
        return "success"

    def describe(self) -> str:
        if self.is_gandalf:
            feat_str = "G"
        elif self.is_eye:
            feat_str = "Eye"
        else:
            feat_str = str(self.feat_raw)
        dice = "+".join(str(d) for d in self.success_dice) if self.success_dice else "-"
        return f"[{feat_str}|{dice}={self.total} vs {self.tn}]"


def _roll_feat(favoured: int) -> int:
    """favoured: +1 favoured (keep high), -1 ill-favoured (keep low), 0 normal."""
    a = rng.randint(1, 12)
    if favoured == 0:
        return a
    b = rng.randint(1, 12)
    return max(a, b) if favoured > 0 else min(a, b)


def skill_check(
    tn: int,
    rank: int,
    favoured: int = 0,
    weary: bool = False,
    modifier: int = 0,
) -> RollResult:
    """Roll a skill/attribute test. `rank` = number of success dice (0..6+)."""
    feat_raw = _roll_feat(favoured)
    is_gandalf = feat_raw == GANDALF
    is_eye = feat_raw == EYE
    feat_value = 0 if (is_gandalf or is_eye) else feat_raw

    dice: List[int] = []
    tengwar = 0
    subtotal = 0
    for _ in range(max(0, rank)):
        d = rng.randint(1, 6)
        dice.append(d)
        if d == 6:
            tengwar += 1
        counted = 0 if (weary and d <= 3) else d
        subtotal += counted

    total = feat_value + subtotal + modifier
    return RollResult(
        total=total,
        tn=tn,
        feat=feat_value,
        feat_raw=feat_raw,
        success_dice=dice,
        tengwar=tengwar,
        is_gandalf=is_gandalf,
        is_eye=is_eye,
        weary=weary,
    )


def roll_dice(number: int, sides: int) -> int:
    return sum(rng.randint(1, sides) for _ in range(number))
