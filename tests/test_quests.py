"""Tests for the quest state machine and QuestLog routing.

The turn-in path touches an `engine`; we use a tiny fake with just the surface
QuestLog reaches for (message_log + player.hero), so no game window is needed.
"""
from __future__ import annotations

from lonelands.quests import Quest, QuestLog, QuestState


class FakeHero:
    def __init__(self):
        self.xp = 0

    def add_xp(self, amount):
        self.xp += amount


class FakeMessageLog:
    def __init__(self):
        self.messages = []

    def add_message(self, text, fg=None, **kwargs):
        self.messages.append(text)


class FakeItem:
    def __init__(self, name):
        self.name = name


class FakeInventory:
    def __init__(self, items=None):
        self.items = list(items or [])

    def remove(self, item):
        self.items.remove(item)


class FakeEngine:
    def __init__(self, hero=None, items=None):
        self.message_log = FakeMessageLog()
        self.player = type("P", (), {"hero": hero,
                                     "inventory": FakeInventory(items)})()


def make_quest(**kw):
    defaults = dict(quest_id="q1", title="Wolves", summary="s",
                    objective="Slay wolves", target_count=3)
    defaults.update(kw)
    return Quest(**defaults)


# --- Quest state machine ---------------------------------------------------

def test_quest_starts_unstarted():
    assert make_quest().state == QuestState.UNSTARTED


def test_advance_does_nothing_until_active():
    q = make_quest()
    q.advance()
    assert q.progress == 0  # ignored while UNSTARTED


def test_advance_moves_to_ready_when_target_met():
    q = make_quest(target_count=2)
    q.state = QuestState.ACTIVE
    q.advance()
    assert q.state == QuestState.ACTIVE
    q.advance()
    assert q.state == QuestState.READY
    assert q.progress == 2


def test_advance_clamps_progress_to_target():
    q = make_quest(target_count=1)
    q.state = QuestState.ACTIVE
    q.advance(amount=99)
    assert q.progress == 1
    assert q.state == QuestState.READY


def test_status_line_reflects_state():
    q = make_quest(target_count=3)
    assert "0/3" in q.status_line()
    q.state = QuestState.READY
    assert "return and report" in q.status_line()
    q.state = QuestState.DONE
    assert "complete" in q.status_line()


# --- QuestLog ---------------------------------------------------------------

def test_register_start_and_query():
    log = QuestLog()
    log.register(make_quest())
    assert not log.is_active("q1")
    log.start("q1")
    assert log.is_active("q1")
    assert log.get("q1").state == QuestState.ACTIVE


def test_start_is_idempotent_once_active():
    log = QuestLog()
    q = make_quest()
    log.register(q)
    log.start("q1")
    q.advance()  # progress 1/3
    log.start("q1")  # should not reset
    assert q.progress == 1


def test_notify_kill_advances_matching_quest_only():
    log = QuestLog()
    wolves = make_quest(quest_id="w", title="Wolves", target_count=2)
    wolves.kill_target = "wolf"
    orcs = make_quest(quest_id="o", title="Orcs", target_count=2)
    orcs.kill_target = "orc"
    log.register(wolves)
    log.register(orcs)
    log.start("w")
    log.start("o")

    engine = FakeEngine()
    log.notify_kill("wolf", engine)
    assert wolves.progress == 1
    assert orcs.progress == 0


def test_notify_event_advances_by_tag():
    log = QuestLog()
    q = make_quest(quest_id="q", target_count=1)
    q.event_tag = "reach_town"
    log.register(q)
    log.start("q")
    log.notify_event("reach_town", FakeEngine())
    assert q.state == QuestState.READY


def test_turn_in_requires_ready_state():
    log = QuestLog()
    q = make_quest(quest_id="q", target_count=1, xp_reward=50)
    log.register(q)
    log.start("q")
    engine = FakeEngine(hero=FakeHero())

    assert log.turn_in("q", engine) is False  # not ready yet
    q.advance()  # -> READY
    assert log.turn_in("q", engine) is True
    assert q.state == QuestState.DONE
    assert engine.player.hero.xp == 50


def test_turn_in_runs_on_complete_callback():
    called = []
    log = QuestLog()
    q = make_quest(quest_id="q", target_count=1,
                   on_complete=lambda eng: called.append(eng))
    log.register(q)
    log.start("q")
    q.advance()
    log.turn_in("q", FakeEngine(hero=FakeHero()))
    assert len(called) == 1


def test_turn_in_twice_is_a_noop_the_second_time():
    log = QuestLog()
    q = make_quest(quest_id="q", target_count=1, xp_reward=10)
    log.register(q)
    log.start("q")
    q.advance()
    hero = FakeHero()
    engine = FakeEngine(hero=hero)
    log.turn_in("q", engine)
    assert log.turn_in("q", engine) is False
    assert hero.xp == 10  # not awarded twice


# --- Delivery / courier objectives -----------------------------------------

def make_delivery_quest(**kw):
    q = make_quest(quest_id="courier", title="The Parcel",
                   objective="carry the parcel to Bree", target_count=1, **kw)
    q.deliver_item = "dwarf-trader's parcel"
    q.deliver_to = "Barliman"
    return q


def test_can_deliver_only_when_active_and_item_held():
    log = QuestLog()
    q = make_delivery_quest()
    log.register(q)
    parcel = FakeItem("dwarf-trader's parcel")

    # UNSTARTED: never deliverable, even holding the item
    assert log.can_deliver("Barliman", FakeEngine(items=[parcel])) is False
    log.start("courier")
    # ACTIVE but empty-handed
    assert log.can_deliver("Barliman", FakeEngine()) is False
    # ACTIVE and carrying it
    assert log.can_deliver("Barliman", FakeEngine(items=[parcel])) is True


def test_can_deliver_only_for_the_named_recipient():
    log = QuestLog()
    q = make_delivery_quest()  # deliver_to = "Barliman"
    log.register(q)
    log.start("courier")
    parcel = FakeItem("dwarf-trader's parcel")
    engine = FakeEngine(items=[parcel])

    # holding the item, but speaking to the wrong NPC
    assert log.can_deliver("Halbarad", engine) is False
    assert log.can_deliver("Barliman", engine) is True


def test_notify_delivery_consumes_item_and_advances():
    log = QuestLog()
    q = make_delivery_quest()
    log.register(q)
    log.start("courier")
    parcel = FakeItem("dwarf-trader's parcel")
    engine = FakeEngine(items=[parcel])

    assert log.notify_delivery("Barliman", engine) is True
    assert parcel not in engine.player.inventory.items  # consumed
    assert q.state == QuestState.READY  # target_count=1 -> ready to report


def test_notify_delivery_fails_without_the_item():
    log = QuestLog()
    q = make_delivery_quest()
    log.register(q)
    log.start("courier")
    engine = FakeEngine()  # empty pack

    assert log.notify_delivery("Barliman", engine) is False
    assert q.state == QuestState.ACTIVE  # unchanged


def test_notify_delivery_ignores_the_wrong_recipient():
    log = QuestLog()
    q = make_delivery_quest()
    log.register(q)
    log.start("courier")
    parcel = FakeItem("dwarf-trader's parcel")
    engine = FakeEngine(items=[parcel])

    assert log.notify_delivery("Halbarad", engine) is False
    assert parcel in engine.player.inventory.items  # not consumed
    assert q.state == QuestState.ACTIVE


def test_notify_delivery_requires_active_quest():
    log = QuestLog()
    q = make_delivery_quest()
    log.register(q)  # still UNSTARTED
    parcel = FakeItem("dwarf-trader's parcel")
    assert log.notify_delivery("Barliman", FakeEngine(items=[parcel])) is False


def test_delivery_then_turn_in_fires_rewards():
    log = QuestLog()
    q = make_delivery_quest(xp_reward=30)
    log.register(q)
    log.start("courier")
    parcel = FakeItem("dwarf-trader's parcel")
    engine = FakeEngine(hero=FakeHero(), items=[parcel])

    log.notify_delivery("Barliman", engine)  # -> READY, parcel gone
    assert log.turn_in("courier", engine) is True  # reward still keyed by quest id
    assert q.state == QuestState.DONE
    assert engine.player.hero.xp == 30


def test_delivery_descriptor_survives_pickling():
    import pickle
    q = make_delivery_quest()
    restored = pickle.loads(pickle.dumps(q))
    assert restored.deliver_item == "dwarf-trader's parcel"
    assert restored.deliver_to == "Barliman"


# --- Talk-to objectives -----------------------------------------------------

def make_talk_quest(node=None, **kw):
    kw.setdefault("target_count", 1)
    q = make_quest(quest_id="errand", title="Word to the Woodsman",
                   objective="carry word to the woodsman of Combe", **kw)
    q.talk_target = "Woodsman"
    if node is not None:
        q.talk_node = node
    return q


def test_notify_talk_advances_matching_quest_only():
    log = QuestLog()
    woodsman = make_talk_quest()
    other = make_quest(quest_id="o", title="Other")
    other.talk_target = "Butterbur"
    log.register(woodsman)
    log.register(other)
    log.start("errand")
    log.start("o")

    log.notify_talk("Woodsman", FakeEngine(), opening=True)
    assert woodsman.state == QuestState.READY
    assert other.progress == 0


def test_notify_talk_ignores_unstarted_quest():
    log = QuestLog()
    q = make_talk_quest()
    log.register(q)  # still UNSTARTED
    log.notify_talk("Woodsman", FakeEngine(), opening=True)
    assert q.progress == 0
    assert q.state == QuestState.UNSTARTED


def test_notify_talk_ignores_the_wrong_npc():
    log = QuestLog()
    q = make_talk_quest()
    log.register(q)
    log.start("errand")
    log.notify_talk("Butterbur", FakeEngine(), opening=True)
    assert q.progress == 0


def test_notify_talk_matches_a_specific_node_when_named():
    log = QuestLog()
    q = make_talk_quest(node="secret")
    log.register(q)
    log.start("errand")

    # right NPC, but not the node the quest cares about
    log.notify_talk("Woodsman", FakeEngine(), node="root")
    assert q.progress == 0
    # the named node advances it
    log.notify_talk("Woodsman", FakeEngine(), node="secret")
    assert q.state == QuestState.READY


def test_plain_talk_to_fires_at_the_hello_not_on_later_nodes():
    log = QuestLog()
    q = make_talk_quest(target_count=1)  # no talk_node
    log.register(q)
    log.start("errand")
    # Node entries mid-conversation don't count for a plain talk-to...
    log.notify_talk("Woodsman", FakeEngine(), node="deeper")
    assert q.progress == 0
    # ...only the opening greeting does.
    log.notify_talk("Woodsman", FakeEngine(), node="root", opening=True)
    assert q.state == QuestState.READY


def test_plain_talk_to_counts_once_per_conversation():
    """A multi-count talk-to advances only at each conversation's hello, so
    walking a tree of nodes in one visit can't over-count."""
    log = QuestLog()
    q = make_talk_quest(target_count=2)  # no talk_node
    log.register(q)
    log.start("errand")

    # One visit: one hello, then several node steps.
    log.notify_talk("Woodsman", FakeEngine(), node="root", opening=True)
    log.notify_talk("Woodsman", FakeEngine(), node="lore")
    log.notify_talk("Woodsman", FakeEngine(), node="deeper")
    assert q.progress == 1  # the node walk didn't rack up progress

    # A second, separate visit advances it to the target.
    log.notify_talk("Woodsman", FakeEngine(), node="root", opening=True)
    assert q.state == QuestState.READY


def test_talk_descriptor_survives_pickling():
    import pickle
    q = make_talk_quest(node="secret")
    restored = pickle.loads(pickle.dumps(q))
    assert restored.talk_target == "Woodsman"
    assert restored.talk_node == "secret"
