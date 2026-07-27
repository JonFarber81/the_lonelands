"""A lightweight quest tracker.

A Quest has a state machine: UNSTARTED -> ACTIVE -> (READY_TO_TURN_IN) -> DONE.
Progress is nudged by game events (kills, item pickups, arrivals) routed through
the QuestLog. Content lives in `content.py`; this is only the machinery."""
from __future__ import annotations

from enum import Enum, auto
from typing import Callable, Dict, List, Optional


class QuestState(Enum):
    UNSTARTED = auto()
    ACTIVE = auto()
    READY = auto()   # objectives met, awaiting turn-in
    DONE = auto()


class Quest:
    def __init__(
        self,
        quest_id: str,
        title: str,
        summary: str,
        objective: str,
        target_count: int = 1,
        on_complete: Optional[Callable[["object"], None]] = None,
        xp_reward: int = 0,
    ) -> None:
        self.id = quest_id
        self.title = title
        self.summary = summary
        self.objective = objective
        self.target_count = target_count
        self.progress = 0
        self.state = QuestState.UNSTARTED
        self.on_complete = on_complete
        self.xp_reward = xp_reward

    def __getstate__(self) -> dict:
        """Drop the (unpicklable) on_complete callback; savegame._rehydrate
        restores it by quest id on load."""
        state = self.__dict__.copy()
        state["on_complete"] = None
        return state

    @property
    def is_active(self) -> bool:
        return self.state in (QuestState.ACTIVE, QuestState.READY)

    def advance(self, amount: int = 1) -> None:
        if self.state != QuestState.ACTIVE:
            return
        self.progress = min(self.target_count, self.progress + amount)
        if self.progress >= self.target_count:
            self.state = QuestState.READY

    def status_line(self) -> str:
        if self.state == QuestState.DONE:
            return f"[x] {self.title} — complete"
        if self.state == QuestState.READY:
            return f"[!] {self.title} — return and report"
        return f"[ ] {self.title} — {self.objective} ({self.progress}/{self.target_count})"


class QuestLog:
    def __init__(self) -> None:
        self.quests: Dict[str, Quest] = {}

    def register(self, quest: Quest) -> None:
        self.quests[quest.id] = quest

    def get(self, quest_id: str) -> Optional[Quest]:
        return self.quests.get(quest_id)

    def start(self, quest_id: str) -> None:
        q = self.quests.get(quest_id)
        if q and q.state == QuestState.UNSTARTED:
            q.state = QuestState.ACTIVE

    def is_active(self, quest_id: str) -> bool:
        q = self.quests.get(quest_id)
        return bool(q and q.is_active)

    def is_ready(self, quest_id: str) -> bool:
        q = self.quests.get(quest_id)
        return bool(q and q.state == QuestState.READY)

    def is_done(self, quest_id: str) -> bool:
        q = self.quests.get(quest_id)
        return bool(q and q.state == QuestState.DONE)

    def turn_in(self, quest_id: str, engine) -> bool:
        q = self.quests.get(quest_id)
        if q and q.state == QuestState.READY:
            q.state = QuestState.DONE
            if q.on_complete:
                q.on_complete(engine)
            if q.xp_reward and engine.player.hero:
                engine.player.hero.add_xp(q.xp_reward)
                engine.message_log.add_message(
                    f"Quest complete: {q.title} (+{q.xp_reward} experience).",
                    (0x4A, 0x6E, 0x9A),
                )
            return True
        return False

    def active_quests(self) -> List[Quest]:
        return [q for q in self.quests.values() if q.is_active]

    def notify_kill(self, name: str, engine) -> None:
        for q in self.quests.values():
            if q.state == QuestState.ACTIVE and getattr(q, "kill_target", None) == name:
                q.advance()
                self._progress_msg(q, engine)

    def notify_event(self, tag: str, engine) -> None:
        for q in self.quests.values():
            if q.state == QuestState.ACTIVE and getattr(q, "event_tag", None) == tag:
                q.advance()
                self._progress_msg(q, engine)

    @staticmethod
    def _held_item(engine, item_name: str):
        """The player's pack slot matching item_name, or None."""
        for item in engine.player.inventory.items:
            if item.name == item_name:
                return item
        return None

    def _deliverable(self, npc_name: str, engine):
        """The (quest, held_item) a hand-over to npc_name could fire right now,
        or None: an ACTIVE delivery quest that wants its item couriered to this
        NPC, with that item in the player's pack. Shared by can_deliver (which
        only asks *whether*) and notify_delivery (which acts on it)."""
        for q in self.quests.values():
            if (q.state == QuestState.ACTIVE
                    and getattr(q, "deliver_to", None) == npc_name
                    and getattr(q, "deliver_item", None)):
                item = self._held_item(engine, q.deliver_item)
                if item is not None:
                    return q, item
        return None

    def can_deliver(self, npc_name: str, engine) -> bool:
        """True when the player could hand a quest item to this NPC now — used to
        `show` the hand-over dialog option only when the hand-over is possible."""
        return self._deliverable(npc_name, engine) is not None

    def notify_delivery(self, npc_name: str, engine) -> bool:
        """Hand a carried item to the NPC being spoken to: consume it from the
        pack and advance the matching delivery quest (the courier mirror of
        notify_kill/notify_event). Returns True if a hand-over fired. Callers
        fire rewards with the usual turn_in once the quest is READY."""
        match = self._deliverable(npc_name, engine)
        if match is None:
            return False
        quest, item = match
        engine.player.inventory.remove(item)
        quest.advance()
        self._progress_msg(quest, engine)
        return True

    @staticmethod
    def _progress_msg(q: Quest, engine) -> None:
        if q.state == QuestState.READY:
            engine.message_log.add_message(
                f"You have done what was asked: {q.title}.", (0xE6, 0xC1, 0x5A)
            )
        else:
            engine.message_log.add_message(
                f"{q.title}: {q.progress}/{q.target_count}", (0x9A, 0xC7, 0xE0)
            )
