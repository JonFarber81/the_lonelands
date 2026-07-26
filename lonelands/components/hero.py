"""The Ranger's character sheet: the three attributes and the XP/level curve.

Attributes (Brawn/Wits/Will) are small modifiers on the d20 and feed the derived
combat numbers on the Fighter. Endurance (on the Fighter) is the single vitality
pool — there is no Hope, no Shadow, no skills, and no weapon proficiencies. Kills
grant XP; levels rise often, each one granting +HP, a periodic +to-hit, and a
perk point every few levels to spend on Paths (a later phase)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from lonelands import character, perks
from lonelands.components.base_component import BaseComponent
from lonelands.dice import RollResult, roll_check, roll_damage

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
        self.perk_points = 0    # unspent; spent on Paths (perks.py)
        self._level_to_hit = 0  # periodic +to-hit accrued from levelling

        # --- Paths & perks (issue #38) ------------------------------------
        self.perks: set = set()             # ids of owned perks (blend across Paths)
        # Per-perk active runtime: cooldown counts down each player turn (0 = ready);
        # a "primed" active waits on the next melee hit; a stance grants temp Soak
        # for a number of rounds.
        self._perk_cooldowns: Dict[str, int] = {}
        self._primed = set()                # ids of primed next-hit actives (Wrath)
        self._stance_soak = 0               # extra Soak from an active stance
        self._stance_rounds = 0             # rounds the stance persists
        # True on a turn spent *setting* a timer (activating a deed or landing a
        # primed charge) so end_player_turn doesn't shorten it by that very turn.
        self._timers_touched_this_turn = False

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
        """The hero's contribution to a melee attack d20: Brawn, the periodic
        to-hit earned by levelling, flat +to-hit perks, and any live rally bonus
        (fires while badly wounded)."""
        return (self.brawn + self._level_to_hit
                + self.perk_bonus("atk_bonus") + self.rally_atk_bonus())

    @property
    def defence_bonus(self) -> int:
        """The hero's contribution to Defence: Wits (wary footwork and senses)
        plus any Defence perks."""
        return self.wits + self.perk_bonus("defence_bonus")

    # --- Paths & perks ----------------------------------------------------
    def owned_perks(self) -> List["perks.Perk"]:
        return [perks.ALL_PERKS[pid] for pid in self.perks if pid in perks.ALL_PERKS]

    def has_perk(self, perk_id: str) -> bool:
        return perk_id in self.perks

    def can_buy(self, perk: "perks.Perk") -> bool:
        """Whether ``perk`` may be bought now: not already owned, affordable, and
        its in-Path prerequisites (and capstone gating) satisfied."""
        if perk.id in self.perks:
            return False
        if self.perk_points < perk.cost:
            return False
        return perks.prerequisites_met(perk, self.perks)

    def buy_perk(self, perk: "perks.Perk") -> bool:
        """Spend ``perk.cost`` points to take ``perk``. Returns False (buying
        nothing) if it isn't currently buyable. A +max-Endurance perk raises the
        Fighter's pool at once, exactly as a level-up does."""
        if not self.can_buy(perk):
            return False
        self.perk_points -= perk.cost
        self.perks.add(perk.id)
        if perk.max_endurance_bonus:
            fighter = getattr(self.parent, "fighter", None)
            if fighter is not None:
                fighter.max_endurance += perk.max_endurance_bonus
                fighter.endurance += perk.max_endurance_bonus  # the new vigour is yours now
        return True

    def perk_bonus(self, field: str) -> int:
        """Sum a flat passive field (e.g. ``"atk_bonus"``, ``"soak_bonus"``) over
        every owned perk."""
        return sum(getattr(p, field, 0) for p in self.owned_perks())

    # --- Low-Endurance rally trigger (read live by the Fighter) -----------
    def _rally_bonus(self, field: str) -> int:
        """Sum a rally field over owned rally perks whose Endurance threshold the
        Fighter currently sits at or below."""
        fighter = getattr(self.parent, "fighter", None)
        if fighter is None or fighter.max_endurance <= 0:
            return 0
        frac = fighter.endurance / fighter.max_endurance
        total = 0
        for p in self.owned_perks():
            if p.rally_threshold > 0 and frac <= p.rally_threshold:
                total += getattr(p, field, 0)
        return total

    def rally_atk_bonus(self) -> int:
        return self._rally_bonus("rally_atk_bonus")

    def rally_soak_bonus(self) -> int:
        return self._rally_bonus("rally_soak_bonus")

    # --- Active abilities (charges/cooldowns) -----------------------------
    def actives(self) -> List["perks.Perk"]:
        """Owned perks that carry an active ability."""
        return [p for p in self.owned_perks() if p.active is not None]

    def ability_ready(self, perk_id: str) -> bool:
        """A ready active is owned, off cooldown, and not already primed."""
        perk = perks.ALL_PERKS.get(perk_id)
        if perk is None or perk.active is None or perk_id not in self.perks:
            return False
        if self._perk_cooldowns.get(perk_id, 0) > 0:
            return False
        return perk_id not in self._primed

    def cooldown_left(self, perk_id: str) -> int:
        return self._perk_cooldowns.get(perk_id, 0)

    def activate_ability(self, perk_id: str) -> Optional[str]:
        """Fire a ready active. Returns a flavour message (or None if it can't
        fire). ``heal``/``stance`` resolve at once and start the cooldown here;
        ``wrath`` primes the next hit and starts its cooldown when that hit lands
        (see ``consume_primed`` in the melee flow)."""
        if not self.ability_ready(perk_id):
            return None
        perk = perks.ALL_PERKS[perk_id]
        spec = perk.active
        if spec.kind == "wrath":
            self._primed.add(perk_id)
            self._timers_touched_this_turn = True
            return f"You gather your fury — your next blow will strike with {spec.name}."
        if spec.kind == "heal":
            fighter = getattr(self.parent, "fighter", None)
            healed = fighter.heal(roll_damage(spec.magnitude)) if fighter else 0
            self._perk_cooldowns[perk_id] = spec.cooldown
            self._timers_touched_this_turn = True
            return f"You draw a Second Wind and recover {healed} Endurance."
        if spec.kind == "stance":
            self._stance_soak = max(self._stance_soak, spec.soak)
            self._stance_rounds = max(self._stance_rounds, spec.duration)
            self._perk_cooldowns[perk_id] = spec.cooldown
            self._timers_touched_this_turn = True
            return f"You set your feet — {spec.name}! (+{spec.soak} Soak)"
        return None

    def is_primed(self, perk_id: str) -> bool:
        """Whether ``perk_id``'s next-hit active is primed and waiting to spend."""
        return perk_id in self._primed

    def consume_primed(self) -> int:
        """Called when a melee hit lands: pay out and clear every primed next-hit
        active, returning the total bonus damage, and start their cooldowns."""
        if not self._primed:
            return 0
        bonus = 0
        for pid in list(self._primed):
            perk = perks.ALL_PERKS.get(pid)
            if perk is None or perk.active is None:
                continue
            bonus += roll_damage(perk.active.magnitude)
            self._perk_cooldowns[pid] = perk.active.cooldown
        self._primed.clear()
        self._timers_touched_this_turn = True  # this turn set the Wrath cooldown
        return bonus

    def on_kill(self) -> None:
        """Called from ``Fighter.die`` when this hero slays a foe. Reaver's
        Instinct (Swift Wrath capstone) readies every active deed at once."""
        if any(p.readies_actives_on_kill for p in self.owned_perks()):
            self._perk_cooldowns.clear()

    @property
    def stance_soak(self) -> int:
        """Extra Soak from an active defensive stance (0 when none is up)."""
        return self._stance_soak if self._stance_rounds > 0 else 0

    @property
    def ambush_advantage(self) -> bool:
        """Whether any owned Hidden Path perk grants advantage on a first strike."""
        return any(p.ambush_advantage for p in self.owned_perks())

    def end_player_turn(self) -> None:
        """Close out one player turn (called once per action by input_handlers).

        A turn spent *setting* a timer — activating a deed, or landing a primed
        Wrath charge — does not also advance timers, so a freshly-set cooldown or
        stance keeps its full authored length. Any other turn ticks them down."""
        if self._timers_touched_this_turn:
            self._timers_touched_this_turn = False
            return
        self.tick_perks()

    def tick_perks(self) -> None:
        """Advance per-perk runtime by one player turn: cooldowns count down and
        any stance decays. The raw per-turn step used by ``end_player_turn``."""
        for pid, remaining in list(self._perk_cooldowns.items()):
            if remaining > 0:
                self._perk_cooldowns[pid] = remaining - 1
        if self._stance_rounds > 0:
            self._stance_rounds -= 1
            if self._stance_rounds <= 0:
                self._stance_soak = 0

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
