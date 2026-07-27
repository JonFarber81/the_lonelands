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
        kind: str = "",             # foe kind for weapon bonus-vs ("orc", "beast"…)
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
        self.kind = kind
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
        self.endurance -= self._scale_incoming(amount)

    def _scale_incoming(self, amount: int) -> int:
        """Apply the run's difficulty to damage the *player* takes (foes are
        never scaled). A real blow never softens below 1; the result is a whole
        number of Endurance."""
        if amount <= 0:
            return amount
        gm = getattr(self.parent, "gamemap", None)
        engine = getattr(gm, "engine", None)
        if engine is None or engine.player is not self.parent:
            return amount
        from lonelands import config
        key = getattr(engine, "difficulty", config.DEFAULT_DIFFICULTY)
        mult = config.difficulty_multiplier(key)
        if mult == 1.0:
            return amount
        return max(1, round(amount * mult))

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
        hero = getattr(self.parent, "hero", None)
        if hero is not None:
            bonus += hero.defence_bonus  # Wits sharpens the hero's Defence
        return self.base_defence + bonus

    @property
    def attack_bonus(self) -> int:
        """The bonus added to this fighter's d20 attack roll: its base, the
        wielded weapon's +hit, plus (for the hero) the attribute- and level-
        derived to-hit (Brawn + periodic +to-hit). Foes carry no Hero, so they
        use base + weapon alone."""
        base = self.base_attack_bonus
        weapon = self._weapon
        if weapon is not None:
            base += weapon.attack_bonus
        hero = getattr(self.parent, "hero", None)
        if hero is not None:
            base += hero.attack_bonus
        return base

    @property
    def pierce(self) -> int:
        """Soak the wielded weapon ignores on a landed blow (0 with no weapon)."""
        weapon = self._weapon
        return weapon.pierce if weapon is not None else 0

    def bonus_vs_damage(self, target: "Actor") -> int:
        """Extra damage the wielded weapon deals against ``target`` when its
        bonus-vs kind matches the target's ``kind`` (0 otherwise)."""
        weapon = self._weapon
        if weapon is None or not weapon.bonus_vs:
            return 0
        tf = getattr(target, "fighter", None)
        if tf is not None and tf.kind == weapon.bonus_vs:
            return weapon.bonus_vs_damage
        return 0

    @property
    def soak(self) -> int:
        eq = getattr(self.parent, "equipment", None)
        bonus = eq.soak_bonus if eq else 0
        hero = getattr(self.parent, "hero", None)
        if hero is not None:
            # Long Watch nodes: flat Soak (Iron Skin) and an active defensive
            # stance (Hold the Line). The rally term is dormant — no ported node
            # grants it yet (a future Kindled Heart Path will).
            bonus += hero.node_bonus("soak_bonus")
            bonus += hero.rally_soak_bonus()
            bonus += hero.stance_soak
        return self.base_soak + bonus

    @property
    def crit_face(self) -> int:
        """The lowest natural d20 face that scores a Critical (normally 20; the
        Long Watch's Reaver capstone widens the range downward). Read by
        MeleeAction."""
        hero = getattr(self.parent, "hero", None)
        widen = hero.node_bonus("crit_range") if hero is not None else 0
        return 20 - max(0, widen)

    @property
    def melee_damage_bonus(self) -> int:
        """Flat damage added to this fighter's melee blows (the Reaver branch)."""
        hero = getattr(self.parent, "hero", None)
        return hero.node_bonus("melee_damage_bonus") if hero is not None else 0

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

    # --- Ranged: a parallel attack path keyed off Wits (ADR 0006) ---------
    # Melee reads the `weapon` slot above; a Shot reads the `ranged` slot below.
    # Both stay equipped at once — the action, not a swap, picks the weapon.
    @property
    def _ranged(self):
        eq = getattr(self.parent, "equipment", None)
        if eq is not None and eq.ranged is not None:
            return eq.ranged.equippable
        return None

    @property
    def has_ranged_weapon(self) -> bool:
        return self._ranged is not None

    @property
    def ranged_weapon_name(self) -> str:
        eq = getattr(self.parent, "equipment", None)
        if eq is not None and eq.ranged is not None:
            return eq.ranged.name
        return "no bow"

    @property
    def ranged_attack_bonus(self) -> int:
        """The bonus added to a Shot's d20: the bow's +hit plus (for the hero)
        Wits + level to-hit + Far Shot perks. No bow means no shot — 0."""
        bow = self._ranged
        if bow is None:
            return 0
        base = bow.attack_bonus
        hero = getattr(self.parent, "hero", None)
        if hero is not None:
            base += hero.ranged_attack_bonus
        return base

    @property
    def ranged_damage(self) -> Union[int, str]:
        """The bow's damage dice (0 with no bow)."""
        bow = self._ranged
        return bow.damage if bow is not None else 0

    @property
    def ranged_damage_bonus(self) -> int:
        """Flat damage the Far Shot Path adds to a Shot (0 for a foe / no hero)."""
        hero = getattr(self.parent, "hero", None)
        return hero.ranged_damage_bonus if hero is not None else 0

    @property
    def effective_range(self) -> int:
        """Tiles a Shot carries with no falloff (the bow's stat; 0 with no bow)."""
        bow = self._ranged
        return bow.effective_range if bow is not None else 0

    def range_penalty(self, distance: int) -> int:
        """The to-hit penalty for a Shot at ``distance`` tiles (Chebyshev): none
        within the bow's effective range, then −1 per 3 tiles beyond it (ADR
        0006). Returned as a positive number the caller subtracts from the roll."""
        excess = distance - self.effective_range
        if excess <= 0:
            return 0
        return (excess + 2) // 3

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
            if engine.player.hero is not None:
                if self.xp_reward:
                    engine.player.hero.add_xp(self.xp_reward)
                    engine.message_log.add_message(
                        f"You gain {self.xp_reward} experience.", color.xp_filled
                    )
                engine.player.hero.on_kill()  # Reaver's Instinct readies deeds
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
                from lonelands import affixes
                dropped = outcome.spawn(engine.game_map, self.parent.x, self.parent.y)
                # Gear a foe drops rolls its own rarity + affixes (ADR 0005, #40);
                # coins and trade-goods are passed over untouched.
                affixes.apply_affixes(dropped)
                engine.message_log.add_message(
                    f"The {foe_name} leaves {dropped.name} behind.", color.item_c
                )
