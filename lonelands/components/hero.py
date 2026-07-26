"""The Ranger's character sheet: the three attributes and the XP/level curve.

Attributes (Brawn/Wits/Will) are small modifiers on the d20 and feed the derived
combat numbers on the Fighter. Endurance (on the Fighter) is the single vitality
pool — there is no Hope, no Shadow, no skills, and no weapon proficiencies. Kills
grant XP; levels rise often, each one granting +HP, a periodic +to-hit, and a
perk point every few levels to spend on Paths (a later phase)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from lonelands import character
from lonelands.components.base_component import BaseComponent
from lonelands.dice import RollResult, roll_check

if TYPE_CHECKING:
    from lonelands.engine import Engine
    from lonelands.entity import Actor


class Hero(BaseComponent):
    parent: "Actor"

    def __init__(
        self,
        attributes: Dict[str, int],
        culture: str = "Ranger of the North",
        calling: str = "Wanderer",
        true_name: str = "",
        coins: int = 15,
    ) -> None:
        # Attributes default to +1 for any the caller omits.
        self.attributes = {a: 1 for a in character.ATTRIBUTES}
        self.attributes.update(attributes)

        self.culture = culture
        self.calling = calling
        # The Ranger's true Dúnedain name; the Bree-folk know him by his
        # nickname (the Actor's `name`), but his own kind use this.
        self.true_name = true_name

        # Purse
        self.coins = coins

        # Advancement
        self.level = 1
        self.xp = 0             # progress toward the next level
        self.xp_total = 0       # lifetime XP earned
        self.perk_points = 0    # unspent; spent on Paths in a later phase
        self._level_to_hit = 0  # periodic +to-hit accrued from levelling

    # --- Attributes -------------------------------------------------------
    @property
    def brawn(self) -> int:
        return self.attributes["Brawn"]

    @property
    def wits(self) -> int:
        return self.attributes["Wits"]

    @property
    def will(self) -> int:
        return self.attributes["Will"]

    def modifier(self, attribute: str) -> int:
        """The d20 modifier for ``attribute`` (0 if unknown)."""
        return self.attributes.get(attribute, 0)

    # --- Derived combat contributions ------------------------------------
    @property
    def attack_bonus(self) -> int:
        """The hero's contribution to a melee attack d20: Brawn plus the
        periodic to-hit earned by levelling."""
        return self.brawn + self._level_to_hit

    @property
    def defence_bonus(self) -> int:
        """The hero's contribution to Defence: Wits (wary footwork and senses)."""
        return self.wits

    # --- Loads & weariness -----------------------------------------------
    @property
    def load(self) -> int:
        total = 0
        if self.parent.equipment:
            total += self.parent.equipment.load
        if self.parent.inventory:
            total += sum(getattr(getattr(i, "equippable", None), "load", 0)
                         for i in self.parent.inventory.items)
        return total

    @property
    def is_weary(self) -> bool:
        fighter = self.parent.fighter
        if fighter is None:
            return False
        return fighter.endurance <= self.load

    # --- Checks -----------------------------------------------------------
    def check(self, mod: int, tn: int, advantage: int = 0) -> RollResult:
        """Make a d20 Check: ``d20 + mod vs tn`` (advantage/disadvantage = +1/-1).

        The single test primitive — callers supply the assembled modifier and
        TN. The roll feeds the dice tray when the player made it."""
        result = roll_check(mod, tn, advantage=advantage)
        self.engine.note_roll(result, self.parent)  # feeds the dice tray
        return result

    # --- Advancement ------------------------------------------------------
    @property
    def xp_to_next(self) -> int:
        """XP still needed for the next level (0 at the level cap)."""
        if self.level >= character.MAX_LEVEL:
            return 0
        return character.xp_to_next(self.level)

    def add_xp(self, amount: int) -> None:
        """Bank ``amount`` XP, levelling up as thresholds are crossed. Leftover
        XP carries toward the next level."""
        if amount <= 0:
            return
        self.xp += amount
        self.xp_total += amount
        while self.level < character.MAX_LEVEL:
            needed = character.xp_to_next(self.level)
            if self.xp < needed:
                break
            self.xp -= needed
            self._level_up()

    def _level_up(self) -> None:
        self.level += 1
        gains: List[str] = [f"Level {self.level}"]

        fighter = getattr(self.parent, "fighter", None)
        if fighter is not None:
            fighter.max_endurance += character.HP_PER_LEVEL
            fighter.endurance += character.HP_PER_LEVEL  # the new vigour is yours at once
            gains.append(f"+{character.HP_PER_LEVEL} Endurance")

        if self.level % character.TOHIT_EVERY == 0:
            self._level_to_hit += 1
            gains.append("+1 to-hit")

        if self.level % character.PERK_POINT_EVERY == 0:
            self.perk_points += 1
            gains.append("+1 perk point")

        self._announce(gains)

    def _announce(self, gains: List[str]) -> None:
        engine = self._engine_or_none()
        if engine is None:
            return
        from lonelands import color
        engine.message_log.add_message(
            "You grow hardier — " + ", ".join(gains) + ".", color.xp_filled
        )

    def _engine_or_none(self) -> Optional["Engine"]:
        """The live Engine, or ``None`` when the hero isn't placed on a map yet
        (so levelling stays message-free in unit tests)."""
        try:
            return self.engine
        except AttributeError:
            return None
