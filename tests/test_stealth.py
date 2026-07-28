"""The stealth / awareness layer (ADR 0014, issue #107).

Drives the real perception model, the awareness state machine on the AI, and the
sneak toggle against a headless Engine/GameMap on an open, fully-lit floor. The
Hidden Path ambush *gate* (Unaware/primed) is exercised alongside the combat
tests in ``test_perks``/``test_ranged``/``test_hidden_path``; here we cover the
perception, detection, decay, alerting, and FOV pieces those don't touch.
"""
from __future__ import annotations

from lonelands import awareness, content, tile_types
from lonelands.engine import Engine
from lonelands.game_map import GameMap
from lonelands.input_handlers import MainGameEventHandler


def make_world(w=30, h=15, outdoors=False):
    """A headless world with an open, transparent, fully-lit floor, the Ranger
    stood left-of-centre so foes have room to be placed within/without range."""
    player = content.make_player()
    engine = Engine(player)
    gm = GameMap(engine, w, h, outdoors=outdoors)
    gm.tiles[:] = tile_types.floor
    gm.visible[:] = True
    gm.explored[:] = True
    engine.game_map = gm
    player.place(5, 7, gm)
    engine.update_fov()
    return engine, gm, player


def spawn_foe(gm, x, y=7):
    return content.cave_goblin.spawn(gm, x, y)


# ---------------------------------------------------------------------------
# Stealth score — Wits + Silent Tread + gear, no floor
# ---------------------------------------------------------------------------
def test_stealth_sums_wits_and_silent_tread_with_no_floor():
    engine, gm, player = make_world()
    hero = player.hero
    assert hero.stealth == hero.wits                 # no nodes, no stealth gear
    hero.nodes["hp_stealth"] = 2                      # Silent Tread rank 2 -> +4
    assert hero.stealth == hero.wits + 4
    hero.attributes["Wits"] = -3                      # clumsy: negative allowed
    assert hero.stealth == -3 + 4                     # no floor — can go low


def test_gear_stealth_bonus_feeds_the_score():
    engine, gm, player = make_world()
    hero = player.hero
    base = hero.stealth
    # An elven brooch (stealth_bonus 2), once worn, lends it to the score.
    import copy
    brooch = copy.deepcopy(content.elven_brooch)
    player.equipment.toggle_equip(brooch, add_message=False)
    assert hero.stealth == base + 2


# ---------------------------------------------------------------------------
# Effective perception — Stealth bites only while sneaking
# ---------------------------------------------------------------------------
def test_stealth_shrinks_perception_only_while_sneaking():
    engine, gm, player = make_world()
    player.hero.nodes["hp_stealth"] = 1              # +2 Stealth
    # Standing plainly: no concealment, foes see at the full base radius.
    assert awareness.stealth_of(engine) == 0
    assert awareness.effective_perception(engine, 8) == 8
    # Crouched: Stealth pulls the radius in.
    engine.sneaking = True
    assert awareness.stealth_of(engine) == player.hero.stealth
    assert awareness.effective_perception(engine, 8) == 8 - player.hero.stealth


def test_negative_stealth_makes_the_ranger_easier_to_see():
    engine, gm, player = make_world()
    engine.sneaking = True
    player.hero.attributes["Wits"] = -2             # clumsy Ranger, Stealth -2
    # No floor: effective perception exceeds the base — he stands out.
    assert awareness.effective_perception(engine, 8) == 10


# ---------------------------------------------------------------------------
# Detection — radius AND line of sight
# ---------------------------------------------------------------------------
def test_perception_reaches_only_through_line_of_sight():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, 10)                          # 5 tiles off, clear floor
    assert awareness.can_detect(engine, foe, awareness.HOSTILE_PERCEPTION)
    gm.tiles[8, 7] = tile_types.wall                 # drop a wall between them
    assert not awareness.can_detect(engine, foe, awareness.HOSTILE_PERCEPTION)


def test_a_foe_beyond_effective_perception_does_not_detect():
    engine, gm, player = make_world()
    engine.sneaking = True
    player.hero.nodes["hp_stealth"] = 2             # Stealth = wits(2) + 4 = 6
    foe = spawn_foe(gm, 12)                          # 7 tiles off; effective = 8-6 = 2
    assert not awareness.can_detect(engine, foe, awareness.HOSTILE_PERCEPTION)


# ---------------------------------------------------------------------------
# Awareness state machine on the AI
# ---------------------------------------------------------------------------
def test_a_hostile_wakes_and_closes_when_it_perceives_the_ranger():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, 12)                          # 7 off, within perception 8
    assert foe.ai.awareness == awareness.UNAWARE
    foe.ai.perform()
    assert foe.ai.awareness == awareness.ALERTED
    assert foe.ai.last_known == (player.x, player.y)
    assert foe.x < 12                               # stepped toward the Ranger


def test_a_sneaking_ranger_slips_past_a_narrowed_perception():
    engine, gm, player = make_world()
    engine.sneaking = True
    player.hero.nodes["hp_stealth"] = 2            # effective perception 8-6 = 2
    foe = spawn_foe(gm, 12)                          # 7 tiles off, unseen
    foe.ai.perform()
    assert foe.ai.awareness == awareness.UNAWARE
    assert (foe.x, foe.y) == (12, 7)                # a hostile holds ground, unaware


def test_a_foe_that_loses_the_ranger_searches_then_gives_up():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, 7)                           # 2 tiles off -> perceived
    foe.ai.perform()
    assert foe.ai.awareness == awareness.ALERTED
    seen_at = foe.ai.last_known
    # The Ranger vanishes far out of perception.
    player.place(28, 13, gm)
    foe.ai.perform()
    assert foe.ai.awareness == awareness.SEARCHING
    assert foe.ai.last_known == seen_at             # hunts where he was last seen
    # Enough turns and the trail goes cold — back to Unaware, memory cleared.
    for _ in range(12):
        foe.ai.perform()
    assert foe.ai.awareness == awareness.UNAWARE
    assert foe.ai.last_known is None


def test_a_lost_foe_pursues_for_the_full_search_window():
    # The turn sight is lost opens the *full* window — no same-turn decrement —
    # so with Stealth 0 the foe searches for max(2, 5) = 5 turns before giving up.
    engine, gm, player = make_world(w=50)
    foe = spawn_foe(gm, 6)                            # perceived (1 tile off)
    foe.ai.perform()
    assert foe.ai.awareness == awareness.ALERTED
    # Pin the last-known tile far away and send the Ranger clear off the board so
    # the foe hunts the whole window without ever arriving (which would end it).
    foe.ai.last_known = (45, 7)
    player.place(48, 14, gm)
    for turn in range(5):
        foe.ai.perform()
        assert foe.ai.awareness == awareness.SEARCHING, f"gave up early on turn {turn}"
    foe.ai.perform()                                 # 6th turn: the trail goes cold
    assert foe.ai.awareness == awareness.UNAWARE


def test_re_detection_snaps_a_searching_foe_back_to_alerted():
    engine, gm, player = make_world()
    foe = spawn_foe(gm, 7)
    foe.ai.perform()                                # Alerted
    player.place(28, 13, gm)
    foe.ai.perform()                                # -> Searching
    assert foe.ai.awareness == awareness.SEARCHING
    player.place(foe.x + 1, foe.y, gm)              # right back in its face
    foe.ai.perform()
    assert foe.ai.awareness == awareness.ALERTED


def test_search_duration_follows_the_formula():
    engine, gm, player = make_world()
    assert awareness.search_duration(engine) == 5   # Stealth 0 -> max(2, 5)
    engine.sneaking = True
    player.hero.nodes["hp_stealth"] = 2             # Stealth 6 -> max(2, 5-6) = 2
    assert awareness.search_duration(engine) == 2


# ---------------------------------------------------------------------------
# Beasts share the model with a shorter Perception
# ---------------------------------------------------------------------------
def test_a_beast_has_a_short_perception_and_wanders_unaware():
    engine, gm, player = make_world()
    beast = content.wolf.spawn(gm, 11, 7)      # 6 off: beyond a beast's 4
    beast.ai.perform()
    assert beast.ai.awareness == awareness.UNAWARE  # hasn't noticed the Ranger
    near = content.wolf.spawn(gm, 8, 7)         # 3 off: within a beast's 4
    near.ai.perform()
    assert near.ai.awareness == awareness.ALERTED


# ---------------------------------------------------------------------------
# Attacking alerts the struck foe and witnesses in sight
# ---------------------------------------------------------------------------
def test_attacking_alerts_the_struck_foe_and_witnesses_in_sight():
    engine, gm, player = make_world()
    struck = spawn_foe(gm, 6)
    witness = spawn_foe(gm, 3)                       # clear line to the fight
    awareness.alert_on_attack(engine, struck)
    assert struck.ai.awareness == awareness.ALERTED
    assert witness.ai.awareness == awareness.ALERTED
    assert witness.ai.last_known == (player.x, player.y)


def test_a_witness_with_no_line_to_the_fight_stays_oblivious():
    engine, gm, player = make_world()
    struck = spawn_foe(gm, 6)
    blind = spawn_foe(gm, 3)
    gm.tiles[4, 7] = tile_types.wall                # wall between blind foe and hero
    awareness.alert_on_attack(engine, struck)
    assert struck.ai.awareness == awareness.ALERTED
    assert blind.ai.awareness == awareness.UNAWARE  # heard nothing (noise is deferred)


# ---------------------------------------------------------------------------
# The sneak toggle — free, and it narrows the Ranger's own FOV
# ---------------------------------------------------------------------------
def test_sneak_toggle_is_free_and_narrows_the_fov():
    engine, gm, player = make_world(outdoors=True)
    engine.update_fov()
    wide = int(gm.visible.sum())
    handler = MainGameEventHandler(engine)
    turns_before = engine.turn_count
    action = handler._toggle_sneak()
    assert action is None                           # a stance, not an Action
    assert engine.sneaking is True
    assert engine.turn_count == turns_before        # no turn passed
    assert int(gm.visible.sum()) < wide             # senses narrowed
    # Toggling back restores the open stance and the wide FOV.
    handler._toggle_sneak()
    assert engine.sneaking is False
    assert int(gm.visible.sum()) == wide
