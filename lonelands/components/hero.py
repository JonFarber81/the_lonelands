"""The Ranger's character sheet: the three attributes and the XP/level curve.

Attributes (Brawn/Wits/Will) are small modifiers on the d20 and feed the derived
combat numbers on the Fighter. Endurance (on the Fighter) is the single vitality
pool — there is no Hope, no Shadow, no skills, and no weapon proficiencies. Kills
grant XP; levels rise often, each one granting +HP and a periodic +to-hit.

Paths (ADR 0011) are a **committed skill-tree**: level 1 is **pathless**; from
level 2 every level grants **one Path point** and the player **commits to a
single Path**, into whose tree all points thereafter are spent (nodes and
ranks). The commit is permanent, and buys outside the committed Path are
rejected — see :meth:`commit_path` / :meth:`can_buy`."""
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
        self.path_points = 0    # unspent; spent on the committed Path (perks.py)
        self._level_to_hit = 0  # periodic +to-hit accrued from levelling

        # --- Paths & nodes (ADR 0011) -------------------------------------
        # The committed Path: None while pathless (level 1). Set once, forever,
        # at level 2 (commit_path); every Path point after goes into its tree.
        self.path: Optional[str] = None
        self.nodes: Dict[str, int] = {}     # owned node id -> current rank (>=1)
        self.points_in_path = 0             # Path points sunk in (the tier gate)
        # Per-node active runtime: cooldown counts down each player turn (0 = ready);
        # a "primed" active waits on the next melee hit; a stance grants temp Soak
        # for a number of rounds.
        self._node_cooldowns: Dict[str, int] = {}
        self._primed = set()                # ids of primed next-hit actives (Wrath)
        self._stance_soak = 0               # extra Soak from an active stance
        self._stance_rounds = 0             # rounds the stance persists
        # True on a turn spent *setting* a timer (activating a deed or landing a
        # primed charge) so end_player_turn doesn't shorten it by that very turn.
        self._timers_touched_this_turn = False

    # --- Attributes -------------------------------------------------------
    # Each attribute is the hero's innate score plus any +attribute lent by worn
    # accessories (a token of +Wits sharpens Defence, +Brawn his blows, and so on).
    def _equip_attr(self, attribute: str) -> int:
        eq = getattr(self.parent, "equipment", None)
        return eq.attribute_bonus(attribute) if eq is not None else 0

    @property
    def brawn(self) -> int:
        return self.attributes["Brawn"] + self._equip_attr("Brawn")

    @property
    def wits(self) -> int:
        return self.attributes["Wits"] + self._equip_attr("Wits")

    @property
    def will(self) -> int:
        return self.attributes["Will"] + self._equip_attr("Will")

    def modifier(self, attribute: str) -> int:
        """The d20 modifier for ``attribute`` (0 if unknown), including any
        +attribute from worn accessories."""
        return self.attributes.get(attribute, 0) + self._equip_attr(attribute)

    # --- Derived combat contributions ------------------------------------
    @property
    def attack_bonus(self) -> int:
        """The hero's contribution to a melee attack d20: Brawn, the periodic
        to-hit earned by levelling, flat +to-hit nodes, and any live rally bonus
        (fires while badly wounded)."""
        return (self.brawn + self._level_to_hit
                + self.node_bonus("atk_bonus") + self.rally_atk_bonus())

    @property
    def defence_bonus(self) -> int:
        """The hero's contribution to Defence: Wits (wary footwork and senses)
        plus any Defence nodes."""
        return self.wits + self.node_bonus("defence_bonus")

    @property
    def ranged_attack_bonus(self) -> int:
        """The hero's contribution to a Shot's d20 (ADR 0006): Wits (the aimed
        eye, not Brawn), the same periodic level to-hit melee earns, and the Far
        Shot Path's flat ranged to-hit nodes. The bow's own +hit is added on the
        Fighter, mirroring how melee adds the weapon's +hit there."""
        return self.wits + self._level_to_hit + self.node_bonus("ranged_bonus")

    @property
    def ranged_damage_bonus(self) -> int:
        """Flat damage the Far Shot Path adds to a Shot (Fletcher's Eye/Deadeye)."""
        return self.node_bonus("ranged_damage_bonus")

    # --- Paths & nodes (ADR 0011) -----------------------------------------
    def owned_nodes(self) -> List["perks.Node"]:
        """The Nodes the hero owns (rank ≥ 1), in no particular order."""
        return [perks.ALL_NODES[nid] for nid in self.nodes if nid in perks.ALL_NODES]

    def has_node(self, node_id: str) -> bool:
        return self.nodes.get(node_id, 0) >= 1

    def rank_of(self, node_id: str) -> int:
        """Current rank of ``node_id`` (0 if unowned)."""
        return self.nodes.get(node_id, 0)

    def commit_path(self, path_id: str) -> bool:
        """Commit — **permanently** — to a single Path. Legal only while pathless
        (the one-time level-2 choice); returns False if a Path is already
        committed or ``path_id`` is unknown. The chooser UI is Phase 2; this is
        the rule it will drive."""
        if self.path is not None:
            return False
        if path_id not in perks.PATHS_BY_ID:
            return False
        self.path = path_id
        return True

    def can_buy(self, node: "perks.Node") -> bool:
        """Whether ``node`` (its next rank) may be bought now: a Path is
        committed and it is *this* Path's, the rank cap isn't reached, the cost is
        affordable, and both the points-in-Path tier gate and the parent-edge are
        satisfied."""
        if self.path is None or node.path != self.path:
            return False
        if self.nodes.get(node.id, 0) >= node.max_rank:
            return False
        if self.path_points < node.cost:
            return False
        if not perks.tier_unlocked(node, self.points_in_path):
            return False
        return perks.parent_met(node, self.nodes.keys())

    def buy_node(self, node: "perks.Node") -> bool:
        """Spend ``node.cost`` Path points to take ``node`` (or its next rank).
        Returns False (buying nothing) if it isn't currently buyable. A
        +max-Endurance node raises the Fighter's pool at once, per rank, exactly
        as a level-up does."""
        if not self.can_buy(node):
            return False
        self.path_points -= node.cost
        self.points_in_path += node.cost
        self.nodes[node.id] = self.nodes.get(node.id, 0) + 1
        if node.max_endurance_bonus:
            fighter = getattr(self.parent, "fighter", None)
            if fighter is not None:
                fighter.max_endurance += node.max_endurance_bonus
                fighter.endurance += node.max_endurance_bonus  # the new vigour is yours now
        return True

    def node_bonus(self, field: str) -> int:
        """Sum a flat passive field (e.g. ``"atk_bonus"``, ``"soak_bonus"``) over
        every owned node, **scaled by rank** (a rank-III Iron Skin gives +3)."""
        return sum(getattr(n, field, 0) * self.nodes.get(n.id, 0)
                   for n in self.owned_nodes())

    # --- Low-Endurance rally trigger (read live by the Fighter) -----------
    def _rally_bonus(self, field: str) -> int:
        """Sum a rally field over owned rally nodes whose Endurance threshold the
        Fighter currently sits at or below."""
        fighter = getattr(self.parent, "fighter", None)
        if fighter is None or fighter.max_endurance <= 0:
            return 0
        frac = fighter.endurance / fighter.max_endurance
        total = 0
        for n in self.owned_nodes():
            if n.rally_threshold > 0 and frac <= n.rally_threshold:
                total += getattr(n, field, 0)
        return total

    def rally_atk_bonus(self) -> int:
        return self._rally_bonus("rally_atk_bonus")

    def rally_soak_bonus(self) -> int:
        return self._rally_bonus("rally_soak_bonus")

    # --- Active abilities (charges/cooldowns) -----------------------------
    def actives(self) -> List["perks.Node"]:
        """Owned nodes that carry an active ability."""
        return [n for n in self.owned_nodes() if n.active is not None]

    def hotbar(self, size: int = 5) -> List["perks.Node"]:
        """The owned actives auto-bound to number keys ``1``–``size`` (ADR 0011),
        in a **stable declaration order** so a deed keeps its slot regardless of
        the order the nodes were bought (or a save reload). Capped at ``size``."""
        order = {nid: i for i, nid in enumerate(perks.ALL_NODES)}
        ranked = sorted(self.actives(), key=lambda n: order.get(n.id, 0))
        return ranked[:size]

    def ability_ready(self, node_id: str) -> bool:
        """A ready active is owned, off cooldown, and not already primed."""
        node = perks.ALL_NODES.get(node_id)
        if node is None or node.active is None or not self.has_node(node_id):
            return False
        if self._node_cooldowns.get(node_id, 0) > 0:
            return False
        return node_id not in self._primed

    def cooldown_left(self, node_id: str) -> int:
        return self._node_cooldowns.get(node_id, 0)

    def activate_ability(self, node_id: str) -> Optional[str]:
        """Fire a ready active. Returns a flavour message (or None if it can't
        fire). ``heal``/``stance`` resolve at once and start the cooldown here;
        ``wrath`` primes the next hit and starts its cooldown when that hit lands
        (see ``consume_primed`` in the melee flow)."""
        if not self.ability_ready(node_id):
            return None
        node = perks.ALL_NODES[node_id]
        spec = node.active
        if spec.kind == "wrath":
            self._primed.add(node_id)
            self._timers_touched_this_turn = True
            return f"You gather your fury — your next blow will strike with {spec.name}."
        if spec.kind == "heal":
            fighter = getattr(self.parent, "fighter", None)
            healed = fighter.heal(roll_damage(spec.magnitude)) if fighter else 0
            self._node_cooldowns[node_id] = spec.cooldown
            self._timers_touched_this_turn = True
            return f"You draw a Second Wind and recover {healed} Endurance."
        if spec.kind == "stance":
            self._stance_soak = max(self._stance_soak, spec.soak)
            self._stance_rounds = max(self._stance_rounds, spec.duration)
            self._node_cooldowns[node_id] = spec.cooldown
            self._timers_touched_this_turn = True
            return f"You set your feet — {spec.name}! (+{spec.soak} Soak)"
        return None

    def is_primed(self, node_id: str) -> bool:
        """Whether ``node_id``'s next-hit active is primed and waiting to spend."""
        return node_id in self._primed

    def consume_primed(self) -> int:
        """Called when a melee hit lands: pay out and clear every primed next-hit
        active, returning the total bonus damage, and start their cooldowns."""
        if not self._primed:
            return 0
        bonus = 0
        for nid in list(self._primed):
            node = perks.ALL_NODES.get(nid)
            if node is None or node.active is None:
                continue
            bonus += roll_damage(node.active.magnitude)
            self._node_cooldowns[nid] = node.active.cooldown
        self._primed.clear()
        self._timers_touched_this_turn = True  # this turn set the Wrath cooldown
        return bonus

    def on_kill(self) -> None:
        """Called from ``Fighter.die`` when this hero slays a foe. Reaver's
        Instinct (the Long Watch's Reaver capstone) readies every active deed at
        once."""
        if any(n.readies_actives_on_kill for n in self.owned_nodes()):
            self._node_cooldowns.clear()

    @property
    def stance_soak(self) -> int:
        """Extra Soak from an active defensive stance (0 when none is up)."""
        return self._stance_soak if self._stance_rounds > 0 else 0

    @property
    def ambush_advantage(self) -> bool:
        """Whether any owned Hidden Path node grants advantage on a first strike."""
        return any(n.ambush_advantage for n in self.owned_nodes())

    def end_player_turn(self) -> None:
        """Close out one player turn (called once per action by input_handlers).

        A turn spent *setting* a timer — activating a deed, or landing a primed
        Wrath charge — does not also advance timers, so a freshly-set cooldown or
        stance keeps its full authored length. Any other turn ticks them down."""
        if self._timers_touched_this_turn:
            self._timers_touched_this_turn = False
            return
        self.tick_nodes()

    def tick_nodes(self) -> None:
        """Advance per-node runtime by one player turn: cooldowns count down and
        any stance decays. The raw per-turn step used by ``end_player_turn``."""
        for nid, remaining in list(self._node_cooldowns.items()):
            if remaining > 0:
                self._node_cooldowns[nid] = remaining - 1
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

        # Level 1 is pathless; from level 2 every level grants a Path point.
        if self.level >= character.PATH_POINT_FROM_LEVEL:
            self.path_points += 1
            gains.append("+1 Path point")

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
