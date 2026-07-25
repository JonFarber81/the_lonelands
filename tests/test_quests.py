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


class FakeEngine:
    def __init__(self, hero=None):
        self.message_log = FakeMessageLog()
        self.player = type("P", (), {"hero": hero})()


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
