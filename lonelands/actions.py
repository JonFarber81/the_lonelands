from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

from lonelands import color
from lonelands import tile_types
from lonelands.components.fighter import CRIT_BLEED
from lonelands.dice import rng, roll_check, roll_damage
from lonelands.exceptions import Impossible

if TYPE_CHECKING:
    from lonelands.engine import Engine
    from lonelands.entity import Actor, Entity, Item


# --- Hidden Path traps (Snare) --------------------------------------------
@dataclass
class Trap:
    """A snare laid on a tile by the Hidden Path's Trapper. The first foe to
    step onto it springs it: it takes ``damage`` (a dice spec, rolled at trigger)
    and is rooted for ``root_rounds`` rounds, then the trap is spent. The hero
    who set it (and other townsfolk) pass over harmlessly."""

    x: int
    y: int
    damage: str = "1d6"
    root_rounds: int = 2
    char: str = "^"


def _spring_trap(engine: "Engine", actor: "Actor") -> None:
    """Spring a Snare under ``actor`` if one is laid on its tile: roll the trap's
    damage, root the foe, spend the trap, and log the catch when it's in sight."""
    trap = engine.game_map.traps.pop((actor.x, actor.y), None)
    if trap is None:
        return
    tf = actor.fighter
    if tf is None or tf.dead:
        return
    dmg = max(1, roll_damage(trap.damage))
    tf.take_damage(dmg)
    if tf.dead:
        return  # the snare finished it; die() already logged the slaying
    tf.apply_root(trap.root_rounds)
    if engine.game_map.visible[actor.x, actor.y]:
        engine.message_log.add_message(
            f"The {actor.name} springs a hidden snare — {dmg} endurance, and held fast!",
            color.enemy_atk,
        )


# --- Shared combat helpers ------------------------------------------------
def resolve_ambush(hero, target_fighter) -> Tuple[bool, int, int]:
    """The Hidden Path ambush, shared by melee and ranged (ADR 0006): an opening
    strike against an unmarked foe (one still at full Endurance) lands with
    advantage and bonus damage. Returns ``(is_ambush, advantage, bonus_damage)``.

    A **primed** ambush (Shadowstep/Vanish) fires against *any* foe, fresh or
    not — the blink or vanish has set up the unseen strike. Advantage is +1 only
    when a node grants it (or an ambush is primed), so a bonus-damage-only ambush
    still counts as an ambush (its flavour and damage) without a second die. A
    foe (no Hero) never ambushes."""
    if hero is None:
        return False, 0, 0
    bonus = hero.node_bonus("ambush_bonus_damage")
    primed = getattr(hero, "ambush_primed", False)
    fresh_opener = (
        target_fighter.endurance >= target_fighter.max_endurance
        and (hero.ambush_advantage or bonus)
    )
    is_ambush = bool(primed or fresh_opener)
    advantage = 1 if (is_ambush and (hero.ambush_advantage or primed)) else 0
    return is_ambush, advantage, bonus


def _second_person(desc: str) -> str:
    """A creature's third-person attack verb (``"hacks at"``, ``"snaps at"``,
    ``"strikes"``) read in the second person for the player (``"hack at"``,
    ``"snap at"``, ``"strike"``): only the leading verb sheds its ``-s``, so a
    trailing preposition is kept. Without this the melee log reads "You strikes".
    """
    head, sep, rest = desc.partition(" ")
    if head.endswith("s"):
        head = head[:-1]
    return head + (sep + rest if rest else "")


class Action:
    def __init__(self, entity: "Actor") -> None:
        self.entity = entity

    @property
    def engine(self) -> "Engine":
        return self.entity.gamemap.engine

    def perform(self) -> None:
        raise NotImplementedError()


class WaitAction(Action):
    def perform(self) -> None:
        pass


class ActionWithDirection(Action):
    def __init__(self, entity: "Actor", dx: int, dy: int):
        super().__init__(entity)
        self.dx = dx
        self.dy = dy

    @property
    def dest_xy(self) -> Tuple[int, int]:
        return self.entity.x + self.dx, self.entity.y + self.dy

    @property
    def blocking_entity(self) -> Optional["Entity"]:
        return self.engine.game_map.get_blocking_entity_at(*self.dest_xy)

    @property
    def target_actor(self) -> Optional["Actor"]:
        return self.engine.game_map.get_actor_at(*self.dest_xy)

    def perform(self) -> None:
        raise NotImplementedError()


class MovementAction(ActionWithDirection):
    def perform(self) -> None:
        f = getattr(self.entity, "fighter", None)
        if f is not None and f.is_rooted:
            # Held fast by a Snare/Pinning — the foe strains but cannot move (the
            # Engine ticks the root down each round). The AI catches this and waits.
            raise Impossible("Held fast, it cannot move.")
        dest_x, dest_y = self.dest_xy
        gm = self.engine.game_map
        if not gm.in_bounds(dest_x, dest_y):
            # The player walking off an edge crosses into the neighbouring
            # Region; anyone else is stopped by the bounds of the map.
            world = getattr(self.engine, "game_world", None)
            if (
                self.entity is self.engine.player
                and world is not None
                and world.cross_edge(self.dx, self.dy)
            ):
                return
            raise Impossible("That way lies the edge of the known world.")
        if not gm.tiles["walkable"][dest_x, dest_y]:
            raise Impossible("The way is blocked.")
        if gm.get_blocking_entity_at(dest_x, dest_y):
            raise Impossible("Something bars the way.")
        self.entity.move(self.dx, self.dy)
        # A foe that steps onto a laid Snare springs it (the hero and townsfolk
        # pass over harmlessly).
        if self.entity is not self.engine.player and is_hostile_actor(self.entity):
            _spring_trap(self.engine, self.entity)
        # Only the player overhears ambient barks, and only on their own steps
        # (foes move through this same action). Throttled inside barks.emit.
        if self.entity is self.engine.player:
            from lonelands import barks
            barks.emit(self.engine)


class MeleeAction(ActionWithDirection):
    def perform(self) -> None:
        target = self.target_actor
        if target is None or target.fighter is None:
            raise Impossible("There is nothing there to strike.")
        return self._resolve_attack(target)

    def _resolve_attack(self, target: "Actor") -> None:
        """One d20 attack, whoever swings: ``d20 + attack bonus vs Defence``. On
        a hit, roll damage and subtract the target's Soak. A natural 20 auto-hits
        for bonus damage and opens a Bleed; a natural 1 auto-misses. The dice
        tray only reflects the player's own rolls (``note_roll`` gates on that)."""
        attacker = self.entity
        af = attacker.fighter
        tf = target.fighter
        engine = self.engine
        is_player = attacker is engine.player
        hero = getattr(attacker, "hero", None)

        # Hidden Path ambush: an opening blow against an unmarked foe (still at
        # full Endurance) strikes with advantage and bonus damage. The Shot flow
        # calls the same helper (ADR 0006).
        ambush, advantage, ambush_dmg = resolve_ambush(hero, tf)

        result = roll_check(af.attack_bonus, tf.defence, advantage=advantage)
        # Tell the roll its Crit threshold (Swift Wrath widens it below 20) so the
        # dice tray and the log agree on a widened Critical.
        result.crit_face = af.crit_face
        engine.note_roll(result, attacker)  # feeds the dice tray (player rolls only)

        who = "You" if is_player else f"The {attacker.name}"
        target_name = "you" if target is engine.player else f"the {target.name}"
        # The player is addressed in the second person ("You strike"), a foe in
        # the third ("The warg savages").
        attack_desc = _second_person(af.attack_desc) if is_player else af.attack_desc
        atk_color = color.player_atk if is_player else color.enemy_atk

        # A Critical is a natural crit-face or higher (Swift Wrath widens it); a
        # natural 1 always fumbles.
        crit = result.is_crit
        if not (crit or result.is_success):
            verb = "swing wildly" if result.is_fumble else "miss"
            engine.message_log.add_message(
                f"{who} {attack_desc} at {target_name} but {verb}.",
                color.sauron_eye if result.is_fumble else color.gray,
            )
            return

        # A hit: roll damage (+ any flat melee-damage perk and a weapon's bonus-
        # vs-kind), subtract Soak — which a piercing weapon partly ignores (a
        # clean blow always stings for 1+).
        raw = roll_damage(af.damage) + af.melee_damage_bonus + af.bonus_vs_damage(target)
        soak = max(0, tf.soak - af.pierce)
        dmg = max(1, raw - soak)
        if crit:
            dmg += roll_damage(af.damage)  # the Critical carries a second roll
        if ambush:
            dmg += ambush_dmg
        if hero is not None:
            dmg += hero.consume_primed()  # Swift Wrath: spend a primed next-hit
            hero.consume_ambush_prime()   # Shadowstep/Vanish: the unseen strike lands
        result.damage = dmg  # surfaced in the dice tray (same object note_roll kept)
        tf.take_damage(dmg)

        flavour = " A CRITICAL blow!" if crit else ""
        if ambush:
            flavour += " From the shadows!"
        engine.message_log.add_message(
            f"{who} {attack_desc} {target_name} for {dmg} endurance.{flavour}",
            atk_color,
        )

        # Crits (and heavy foes) leave the target bleeding; the Hidden Path's
        # Poisoned Blade envenoms every hero blow the same way.
        stacks = (CRIT_BLEED if crit else 0) + af.bleed_on_hit + af.melee_bleed
        if stacks and tf.endurance > 0:
            tf.apply_bleed(stacks)
            engine.message_log.add_message(
                f"{target_name.capitalize()} {'are' if target is engine.player else 'is'} "
                f"left bleeding!",
                color.player_die if target is engine.player else color.enemy_atk,
            )


# --- Ranged: arrows & the Shot (ADR 0006, issue #46) ----------------------
# Arrow recovery: this fraction of loosed arrows can be picked back up (they
# land on the target's tile). A deliberate future perk lever.
ARROW_RECOVERY_CHANCE = 0.5


def _ammo_stack(actor: "Actor"):
    """The actor's arrow Stack, if the pack holds one (matched by the canonical
    ammo name, since arrows are a fungible Stack, not distinct gear)."""
    from lonelands import content
    inv = getattr(actor, "inventory", None)
    if inv is None:
        return None
    for item in inv.items:
        if item.stackable and item.name == content.AMMO_NAME:
            return item
    return None


def _spend_one_arrow(stack: "Item", actor: "Actor") -> None:
    """Consume a single arrow from ``stack``, removing the empty Stack."""
    stack.quantity -= 1
    if stack.quantity <= 0 and actor.inventory is not None:
        actor.inventory.remove(stack)


def _chebyshev(a: "Actor", b: "Actor") -> int:
    """Grid (king-move) distance — the metric a Shot's range falloff uses."""
    return max(abs(a.x - b.x), abs(a.y - b.y))


def is_hostile_actor(actor: "Actor") -> bool:
    """Whether ``actor`` is a living combatant (not a townsfolk) — a valid mark
    for a Shot and the thing whose adjacency spoils one. Callers exclude the
    acting hero themselves (the hero also matches this shape)."""
    return (
        actor.npc is None
        and actor.fighter is not None and not actor.fighter.dead
    )


def _has_adjacent_hostile(engine: "Engine", actor: "Actor") -> bool:
    """Whether a living, non-friendly fighter stands in any of ``actor``'s eight
    neighbours — the point-blank condition that spoils a Shot (Disadvantage)."""
    gm = engine.game_map
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            other = gm.get_actor_at(actor.x + dx, actor.y + dy)
            if other is not None and other is not actor and is_hostile_actor(other):
                return True
    return False


def _maybe_recover_arrow(engine: "Engine", target: "Actor") -> None:
    """Half of loosed arrows survive to be picked up: drop one on the target's
    tile on a coin-flip (ADR 0006). Recovery rate is a future perk lever."""
    if rng.random() >= ARROW_RECOVERY_CHANCE:
        return
    from lonelands import content
    content.arrows.spawn(engine.game_map, target.x, target.y)


class RangedAttackAction(Action):
    """Loose an arrow at a chosen foe (ADR 0006): the d20 core keyed off Wits,
    with a per-bow effective range and falloff beyond it, Disadvantage at point-
    blank, the shared Hidden Path ambush, and no Bleed on a Critical. Costs a
    full turn and spends one arrow; half of spent arrows are recoverable."""

    def __init__(self, entity: "Actor", target: "Actor"):
        super().__init__(entity)
        self.target = target

    def perform(self) -> None:
        attacker = self.entity
        af = attacker.fighter
        engine = self.engine
        if af is None or not af.has_ranged_weapon:
            raise Impossible("You have no bow readied.")
        target = self.target
        if target is None or target.fighter is None or target.fighter.dead:
            raise Impossible("There is nothing there to shoot.")
        ammo = _ammo_stack(attacker)
        if ammo is None:
            raise Impossible("Your quiver is empty.")

        tf = target.fighter
        is_player = attacker is engine.player
        hero = getattr(attacker, "hero", None)

        _spend_one_arrow(ammo, attacker)  # an arrow is spent, hit or miss

        distance = _chebyshev(attacker, target)
        penalty = af.range_penalty(distance)

        # A foe at your elbow spoils the aim (Disadvantage); the Hidden Path
        # ambush lends Advantage. The two fold into one signed advantage int.
        adjacent = _has_adjacent_hostile(engine, attacker)
        ambush, ambush_adv, ambush_dmg = resolve_ambush(hero, tf)
        advantage = ambush_adv + (-1 if adjacent else 0)

        # A Shot Crits only on a natural 20 — Swift Wrath's widened melee crit
        # does not carry to the bow (ADR 0006), so the default crit_face stands.
        result = roll_check(af.ranged_attack_bonus - penalty, tf.defence,
                            advantage=advantage)
        engine.note_roll(result, attacker)  # feeds the dice tray (player rolls only)

        who = "You" if is_player else f"The {attacker.name}"
        target_name = "you" if target is engine.player else f"the {target.name}"
        loose = "loose" if is_player else "looses"
        strike = "strike" if is_player else "strikes"
        atk_color = color.player_atk if is_player else color.enemy_atk

        crit = result.is_crit
        if not (crit or result.is_success):
            verb = "the arrow flies wild" if result.is_fumble else "miss"
            engine.message_log.add_message(
                f"{who} {loose} an arrow at {target_name} but {verb}.",
                color.sauron_eye if result.is_fumble else color.gray,
            )
            _maybe_recover_arrow(engine, target)
            return

        # A hit: roll the bow's damage (+ any Far Shot damage perk), subtract
        # Soak — a clean shot always stings for 1+. No pierce, no Bleed.
        raw = roll_damage(af.ranged_damage) + af.ranged_damage_bonus
        dmg = max(1, raw - tf.soak)
        if crit:
            dmg += roll_damage(af.ranged_damage)  # the Critical carries a second roll
        if ambush:
            dmg += ambush_dmg
        if hero is not None:
            hero.consume_ambush_prime()   # Shadowstep/Vanish: the unseen shot lands
        result.damage = dmg  # surfaced in the dice tray (same object note_roll kept)
        tf.take_damage(dmg)

        flavour = " A CRITICAL shot!" if crit else ""
        if ambush:
            flavour += " From the shadows!"
        engine.message_log.add_message(
            f"{who} {loose} an arrow and {strike} {target_name} for {dmg} endurance.{flavour}",
            atk_color,
        )
        _maybe_recover_arrow(engine, target)


class BumpAction(ActionWithDirection):
    def perform(self) -> None:
        # A friendly NPC is spoken to, never struck; anyone else with a living
        # fighter (the player included) is a valid combat target. A corpse stays
        # on the map as a dead actor with a fighter, so gate on `not dead` — that
        # lets the player step onto the tile and pick up any loot underneath.
        target = self.target_actor
        if target and target.npc is not None:
            return TalkAction(self.entity, target).perform()
        if target and target.fighter and not target.fighter.dead:
            return MeleeAction(self.entity, self.dx, self.dy).perform()
        return MovementAction(self.entity, self.dx, self.dy).perform()


class TalkAction(Action):
    def __init__(self, entity: "Actor", target: "Actor"):
        super().__init__(entity)
        self.target = target

    def perform(self) -> None:
        from lonelands import input_handlers

        if self.target.npc is None:
            raise Impossible("They have nothing to say.")
        self.engine.event_handler = input_handlers.DialogHandler(
            self.engine, self.target
        )


class PickupAction(Action):
    def perform(self) -> None:
        actor = self.entity
        x, y = actor.x, actor.y
        inv = actor.inventory
        for item in list(self.engine.game_map.items):
            if item.x == x and item.y == y:
                inv.add(item)  # merges fungible stacks; raises if the pack is full
                self.engine.game_map.entities.remove(item)
                # Gear shows its full stat line on the spot — there is no
                # identification (ADR 0005).
                line = ""
                if item.equippable is not None:
                    line = f" [{item.equippable.stat_line()}]"
                self.engine.message_log.add_message(
                    f"You take the {item.name}.{line}", color.item_c)
                event = getattr(item, "pickup_event", None)
                if event:
                    self.engine.quest_log.notify_event(event, self.engine)
                return
        raise Impossible("There is nothing here to pick up.")


class ItemAction(Action):
    def __init__(self, entity: "Actor", item: "Item", target_xy: Optional[Tuple[int, int]] = None):
        super().__init__(entity)
        self.item = item
        self.target_xy = target_xy or (entity.x, entity.y)

    @property
    def target_actor(self) -> Optional["Actor"]:
        return self.engine.game_map.get_actor_at(*self.target_xy)

    def perform(self) -> None:
        if self.item.consumable:
            self.item.consumable.activate(self)


class DropItem(ItemAction):
    def perform(self) -> None:
        if self.entity.equipment and self.entity.equipment.item_is_equipped(self.item):
            self.entity.equipment.toggle_equip(self.item)
        self.entity.inventory.drop(self.item)


class EquipAction(Action):
    def __init__(self, entity: "Actor", item: "Item"):
        super().__init__(entity)
        self.item = item

    def perform(self) -> None:
        self.entity.equipment.toggle_equip(self.item)


class ActivateAbilityAction(Action):
    """Fire one of the hero's Path actives (a node's active — ADR 0011).

    A heal/stance resolves at once; a "wrath"-style active primes the hero's next
    melee hit. Either way this counts as the player's turn, so cooldowns tick and
    foes act afterwards. Impossible if the ability isn't ready."""

    def __init__(self, entity: "Actor", node_id: str):
        super().__init__(entity)
        self.node_id = node_id

    def perform(self) -> None:
        hero = getattr(self.entity, "hero", None)
        if hero is None or not hero.ability_ready(self.node_id):
            raise Impossible("That ability is not ready.")
        message = hero.activate_ability(self.node_id)
        if message is None:
            raise Impossible("That ability is not ready.")
        self.engine.message_log.add_message(message, color.hope_gain)


# --- Hidden Path targeted deeds (ADR 0011, #77) ---------------------------
# Shadowstep/Disengage (blink to a tile), Snare (lay a trap), Pinning (root a
# foe). Each is picked with a targeting handler, resolves here with map access,
# and charges its cooldown via the Hero. All count as the player's turn.
def _ready_active(entity: "Actor", node_id: str):
    """The hero and the ready active node for ``node_id`` — raising Impossible if
    the deed isn't the hero's, isn't owned, or isn't off cooldown."""
    hero = getattr(entity, "hero", None)
    if hero is None or not hero.ability_ready(node_id):
        raise Impossible("That deed is not ready.")
    from lonelands import perks
    node = perks.ALL_NODES.get(node_id)
    if node is None or node.active is None:
        raise Impossible("That deed is not ready.")
    return hero, node


def _tile_reachable(engine: "Engine", actor: "Actor", x: int, y: int,
                    reach: int) -> None:
    """Guard a chosen blink/snare tile: on the map, in sight, open (walkable and
    unblocked), and within ``reach`` tiles. Raises Impossible on any failure."""
    gm = engine.game_map
    if not gm.in_bounds(x, y):
        raise Impossible("That lies beyond the map.")
    if max(abs(x - actor.x), abs(y - actor.y)) > reach:
        raise Impossible("That is too far.")
    if not gm.visible[x, y]:
        raise Impossible("You cannot see that spot.")
    if not gm.tiles["walkable"][x, y]:
        raise Impossible("The way there is blocked.")
    if gm.get_blocking_entity_at(x, y) is not None or (x, y) == (actor.x, actor.y):
        raise Impossible("There is no room there.")


class ShadowstepAction(Action):
    """Blink to a chosen empty tile within reach (Shadowstep/Disengage). If the
    deed primes an ambush, the next strike lands unseen. A full turn."""

    def __init__(self, entity: "Actor", node_id: str, target_xy: Tuple[int, int]):
        super().__init__(entity)
        self.node_id = node_id
        self.target_xy = target_xy

    def perform(self) -> None:
        hero, node = _ready_active(self.entity, self.node_id)
        spec = node.active
        x, y = self.target_xy
        _tile_reachable(self.engine, self.entity, x, y, spec.reach)
        self.entity.x, self.entity.y = x, y
        if spec.primes_ambush:
            hero.prime_ambush()
        hero.begin_cooldown(self.node_id)
        tail = " — you ready an unseen strike." if spec.primes_ambush else "."
        self.engine.message_log.add_message(
            f"You slip through the shadows{tail}", color.hope_gain)


class SnareAction(Action):
    """Lay a Snare trap on a chosen tile within reach (a full turn)."""

    def __init__(self, entity: "Actor", node_id: str, target_xy: Tuple[int, int]):
        super().__init__(entity)
        self.node_id = node_id
        self.target_xy = target_xy

    def perform(self) -> None:
        hero, node = _ready_active(self.entity, self.node_id)
        spec = node.active
        x, y = self.target_xy
        _tile_reachable(self.engine, self.entity, x, y, spec.reach)
        if (x, y) in self.engine.game_map.traps:
            raise Impossible("A snare is already laid there.")
        self.engine.game_map.traps[(x, y)] = Trap(
            x, y, damage=spec.magnitude, root_rounds=spec.duration)
        hero.begin_cooldown(self.node_id)
        self.engine.message_log.add_message(
            "You set a hidden snare among the shadows.", color.hope_gain)


class PinningAction(Action):
    """Root a chosen visible foe within reach for the deed's duration (a full
    turn)."""

    def __init__(self, entity: "Actor", node_id: str, target: "Actor"):
        super().__init__(entity)
        self.node_id = node_id
        self.target = target

    def perform(self) -> None:
        hero, node = _ready_active(self.entity, self.node_id)
        spec = node.active
        target = self.target
        if target is None or target.fighter is None or target.fighter.dead:
            raise Impossible("There is nothing there to pin.")
        if max(abs(target.x - self.entity.x),
               abs(target.y - self.entity.y)) > spec.reach:
            raise Impossible("That foe is too far to pin.")
        if not self.engine.game_map.visible[target.x, target.y]:
            raise Impossible("You cannot see that foe.")
        target.fighter.apply_root(spec.duration)
        hero.begin_cooldown(self.node_id)
        self.engine.message_log.add_message(
            f"You pin the {target.name} where it stands!", color.hope_gain)


class TakeInteractAction(Action):
    """Use whatever the tile the actor stands on offers: stairs, entrances, exits."""

    def perform(self) -> None:
        engine = self.engine
        message = engine.game_world.use_tile()
        if message is None:
            raise Impossible("There is nothing here to enter.")
        engine.message_log.add_message(message, color.welcome_text)
