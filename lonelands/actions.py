from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from lonelands import color
from lonelands import tile_types
from lonelands.dice import skill_check
from lonelands.exceptions import Impossible

if TYPE_CHECKING:
    from lonelands.engine import Engine
    from lonelands.entity import Actor, Entity, Item


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


class MeleeAction(ActionWithDirection):
    def perform(self) -> None:
        target = self.target_actor
        if target is None or target.fighter is None:
            raise Impossible("There is nothing there to strike.")

        # Incoming blows on the player are resolved by the *player's* own roll:
        # a Parry test. Every die on screen stays the hero's. (The attacker
        # never rolls in this case.)
        if target is self.engine.player and target.hero is not None:
            return self._resolve_incoming(target)
        return self._resolve_strike(target)

    def _resolve_strike(self, target: "Actor") -> None:
        attacker = self.entity
        af = attacker.fighter
        engine = self.engine
        is_player = attacker is engine.player

        weary = attacker.hero.is_weary if attacker.hero else False
        tn = target.fighter.defence
        result = skill_check(tn, af.prowess, weary=weary)
        engine.note_roll(result, attacker)  # feeds the dice tray (player rolls only)

        who = "You" if is_player else f"The {attacker.name}"
        target_name = "you" if target is engine.player else f"the {target.name}"
        atk_color = color.player_atk if is_player else color.enemy_atk

        if result.is_eye:
            engine.message_log.add_message(
                f"{who} strike wildly — the Shadow stirs.",
                color.sauron_eye,
            )

        if not result.is_success:
            engine.message_log.add_message(
                f"{who} {af.attack_desc} at {target_name} but miss.",
                color.gray,
            )
            return

        dmg = af.damage + result.tengwar * af.edge
        target.fighter.take_damage(dmg)
        flavour = ""
        if result.tengwar:
            flavour = f" A tengwar flares — {result.tengwar} extra!"
        engine.message_log.add_message(
            f"{who} {af.attack_desc} {target_name} for {dmg} endurance.{flavour}",
            atk_color,
        )

        # A great success threatens a Piercing Blow.
        if result.is_great and target.fighter.endurance > 0:
            if not target.fighter.protection_test(af.injury):
                mortal = target.fighter.inflict_wound()
                if mortal:
                    engine.message_log.add_message(
                        f"A mortal blow! {target_name.capitalize()} is struck down.",
                        color.player_die if target is engine.player else color.enemy_die,
                    )
                    target.fighter.endurance = 0
                else:
                    engine.message_log.add_message(
                        f"A piercing blow wounds {target_name}!",
                        color.enemy_atk if is_player else color.player_die,
                    )

    def _resolve_incoming(self, player: "Actor") -> None:
        """A foe strikes the player: the player rolls a Parry test (Battle,
        plus any shield/helm bonus) against the attacker's Attack TN. Turn it
        aside on a success; take the blow on a failure. A fumbled parry (the
        Eye) leaves the hero open to a wounding Piercing Blow."""
        attacker = self.entity
        af = attacker.fighter
        engine = self.engine
        hero = player.hero

        defence_bonus = player.equipment.defence_bonus if player.equipment else 0
        result = hero.test_skill("Battle", tn=af.attack, modifier=defence_bonus)
        # test_skill already feeds the dice tray (a player roll).

        foe = f"The {attacker.name}"
        if result.is_success:
            engine.message_log.add_message(
                f"{foe} {af.attack_desc} you, but you turn the blow aside.",
                color.gray,
            )
            return

        dmg = af.damage
        player.fighter.take_damage(dmg)
        engine.message_log.add_message(
            f"{foe} {af.attack_desc} you for {dmg} endurance.",
            color.enemy_atk,
        )
        if player.fighter.endurance <= 0:
            return  # die() already fired from the endurance setter

        # A fumbled parry (Eye of Sauron) leaves you exposed to a Piercing Blow.
        if result.is_eye:
            engine.message_log.add_message(
                "You are thrown off-guard — the Shadow presses the attack!",
                color.sauron_eye,
            )
            if not player.fighter.protection_test(af.injury):
                mortal = player.fighter.inflict_wound()
                if mortal:
                    engine.message_log.add_message(
                        "A mortal wound! You are struck down.", color.player_die
                    )
                    player.fighter.endurance = 0
                else:
                    engine.message_log.add_message(
                        "A piercing blow wounds you!", color.player_die
                    )


class BumpAction(ActionWithDirection):
    def perform(self) -> None:
        # A friendly NPC is spoken to, never struck; anyone else with a fighter
        # (the player included) is a valid combat target.
        if self.target_actor and self.target_actor.npc is not None:
            return TalkAction(self.entity, self.target_actor).perform()
        if self.target_actor and self.target_actor.fighter:
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
                self.engine.message_log.add_message(f"You take the {item.name}.", color.item_c)
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


class TakeInteractAction(Action):
    """Use whatever the tile the actor stands on offers: stairs, entrances, exits."""

    def perform(self) -> None:
        engine = self.engine
        message = engine.game_world.use_tile()
        if message is None:
            raise Impossible("There is nothing here to enter.")
        engine.message_log.add_message(message, color.welcome_text)
