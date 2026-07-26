"""Combat component shared by the player and all creatures.

Endurance is the vitality pool (reaching 0 fells the combatant). Combat uses the
d20 core: an attack is ``d20 + attack bonus vs the defender's Defence``; on a hit
the attacker rolls weapon damage and subtracts the defender's Soak. A natural 20
is a Critical (auto-hit, bonus damage, and a Bleed); a natural 1 is a Fumble
(auto-miss). Bleed is a damage-over-time status ticked once per round."""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple, Union

from lonelands import color
from lonelands.components.base_component import BaseComponent
from lonelands.dice import rng
from lonelands.render_order import RenderOrder

# Bleed: each remaining stack ticks this much Endurance at the start of the
# bearer's round, then decays by one. Crits (and heavy foes) apply fresh stacks.
BLEED_DAMAGE = 2
CRIT_BLEED = 2  # Bleed stacks a Critical opens on the target

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
        defence: int,               # base Defence: the TN an attacker must hit
        attack_bonus: int,          # base bonus added to this fighter's d20 attack
        damage: Union[int, str],    # natural weapon damage (flat or dice notation)
        *,
        soak: int = 0,              # armour Soak subtracted from incoming damage
        bleed_on_hit: int = 0,      # Bleed stacks a heavy foe inflicts on any hit
        attack_desc: str = "strikes",
        xp_reward: int = 0,
        corpse_char: str = "%",
        loot: Optional[LootTable] = None,
    ) -> None:
        self.max_endurance = endurance
        self._endurance = endurance
        self.base_defence = defence
        self.base_attack_bonus = attack_bonus
        self.base_damage = damage
        self.base_soak = soak
        self.bleed_on_hit = bleed_on_hit
        self.attack_desc = attack_desc
        self.xp_reward = xp_reward
        self.corpse_char = corpse_char
        self.loot = loot
        self.bleed = 0  # remaining Bleed stacks
        self._dead = False

    # --- Vitals -----------------------------------------------------------
    @property
    def dead(self) -> bool:
        """True once this fighter has been slain (its actor is now a corpse)."""
        return self._dead

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
        return self.base_defence + bonus

    @property
    def attack_bonus(self) -> int:
        """The bonus added to this fighter's d20 attack roll. (Attribute- and
        perk-derived bonuses land in Phase 2; for now it is the base value.)"""
        return self.base_attack_bonus

    @property
    def soak(self) -> int:
        eq = getattr(self.parent, "equipment", None)
        bonus = eq.soak_bonus if eq else 0
        return self.base_soak + bonus

    @property
    def damage(self) -> Union[int, str]:
        weapon = self._weapon
        return weapon.damage if weapon is not None else self.base_damage

    @property
    def weapon_name(self) -> str:
        eq = getattr(self.parent, "equipment", None)
        if eq is not None and eq.weapon is not None:
            return eq.weapon.name
        return "bare hands"

    # --- Statuses ---------------------------------------------------------
    def apply_bleed(self, stacks: int) -> None:
        """Add Bleed stacks (each ticks ``BLEED_DAMAGE`` at the bearer's round)."""
        if stacks > 0:
            self.bleed += stacks

    def tick_bleed(self) -> int:
        """Bleed for one round: deal ``BLEED_DAMAGE`` and decay a stack. Returns
        the Endurance lost (0 if not bleeding)."""
        if self.bleed <= 0 or self._dead:
            return 0
        self.bleed -= 1
        before = self._endurance
        self.take_damage(BLEED_DAMAGE)
        return before - self._endurance

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
