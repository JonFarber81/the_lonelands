"""Quests, speaking characters, and dialog trees for the starting Region:
the town of Bree, and the barrow-wight mounds of Tyrn Gorthad in the
Barrow-downs west of it (the ruined watchtower of Amon Sûl on Weathertop, east
along the Road, is its own ruin — see ADR 0003).

Setting: TA 2965. Bree is peopled accurately for that year — the Prancing Pony
is kept by a Butterbur (an ancestor of the Barliman of later days), and Rangers
of the North lodge there. Canon detail is left thin on purpose, to be enriched
later from the TOR Bree supplement; do not invent hard lore here.

A dialog *node* is {"text": str|callable, "options": [option, ...]}.
An *option* is a dict with:
    text   : the line the player may choose
    goto   : next node id, or None to end the conversation
    show   : optional callable(engine)->bool gating visibility
    do     : optional callable(engine)->None side effect
    handler: optional callable(engine)->EventHandler to switch UI (e.g. a shop)
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Optional

from lonelands import color, content
from lonelands.components.equipment import Equipment
from lonelands.components.inventory import Inventory
from lonelands.components.npc import NPC
from lonelands.entity import Actor
from lonelands.quests import Quest


def opt(text, goto=None, do=None, show=None, handler=None) -> Dict[str, Any]:
    return {"text": text, "goto": goto, "do": do, "show": show, "handler": handler}


# ---------------------------------------------------------------------------
# Quests
# ---------------------------------------------------------------------------
def build_quests(engine) -> None:
    log = engine.quest_log

    def finish_main(eng):
        eng.message_log.add_message(
            "Dírhael turns the silver star-brooch in his hands, eyes bright with old memory.",
            color.welcome_text,
        )
        content.miruvor.spawn(eng.player.gamemap, eng.player.x, eng.player.y)
        # place the reward straight into the pack
        reward = copy.deepcopy(content.dunedain_sword)
        reward.parent = eng.player.inventory
        eng.player.inventory.items.append(reward)
        eng.message_log.add_message(
            "He presses an heirloom blade upon you: a Dúnedain sword. (Added to your pack.)",
            color.item_c,
        )

    main = Quest(
        "main_barrow",
        "The Star of the Barrow",
        "Old Dírhael speaks of a fell chill rising from the barrow-mounds of Tyrn "
        "Gorthad, west of Bree, and of a star-brooch of Arnor lost among the wights.",
        objective="recover the star-brooch from the deep barrow",
        target_count=1,
        on_complete=finish_main,
        xp_reward=40,
    )
    main.event_tag = "heirloom"
    log.register(main)

    wolves = Quest(
        "wolves",
        "Wolves at the Wold",
        "Halbarad says grey wolves have grown bold on the hills, harrying the flocks.",
        objective="slay grey wolves in the wild",
        target_count=3,
        xp_reward=18,
    )
    wolves.kill_target = "grey wolf"
    log.register(wolves)

    orcs = Quest(
        "orcs",
        "The Crawling Dark",
        "Orcs of the mountains have crept into the old mounds. Halbarad would see their number thinned.",
        objective="slay orc soldiers in the barrow",
        target_count=4,
        xp_reward=24,
    )
    orcs.kill_target = "orc soldier"
    log.register(orcs)


# ---------------------------------------------------------------------------
# NPC factory helper
# ---------------------------------------------------------------------------
def _npc(char, col, name, title, tree) -> Actor:
    actor = Actor(char=char, color=col, name=name, ai_cls=None,
                  inventory=Inventory(0), equipment=Equipment(),
                  npc=NPC(title=title, tree=tree))
    return actor


# ---------------------------------------------------------------------------
# Dírhael the Elder — the main quest
# ---------------------------------------------------------------------------
def make_elder() -> Actor:
    def q(engine):
        return engine.quest_log

    tree = {
        "root": {
            "text": "Dírhael, an old Ranger who winters in Bree, regards you from beneath "
                    "white brows.\n\"A Ranger of the North, and travelling alone. These are "
                    "darkening days, kinsman. Sit, and tell me — or ask what you will.\"",
            "options": [
                opt("What shadow lies on this place?", goto="trouble"),
                opt("Tell me of the barrow-downs.", goto="ruins_lore"),
                opt("I will go into the barrow. What must I find?",
                    goto="quest_given",
                    do=lambda e: q(e).start("main_barrow"),
                    show=lambda e: q(e).get("main_barrow").state.name == "UNSTARTED"),
                opt("I have recovered the star-brooch of Arnor.",
                    goto="quest_done",
                    do=lambda e: q(e).turn_in("main_barrow", e),
                    show=lambda e: q(e).is_ready("main_barrow")),
                opt("The road calls. Farewell.", goto=None),
            ],
        },
        "trouble": {
            "text": "\"A cold has come out of the old barrow-downs west of here — Tyrn "
                    "Gorthad, the green mounds where the last men of Cardolan were laid. "
                    "The dead do not lie quiet, and fell things have crept into the "
                    "mounds. The Bree-folk bar their doors after dark.\"",
            "options": [
                opt("And you would have me go down there.", goto="quest_given",
                    do=lambda e: q(e).start("main_barrow"),
                    show=lambda e: q(e).get("main_barrow").state.name == "UNSTARTED"),
                opt("Tell me more of the mounds.", goto="ruins_lore"),
                opt("(step back)", goto="root"),
            ],
        },
        "ruins_lore": {
            "text": "\"In the last days of Cardolan its princes were laid in the barrows "
                    "of Tyrn Gorthad. When that realm failed, the Witch-king sent evil "
                    "spirits — barrow-wights — into the mounds, and they have haunted them "
                    "ever since. Deepest of all lies a star-brooch, the token of the last "
                    "prince. Recover it, and perhaps the chill will lift.\"",
            "options": [
                opt("I will find it.", goto="quest_given",
                    do=lambda e: q(e).start("main_barrow"),
                    show=lambda e: q(e).get("main_barrow").state.name == "UNSTARTED"),
                opt("(step back)", goto="root"),
            ],
        },
        "quest_given": {
            "text": "\"Walk west out of Bree, past the eaves of the Old Forest, into the "
                    "Barrow-downs — you'll find a broken barrow-arch among the mounds. Go "
                    "carefully, and go with hope. The star-brooch will be deepest of all, "
                    "where the cold is thickest.\"",
            "options": [opt("I will not fail.", goto=None)],
        },
        "quest_done": {
            "text": "\"So. The star of the last warden comes home.\" The old man's voice "
                    "shakes. \"You have done a deed the songs will not forget, Tarandir.\"",
            "options": [opt("It was rightly done.", goto=None)],
        },
    }
    return _npc("@", color.npc_c, "Dírhael the Elder", "Elder of the Dúnedain", tree)


# ---------------------------------------------------------------------------
# The herb-wife of Bree — healing & Hope
# ---------------------------------------------------------------------------
def make_healer() -> Actor:
    def heal(engine):
        p = engine.player
        healed = p.fighter.heal(p.fighter.max_endurance)
        p.fighter.bleed = 0
        engine.message_log.add_message(
            f"The herb-wife's care mends you (+{healed} endurance) and staunches "
            f"your wounds.",
            color.health_recovered,
        )

    def give_herbs(engine, tag="herbwife_gift"):
        if engine.flags.get(tag):
            engine.message_log.add_message("\"I have given what I can spare, friend.\"", color.gray)
            return
        engine.flags[tag] = True
        import copy as _c
        herb = _c.deepcopy(content.healing_herbs)
        herb.parent = engine.player.inventory
        engine.player.inventory.items.append(herb)
        herb2 = _c.deepcopy(content.athelas)
        herb2.parent = engine.player.inventory
        engine.player.inventory.items.append(herb2)
        engine.message_log.add_message(
            "The herb-wife presses healing herbs and a sprig of athelas into your hand.",
            color.item_c,
        )

    tree = {
        "root": {
            "text": "Mistress Rushlight, the herb-wife of Bree, looks up from her "
                    "drying-racks, the air sharp with the scent of kingsfoil.\n\"You've "
                    "the look of the long road on you. What do you need, wanderer?\"",
            "options": [
                opt("Tend my hurts, if you would.", goto="root", do=heal),
                opt("Might you spare some herbs?", goto="root", do=give_herbs),
                opt("What is athelas?", goto="athelas"),
                opt("Thank you. Farewell.", goto=None),
            ],
        },
        "athelas": {
            "text": "\"Kingsfoil, some call it — a weed to most. But in the right hands it "
                    "cleans a wound and drives back the black breath of fell things. Carry "
                    "some into that barrow; you'll bless me for it.\"",
            "options": [opt("(step back)", goto="root")],
        },
    }
    return _npc("@", (0xC8, 0x9A, 0xB0), "Mistress Rushlight", "Herb-wife of Bree", tree)


# ---------------------------------------------------------------------------
# Halbarad — kinsman, trader, side-quests
# ---------------------------------------------------------------------------
def make_halbarad() -> Actor:
    def q(engine):
        return engine.quest_log

    def open_shop(engine):
        from lonelands import input_handlers
        # Stock is item references; buy/sell prices derive from each item's Value.
        stock = [
            content.short_sword, content.war_spear, content.buckler,
            content.leather_gear, content.travellers_hood,
            content.healing_herbs, content.athelas, content.lembas,
            content.hunting_dagger,
        ]
        return input_handlers.ShopHandler(engine, "Halbarad's stores", stock)

    tree = {
        "root": {
            "text": "Halbarad leans on a spear by the hedge, grey-cloaked as you are.\n"
                    "\"Well met, cousin. Few of our folk pass through Bree these days. I "
                    "keep what gear I can for those who walk the Wild. What's your need?\"",
            "options": [
                opt("Show me your wares.", handler=open_shop),
                opt("You spoke of wolves?", goto="wolves_intro",
                    show=lambda e: q(e).get("wolves").state.name == "UNSTARTED"),
                opt("The wolves are dealt with.", goto="wolves_done",
                    do=lambda e: q(e).turn_in("wolves", e),
                    show=lambda e: q(e).is_ready("wolves")),
                opt("Is there other work?", goto="orcs_intro",
                    show=lambda e: (q(e).get("orcs").state.name == "UNSTARTED"
                                    and q(e).get("main_barrow").is_active)),
                opt("The orcs are fewer now.", goto="orcs_done",
                    do=lambda e: q(e).turn_in("orcs", e),
                    show=lambda e: q(e).is_ready("orcs")),
                opt("Farewell, kinsman.", goto=None),
            ],
        },
        "wolves_intro": {
            "text": "\"Grey wolves off the Weather Hills — bolder than they ought to be, "
                    "as if something drives them. Thin their number out in the wild and "
                    "I'll see you rewarded.\"",
            "options": [
                opt("I'll hunt them.", goto=None, do=lambda e: q(e).start("wolves")),
                opt("(step back)", goto="root"),
            ],
        },
        "wolves_done": {
            "text": "\"Good work. The flocks will rest easier.\" He clasps your arm.",
            "options": [opt("(step back)", goto="root")],
        },
        "orcs_intro": {
            "text": "\"Since you're bound for the barrow anyway — every orc-soldier you "
                    "put down is one fewer to trouble Bree. Bring me word of four, and "
                    "I'll not forget it.\"",
            "options": [
                opt("Consider it done.", goto=None, do=lambda e: q(e).start("orcs")),
                opt("(step back)", goto="root"),
            ],
        },
        "orcs_done": {
            "text": "\"Four fewer, and the songs a little longer. Well struck, cousin.\"",
            "options": [opt("(step back)", goto="root")],
        },
    }
    return _npc("@", color.ranger_green, "Halbarad", "Ranger of the North", tree)


# ---------------------------------------------------------------------------
# Butterbur — keeper of the Prancing Pony (rumour & wayfinding)
# ---------------------------------------------------------------------------
def make_innkeeper() -> Actor:
    tree = {
        "root": {
            "text": "The stout keeper of the Prancing Pony bustles over, wiping his hands "
                    "on his apron.\n\"Welcome, welcome! Butterbur's the name, and this is "
                    "the Pony — best beds and beer in Bree-land. What'll it be?\"",
            "options": [
                opt("Which way lies the Wild?", goto="roads"),
                opt("Any news on the roads?", goto="rumour"),
                opt("Where might I resupply?", goto="hint"),
                opt("My thanks.", goto=None),
            ],
        },
        "roads": {
            "text": "\"Bree sits where the roads cross, see. Walk west and you come to the "
                    "old Barrow-downs — that's where your barrow is, if you're set on it. "
                    "East on the Great East Road climbs to Weathertop and the Weather "
                    "Hills, north lies the Chetwood, south the downs along the Greenway. "
                    "Just walk out and keep going; you'll pass into whichever land you're "
                    "headed.\"",
            "options": [opt("(step back)", goto="root")],
        },
        "rumour": {
            "text": "\"Wolves bolder than they ought to be, and a chill out of those old "
                    "barrow-downs west of here. Rangers come and go — grey folk, quiet "
                    "folk. Old Dírhael's one, and he's got that far-off look tonight.\"",
            "options": [opt("(step back)", goto="root")],
        },
        "hint": {
            "text": "\"Mistress Rushlight has herbs by her cot, and that Ranger Halbarad "
                    "keeps gear for Wild-walkers. Speak with old Dírhael before you go — "
                    "he knows the deep history of those mounds.\"",
            "options": [opt("(step back)", goto="root")],
        },
    }
    return _npc("@", (0xC8, 0xA0, 0x62), "Butterbur", "Keeper of the Prancing Pony", tree)


def make_town_npcs() -> List[Actor]:
    return [make_elder(), make_healer(), make_halbarad(), make_innkeeper()]
