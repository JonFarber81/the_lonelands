from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from lonelands import color
from lonelands import tile_types
from lonelands.components.fighter import CRIT_BLEED
from lonelands.dice import rng, roll_check, roll_damage
from lonelands.exceptions import Impossible

if TYPE_CHECKING:
    from lonelands.engine import Engine
    from lonelands.entity import Actor, Entity, Item


# --- Shared combat helpers ------------------------------------------------
def resolve_ambush(hero, target_fighter) -> Tuple[bool, int, int]:
    """The Hidden Path ambush, shared by melee and ranged (ADR 0006): an opening
    strike against an unmarked foe (one still at full Endurance) lands with
    advantage and bonus damage. Returns ``(is_ambush, advantage, bonus_damage)``.

    Advantage is +1 only when a perk actually grants it, so a bonus-damage-only
    ambush still counts as an ambush (its flavour and damage) without a second
    die. A foe (no Hero) never ambushes."""
    if hero is None:
        return False, 0, 0
    bonus = hero.perk_bonus("ambush_bonus_damage")
    is_ambush = bool(
        target_fighter.endurance >= target_fighter.max_endurance
        and (hero.ambush_advantage or bonus)
    )
    advantage = 1 if (is_ambush and hero.ambush_advantage) else 0
    return is_ambush, advantage, bonus


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
        atk_color = color.player_atk if is_player else color.enemy_atk

        # A Critical is a natural crit-face or higher (Swift Wrath widens it); a
        # natural 1 always fumbles.
        crit = result.is_crit
        if not (crit or result.is_success):
            verb = "swing wildly" if result.is_fumble else "miss"
            engine.message_log.add_message(
                f"{who} {af.attack_desc} at {target_name} but {verb}.",
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
        result.damage = dmg  # surfaced in the dice tray (same object note_roll kept)
        tf.take_damage(dmg)

        flavour = " A CRITICAL blow!" if crit else ""
        if ambush:
            flavour += " From the shadows!"
        engine.message_log.add_message(
            f"{who} {af.attack_desc} {target_name} for {dmg} endurance.{flavour}",
            atk_color,
        )

        # Crits (and heavy foes) leave the target bleeding.
        stacks = (CRIT_BLEED if crit else 0) + af.bleed_on_hit
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
    """Fire one of the hero's Path actives (Paths & perks, issue #38).

    A heal/stance resolves at once; a "wrath"-style active primes the hero's next
    melee hit. Either way this counts as the player's turn, so cooldowns tick and
    foes act afterwards. Impossible if the ability isn't ready."""

    def __init__(self, entity: "Actor", perk_id: str):
        super().__init__(entity)
        self.perk_id = perk_id

    def perform(self) -> None:
        hero = getattr(self.entity, "hero", None)
        if hero is None or not hero.ability_ready(self.perk_id):
            raise Impossible("That ability is not ready.")
        message = hero.activate_ability(self.perk_id)
        if message is None:
            raise Impossible("That ability is not ready.")
        self.engine.message_log.add_message(message, color.hope_gain)


class TakeInteractAction(Action):
    """Use whatever the tile the actor stands on offers: stairs, entrances, exits."""

    def perform(self) -> None:
        engine = self.engine
        message = engine.game_world.use_tile()
        if message is None:
            raise Impossible("There is nothing here to enter.")
        engine.message_log.add_message(message, color.welcome_text)
