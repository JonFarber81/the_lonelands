"""Combat component shared by the player and all creatures.

Endurance is the vitality pool (reaching 0 fells the combatant). Combat uses the
TOR feat+success dice: an attack is a proficiency test against the defender's
Parry-derived TN; a *great* success threatens a Piercing Blow, which forces a
Protection test against the weapon's Injury rating or inflicts a Wound."""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple, Union

from lonelands import color
from lonelands.components.base_component import BaseComponent
from lonelands.dice import rng, skill_check
from lonelands.render_order import RenderOrder

if TYPE_CHECKING:
    from lonelands.entity import Actor, Item


class Coins:
    """A loot outcome that pays coins straight into the purse: a whole-number
    range [lo, hi] (inclusive)."""

    __slots__ = ("lo", "hi")

    def __init__(self, lo: int, hi: Optional[int] = None) -> None:
        self.lo = lo
        self.hi = lo if hi is None else hi


# A single roll is a weighted list of outcomes — each outcome a `Coins` payout,
# an `Item` template to drop, or `None` (nothing). A loot table is a list of such
# independent rolls; a kill may resolve several.
Outcome = Union[Coins, "Item", None]
Roll = Sequence[Tuple[Outcome, int]]
LootTable = List[Roll]


def resolve_roll(roll: Roll) -> Outcome:
    """Pick one outcome from a single weighted roll."""
    total = sum(w for _, w in roll)
    r = rng.uniform(0, total)
    upto = 0.0
    for outcome, weight in roll:
        upto += weight
        if r <= upto:
            return outcome
    return roll[-1][0]


class Fighter(BaseComponent):
    parent: "Actor"

    def __init__(
        self,
        endurance: int,
        defence: int,          # base TN an attacker must meet to hit
        prowess: int,          # natural attack success dice (unarmed / monster)
        damage: int,           # natural weapon damage
        *,
        attack: int = 12,      # TN the player's Parry test must meet when this foe strikes
        edge: int = 1,
        injury: int = 14,
        protection: int = 0,   # natural armour success dice
        attack_desc: str = "strikes",
        xp_reward: int = 0,
        corpse_char: str = "%",
        loot: Optional[LootTable] = None,
    ) -> None:
        self.max_endurance = endurance
        self._endurance = endurance
        self.base_defence = defence
        self.base_attack = attack
        self.base_prowess = prowess
        self.base_damage = damage
        self.base_edge = edge
        self.base_injury = injury
        self.base_protection = protection
        self.attack_desc = attack_desc
        self.xp_reward = xp_reward
        self.corpse_char = corpse_char
        self.loot = loot
        self.wounded = False
        self._dead = False

    # --- Vitals -----------------------------------------------------------
    @property
    def endurance(self) -> int:
        return self._endurance

    @endurance.setter
    def endurance(self, value: int) -> None:
        self._endurance = max(0, min(value, self.max_endurance))
        if self._endurance == 0 and not self._dead:
            self._dead = True
            self.die()

    def heal(self, amount: int) -> int:
        if self._endurance >= self.max_endurance:
            return 0
        before = self._endurance
        self.endurance = self._endurance + amount
        return self._endurance - before

    def take_damage(self, amount: int) -> None:
        self.endurance -= amount

    # --- Derived combat stats --------------------------------------------
    @property
    def _weapon(self):
        eq = getattr(self.parent, "equipment", None)
        if eq is not None and eq.weapon is not None:
            return eq.weapon.equippable
        return None

    @property
    def defence(self) -> int:
        eq = getattr(self.parent, "equipment", None)
        bonus = eq.defence_bonus if eq else 0
        penalty = 2 if self.wounded else 0
        return self.base_defence + bonus - penalty

    @property
    def attack(self) -> int:
        """The TN the player's Parry test must meet to turn this foe's blow
        aside. A wounded foe strikes less surely."""
        penalty = 2 if self.wounded else 0
        return self.base_attack - penalty

    @property
    def protection(self) -> int:
        eq = getattr(self.parent, "equipment", None)
        bonus = eq.protection_bonus if eq else 0
        return self.base_protection + bonus

    @property
    def prowess(self) -> int:
        weapon = self._weapon
        hero = getattr(self.parent, "hero", None)
        base = self.base_prowess
        if weapon is not None and hero is not None and weapon.proficiency:
            base = hero.proficiencies.get(weapon.proficiency, 0)
        if self.wounded:
            base = max(0, base - 1)
        return base

    @property
    def damage(self) -> int:
        weapon = self._weapon
        return weapon.damage if weapon is not None else self.base_damage

    @property
    def edge(self) -> int:
        weapon = self._weapon
        return weapon.edge if weapon is not None else self.base_edge

    @property
    def injury(self) -> int:
        weapon = self._weapon
        return weapon.injury if weapon is not None else self.base_injury

    @property
    def weapon_name(self) -> str:
        eq = getattr(self.parent, "equipment", None)
        if eq is not None and eq.weapon is not None:
            return eq.weapon.name
        return "bare hands"

    # --- Resolution -------------------------------------------------------
    def protection_test(self, injury_tn: int) -> bool:
        result = skill_check(injury_tn, self.protection)
        self.engine.note_roll(result, self.parent)  # tray shows the player's saves
        return result.is_success

    def inflict_wound(self) -> bool:
        """Returns True if the wound is mortal."""
        if self.wounded:
            return True
        self.wounded = True
        return False

    def die(self) -> None:
        engine = self.engine
        if engine.player is self.parent:
            death_message = "You fall, and the long road of the Dúnedain ends here."
            death_color = color.player_die
            engine.message_log.add_message(death_message, death_color)
            from lonelands import input_handlers
            engine.event_handler = input_handlers.GameOverEventHandler(engine)
        else:
            death_message = f"The {self.parent.name} is slain."
            death_color = color.enemy_die
            engine.message_log.add_message(death_message, death_color)
            if engine.player.hero is not None and self.xp_reward:
                engine.player.hero.add_xp(self.xp_reward)
                engine.message_log.add_message(
                    f"You gain {self.xp_reward} experience.", color.xp_filled
                )
            engine.quest_log.notify_kill(self.parent.name, engine)
            self._resolve_loot()

        self.parent.char = self.corpse_char
        self.parent.color = (0x7A, 0x30, 0x2A)
        self.parent.blocks_movement = False
        self.parent.ai = None
        self.parent.name = f"remains of {self.parent.name}"
        self.parent.render_order = RenderOrder.CORPSE

    def _resolve_loot(self) -> None:
        """Resolve this creature's loot table (called while the corpse still
        carries its living name and position). Coins go straight to the purse;
        trade-goods spawn onto the corpse tile to be picked up."""
        if not self.loot:
            return
        engine = self.engine
        hero = engine.player.hero
        foe_name = self.parent.name
        for roll in self.loot:
            outcome = resolve_roll(roll)
            if outcome is None:
                continue
            if isinstance(outcome, Coins):
                amount = rng.randint(outcome.lo, outcome.hi)
                if amount <= 0:
                    continue
                if hero is not None:
                    hero.coins += amount
                engine.message_log.add_message(
                    f"You take {amount} coins from the {foe_name}.", color.gold_c
                )
            else:  # an Item template to drop on the corpse tile
                outcome.spawn(engine.game_map, self.parent.x, self.parent.y)
                engine.message_log.add_message(
                    f"The {foe_name} leaves {outcome.name} behind.", color.item_c
                )
