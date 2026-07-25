"""The player's One Ring character sheet: attributes, skills, proficiencies,
Hope, and the derived Weary state — plus the XP/advancement bookkeeping."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

from lonelands import tor
from lonelands.components.base_component import BaseComponent
from lonelands.dice import RollResult, skill_check

if TYPE_CHECKING:
    from lonelands.entity import Actor


class Hero(BaseComponent):
    parent: "Actor"

    def __init__(
        self,
        attributes: Dict[str, int],
        skills: Dict[str, int],
        proficiencies: Dict[str, int],
        max_hope: int = 12,
        valour: int = 1,
        wisdom: int = 1,
        culture: str = "Ranger of the North",
        calling: str = "Wanderer",
        true_name: str = "",
    ) -> None:
        self.attributes = dict(attributes)
        self.skills = {s: 0 for s in tor.ALL_SKILLS}
        self.skills.update(skills)
        self.proficiencies = {p: 0 for p in tor.PROFICIENCIES}
        self.proficiencies.update(proficiencies)

        self.max_hope = max_hope
        self._hope = max_hope
        self.valour = valour
        self.wisdom = wisdom
        self.culture = culture
        self.calling = calling
        # The Ranger's true Dúnedain name; the Bree-folk know him by his
        # nickname (the Actor's `name`), but his own kind use this.
        self.true_name = true_name

        # Purse
        self.coins = 15

        # Advancement
        self.xp = 0
        self.xp_total = 0
        self.shadow = 0  # Shadow points; miserable when >= wisdom threshold

    # --- Hope -------------------------------------------------------------
    @property
    def hope(self) -> int:
        return self._hope

    @hope.setter
    def hope(self, value: int) -> None:
        self._hope = max(0, min(self.max_hope, value))

    def spend_hope(self, amount: int = 1) -> bool:
        if self._hope < amount:
            return False
        self._hope -= amount
        return True

    def restore_hope(self, amount: int) -> int:
        before = self._hope
        self.hope = self._hope + amount
        return self._hope - before

    @property
    def is_miserable(self) -> bool:
        return self.shadow >= self.max_hope

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

    # --- Tests ------------------------------------------------------------
    def attr_tn(self, attribute: str) -> int:
        return tor.attribute_tn(self.attributes.get(attribute, 3))

    def skill_tn(self, skill: str) -> int:
        return self.attr_tn(tor.SKILL_TO_ATTR[skill])

    def test_skill(
        self,
        skill: str,
        tn: Optional[int] = None,
        favoured: int = 0,
        modifier: int = 0,
        weary: Optional[bool] = None,
    ) -> RollResult:
        rank = self.skills.get(skill, 0)
        target = tn if tn is not None else self.skill_tn(skill)
        if weary is None:
            weary = self.is_weary
        result = skill_check(target, rank, favoured=favoured, weary=weary, modifier=modifier)
        self.engine.note_roll(result, self.parent)  # feeds the dice tray
        return result

    def test_attribute(
        self, attribute: str, tn: Optional[int] = None, favoured: int = 0, modifier: int = 0
    ) -> RollResult:
        target = tn if tn is not None else self.attr_tn(attribute)
        # Bare attribute test: feat die + no success dice.
        result = skill_check(target, 0, favoured=favoured, weary=self.is_weary, modifier=modifier)
        self.engine.note_roll(result, self.parent)  # feeds the dice tray
        return result

    # --- Advancement ------------------------------------------------------
    def add_xp(self, amount: int) -> None:
        self.xp += amount
        self.xp_total += amount

    def cost_to_raise_skill(self, skill: str) -> int:
        next_rank = self.skills.get(skill, 0) + 1
        return next_rank * 3  # simple escalating cost

    def cost_to_raise_prof(self, prof: str) -> int:
        next_rank = self.proficiencies.get(prof, 0) + 1
        return next_rank * 4

    def raise_skill(self, skill: str) -> bool:
        if self.skills.get(skill, 0) >= 6:
            return False
        cost = self.cost_to_raise_skill(skill)
        if self.xp < cost:
            return False
        self.xp -= cost
        self.skills[skill] += 1
        return True

    def raise_prof(self, prof: str) -> bool:
        if self.proficiencies.get(prof, 0) >= 6:
            return False
        cost = self.cost_to_raise_prof(prof)
        if self.xp < cost:
            return False
        self.xp -= cost
        self.proficiencies[prof] += 1
        return True
