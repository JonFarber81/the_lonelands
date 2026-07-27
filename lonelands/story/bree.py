"""Quests, speaking characters, and dialog trees for Bree — the hub town at the
meeting of the roads — and the quests given there (the main barrow-quest that
sends the hero west to Tyrn Gorthad, and Halbarad's wolf/orc bounties).

Setting: TA 2965. Bree is peopled accurately for that year — the Prancing Pony
is kept by a Butterbur (an ancestor of the Barliman of later days), and Rangers
of the North lodge there. Canon detail is left thin on purpose, to be enriched
later from the TOR Bree supplement; do not invent hard lore here.
"""
from __future__ import annotations

import copy
from typing import List

from lonelands import color, content
from lonelands.barks import BarkField, BarkSource
from lonelands.entity import Actor
from lonelands.quests import Quest
from lonelands.story._helpers import make_npc, make_signpost, opt
from lonelands.story.patrons import make_patrons  # re-exported for procgen


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
    return make_npc("@", color.npc_c, "Dírhael the Elder", "Elder of the Dúnedain", tree)


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
        herb = copy.deepcopy(content.healing_herbs)
        herb.parent = engine.player.inventory
        engine.player.inventory.items.append(herb)
        herb2 = copy.deepcopy(content.athelas)
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
    return make_npc("@", (0xC8, 0x9A, 0xB0), "Mistress Rushlight", "Herb-wife of Bree", tree)


# ---------------------------------------------------------------------------
# Halbarad — kinsman, trader, side-quests
# ---------------------------------------------------------------------------
def make_halbarad() -> Actor:
    def q(engine):
        return engine.quest_log

    def open_shop(engine):
        from lonelands import affixes, input_handlers
        # Stock is item references; buy/sell prices derive from each item's Value.
        stock = [
            content.short_sword, content.war_spear, content.buckler,
            content.leather_gear, content.travellers_hood, content.ranger_star,
            content.healing_herbs, content.athelas, content.lembas,
            content.hunting_dagger,
        ]
        # A couple of finer wares Halbarad has come by — rolled affixed gear, its
        # richer Value flowing straight into the buy price (ADR 0005, #40).
        stock += [
            affixes.generate(content.short_sword, rarity=affixes.FINE),
            affixes.generate(content.leather_gear, rarity=affixes.RARE),
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
    return make_npc("@", color.ranger_green, "Halbarad", "Ranger of the North", tree)


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
                    "East on the Great East Road you'll pass our little Bree-land "
                    "villages — Combe and Staddle on the Hill's far shoulder, and the "
                    "lonely Forsaken Inn beyond — before ever you climb to Weathertop. "
                    "North lies the Chetwood, and Archet under its eaves; south the "
                    "downs along the Greenway. Just walk out and keep going; you'll pass "
                    "into whichever land you're headed.\"",
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
    return make_npc("@", (0xC8, 0xA0, 0x62), "Butterbur", "Keeper of the Prancing Pony", tree)


# ---------------------------------------------------------------------------
# Cob the fletcher — bows, arrows, and the marksman's trade (ADR 0006)
# ---------------------------------------------------------------------------
def make_fletcher() -> Actor:
    def open_shop(engine):
        from lonelands import input_handlers
        # Arrows sell one shaft at a time (a coin apiece); a longbow for the
        # Ranger who would strike from afar, and a spare shortbow besides.
        stock = [
            content.longbow, content.shortbow, content.arrows,
        ]
        return input_handlers.ShopHandler(engine, "Cob's fletchery", stock)

    tree = {
        "root": {
            "text": "Cob the fletcher sits amid shavings and feathers, binding a "
                    "shaft between blunt, clever fingers.\n\"Bow or shaft, wanderer? "
                    "A Ranger's no good without both, and I've the best in Bree.\"",
            "options": [
                opt("Show me your bows and arrows.", handler=open_shop),
                opt("What makes a good bow?", goto="craft"),
                opt("Good day to you.", goto=None),
            ],
        },
        "craft": {
            "text": "\"A shortbow's quick and true up close; a longbow carries far "
                    "and hits the harder for it. Either way, keep your quiver full — "
                    "a shaft loosed is oft a shaft you'll walk over and pick up again.\"",
            "options": [opt("(step back)", goto="root")],
        },
    }
    return make_npc("@", (0xA8, 0x8C, 0x54), "Cob", "Fletcher of Bree", tree)


def make_town_npcs() -> List[Actor]:
    return [make_elder(), make_healer(), make_halbarad(), make_innkeeper(),
            make_fletcher()]


# ---------------------------------------------------------------------------
# Harry Goatleaf — the West-gate keeper (greeting & wayfinding)
# ---------------------------------------------------------------------------
def make_gatekeeper() -> Actor:
    tree = {
        "root": {
            "text": "A stout man in a mud-coloured cloak leans from the gate-lodge, "
                    "peering at you before he lifts the bar.\n\"Harry Goatleaf, keeper "
                    "of the West-gate. We're careful who we let in these nights. "
                    "Business in Bree, is it?\"",
            "options": [
                opt("Which roads meet here?", goto="roads"),
                opt("Careful of what?", goto="wary"),
                opt("Only passing through.", goto=None),
            ],
        },
        "roads": {
            "text": "\"This gate opens on the West Road — the Shire's away that way, and "
                    "the old Barrow-downs nearer, though none go there willing. North the "
                    "Greenway climbs to the Chetwood; south it runs down to the Downs. And "
                    "east the road lifts over the Hill and off to the Bree-land and the "
                    "wild lands beyond. The Pony's your first stop, whichever way you came.\"",
            "options": [opt("(step back)", goto="root")],
        },
        "wary": {
            "text": "\"Queer folk on the roads of late — and a cold out of the west mounds "
                    "that puts the wind up honest men. I keep the bar down after dark, and "
                    "I'd not walk the Downs for a pocket of silver.\"",
            "options": [opt("(step back)", goto="root")],
        },
    }
    return make_npc("@", (0x9E, 0x8A, 0x66), "Harry Goatleaf", "Keeper of the West-gate", tree)


# ---------------------------------------------------------------------------
# Bill Ferny — a shifty Bree-man loitering by his house (pure colour, TA 2965)
# ---------------------------------------------------------------------------
def make_ferny() -> Actor:
    tree = {
        "root": {
            "text": "A lean, sallow man lounges against his gatepost, picking his teeth. "
                    "His eyes go over you the way a fence prices a stolen horse.\n"
                    "\"Ferny. Bill Ferny. New in Bree, and armed. What's your trade, "
                    "stranger — and what's it worth to a man who knows the roads?\"",
            "options": [
                opt("Nothing that concerns you.", goto="rebuff"),
                opt("You know the roads?", goto="roads"),
                opt("(leave him to it)", goto=None),
            ],
        },
        "rebuff": {
            "text": "\"Suit yourself.\" He smiles without warmth. \"Only, a man alone on "
                    "these roads does well to have friends. Cheap friends. Remember old "
                    "Ferny when the dark comes down.\"",
            "options": [opt("(leave him to it)", goto=None)],
        },
        "roads": {
            "text": "\"I know 'em. Who's coming, who's going, who's paying. Word's worth "
                    "coin, and I don't give coin away.\" He looks past you, already bored. "
                    "\"Off with you. I've watching to do.\"",
            "options": [opt("(leave him to it)", goto=None)],
        },
    }
    return make_npc("@", (0x8E, 0x7A, 0x5A), "Bill Ferny", "a shifty Bree-man", tree)


# ---------------------------------------------------------------------------
# Signposts naming the quarters of the town (examinable flavor props)
# ---------------------------------------------------------------------------
def make_signposts() -> List[Actor]:
    return [
        make_signpost(
            "Bree-hill signpost",
            "A weathered board points up the rising ground.\n\"BREE-HILL — the "
            "Men's houses climb the slope; the smials of the hobbits are dug "
            "above. Mind the road; it lifts over the Hill and east to the "
            "Bree-land.\"",
        ),
        make_signpost(
            "Hobbit-holes signpost",
            "A low, round-lettered post stands where the green doors begin.\n"
            "\"THE HOBBIT-HOLES. Kindly folk, small doors. Knock, don't stoop "
            "in uninvited — and never near supper.\"",
        ),
    ]


# ---------------------------------------------------------------------------
# Ambient barks — the town's idle life overheard as the player crosses it (#54).
# Coordinates track the redrawn procgen.generate_bree (ADR 0008): the Prancing
# Pony common room ~(10,10) and its inn-yard ~(11,17), the crossing of the roads
# ~(22,22), and the hobbit-holes dug into the rise to the NE ~(35,10).
# ---------------------------------------------------------------------------
def make_barks() -> BarkField:
    return BarkField([
        BarkSource(  # the Prancing Pony's common room — the heart of the town
            10, 10, radius=8, cadence=10,
            lines=[
                "Laughter and a snatch of song roll out of the Pony's common room.",
                "Mugs thump on board and a cheer goes up somewhere in the throng.",
                "A fiddle scrapes into a jig; boots take up the beat on the boards.",
                "Butterbur's voice carries over the din — \"Coming, coming!\"",
                "The great hearth spits and roars; someone calls for more ale.",
            ],
        ),
        BarkSource(  # the inn-yard and stables
            11, 17, radius=6, cadence=13,
            lines=[
                "A pony stamps and blows in the Pony's inn-yard.",
                "The Pony's door bangs; a serving-lad hurries across the yard.",
                "Harness jingles in the stable-shadow as an ostler works.",
            ],
        ),
        BarkSource(  # the crossing of the roads, just outside the Pony
            22, 22, radius=8, cadence=15,
            lines=[
                "A cart creaks past the crossing, its driver nodding to no one.",
                "Two Bree-men stop at the roadside to argue, unhurried.",
                "A dog trots the road on some errand of its own.",
            ],
        ),
        BarkSource(  # the hobbit-holes in the rise to the north-east
            35, 10, radius=8, cadence=16,
            lines=[
                "Smoke curls from a round green door up the rise.",
                "Somewhere among the smials a hobbit calls the children in to supper.",
                "The smell of new bread drifts down from the hobbit-holes.",
            ],
        ),
    ])


# The aggregate seam every location module exposes (see story/__init__.py):
# every *authored* speaking NPC in this location, used for savegame tree
# rehydration by name. Wandering Bystanders (patrons) are deliberately absent —
# they are generated, keep their own lambda-free tree across a save, and so need
# no rehydration (CONTEXT.md, story/patrons.py).
def make_npcs() -> List[Actor]:
    return (make_town_npcs()
            + [make_gatekeeper(), make_ferny()]
            + make_signposts())
