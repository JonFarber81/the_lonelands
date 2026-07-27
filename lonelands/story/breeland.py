"""The Bree-land east of the Hill (overworld cell (1,0)): the little hamlets of
**Combe** and **Staddle** on the slopes of Bree-hill, and the lonely **Forsaken
Inn** further out along the Great East Road.

Setting: TA 2965, as with Bree. The folk here bear the old Bree-land family
names (Heathertoes, Mugwort, Sandheaver, Tunnelly, Ferny) with invented given
names — no named canon individuals, and no hard lore invented. Staddle is a
hobbit hamlet; Combe a woodsman-village of Men; the Forsaken Inn a half-suspect
waystation where a Blue-Mountain Dwarf keeps a trading-stall.

Quests here stay within the existing kill/event machinery (see quests.py); the
richer objective types are tracked as issues #50–#53.
"""
from __future__ import annotations

from typing import List

from lonelands import color, content
from lonelands.entity import Actor
from lonelands.quests import Quest
from lonelands.story._helpers import make_npc, make_signpost, opt


# ---------------------------------------------------------------------------
# Quests
# ---------------------------------------------------------------------------
def build_quests(engine) -> None:
    log = engine.quest_log

    combe = Quest(
        "combe_spiders",
        "Shadows in the Coppice",
        "Todi Heathertoes of Combe says great spiders have crept down out of the "
        "Chetwood into the coppices, and no woodsman dares the north eaves.",
        objective="slay great spiders in the wild",
        target_count=3,
        xp_reward=20,
    )
    combe.kill_target = "great spider"
    log.register(combe)

    road = Quest(
        "road_east",
        "The Road Runs Red",
        "Thulin the Dwarf-trader has lost pack-beasts to wargs on the East Road; "
        "he would see the brutes thinned before he ventures on toward the Fords.",
        objective="slay wargs on the roads east",
        target_count=3,
        xp_reward=24,
    )
    road.kill_target = "warg"
    log.register(road)


# ---------------------------------------------------------------------------
# Combe — Todi Heathertoes, woodsman & quest-giver
# ---------------------------------------------------------------------------
def make_combe_woodsman() -> Actor:
    def q(engine):
        return engine.quest_log

    tree = {
        "root": {
            "text": "Todi Heathertoes leans on a long-handled axe outside a "
                    "timber-and-thatch house, sawdust in his beard.\n\"You're no "
                    "Combe man. Come up from Bree, have you? Well — there's little "
                    "cheer in Combe this season, I'll tell you that for nothing.\"",
            "options": [
                opt("What troubles Combe?", goto="trouble",
                    show=lambda e: q(e).get("combe_spiders").state.name == "UNSTARTED"),
                opt("I'll clear the coppice of spiders.", goto="quest_given",
                    do=lambda e: q(e).start("combe_spiders"),
                    show=lambda e: q(e).get("combe_spiders").state.name == "UNSTARTED"),
                opt("The spiders are dealt with.", goto="quest_done",
                    do=lambda e: q(e).turn_in("combe_spiders", e),
                    show=lambda e: q(e).is_ready("combe_spiders")),
                opt("Tell me of Combe.", goto="lore"),
                opt("Good day to you.", goto=None),
            ],
        },
        "trouble": {
            "text": "\"Great spiders — ugh. Crept down out of the Chetwood into our "
                    "coppices, thick as your fist and quick as sin. Two of my gang "
                    "won't go north of the beck now, and firewood's not cutting "
                    "itself. Thin them out in the wild and I'll pay what I can.\"",
            "options": [
                opt("I'll hunt them.", goto="quest_given",
                    do=lambda e: q(e).start("combe_spiders")),
                opt("(step back)", goto="root"),
            ],
        },
        "quest_given": {
            "text": "\"Look to the north eaves, toward the Chetwood — that's where "
                    "they web up thickest. Mind their bite; there's a venom in it "
                    "that won't let a wound close. Go careful, Bree-man.\"",
            "options": [opt("I'll be careful.", goto=None)],
        },
        "quest_done": {
            "text": "\"Fewer of the crawling things? The lads will bless you for it. "
                    "Here — it's little, but it's honest coin.\" He grips your hand.",
            "options": [opt("(step back)", goto="root")],
        },
        "lore": {
            "text": "\"Combe sits in the fold of the hill, out of the wind. Quiet "
                    "place — we cut wood and mind our own, and let Bree do the "
                    "talking. Archet's north of us, deeper in the trees; queerer "
                    "folk up there, but good enough.\"",
            "options": [opt("(step back)", goto="root")],
        },
    }
    return make_npc("@", (0x8C, 0x9E, 0x6A), "Todi Heathertoes", "Woodsman of Combe", tree)


# ---------------------------------------------------------------------------
# Staddle — Rollo Tunnelly, hobbit provisioner (shop)
# ---------------------------------------------------------------------------
def make_staddle_provisioner() -> Actor:
    def open_shop(engine):
        from lonelands import input_handlers
        stock = [
            content.pipe_weed, content.lembas, content.healing_herbs, content.athelas,
        ]
        return input_handlers.ShopHandler(engine, "Tunnelly's larder", stock)

    tree = {
        "root": {
            "text": "Rollo Tunnelly, a stout hobbit of Staddle, stands in a low "
                    "green door with a pipe already lit.\n\"Well now! A big person, "
                    "all the way up the Staddle lane. You'll be wanting victuals, or "
                    "leaf — folk always want one or the other. What'll it be?\"",
            "options": [
                opt("Show me your larder.", handler=open_shop),
                opt("Tell me of Staddle.", goto="lore"),
                opt("What's this Southlinch leaf?", goto="leaf"),
                opt("Good day, master hobbit.", goto=None),
            ],
        },
        "lore": {
            "text": "\"Staddle? Oldest holes in the Bree-land, these — hobbits dug "
                    "in the south slope before ever the Big Folk raised the Pony. "
                    "Quiet, warm, and out of the wind. We keep to ourselves, mostly, "
                    "and we eat well. That's the whole of it.\"",
            "options": [opt("(step back)", goto="root")],
        },
        "leaf": {
            "text": "\"Southlinch! Grown right here on the sunny slope — best leaf in "
                    "the Bree-land, and don't let a Shire-hobbit tell you otherwise. "
                    "A pipe of it after a long road, and the aches just... loosen. "
                    "You'll see.\"",
            "options": [opt("(step back)", goto="root")],
        },
    }
    return make_npc("@", (0x8E, 0xB0, 0x6E), "Rollo Tunnelly", "Provisioner of Staddle", tree)


# ---------------------------------------------------------------------------
# The Forsaken Inn — Mat Ferny, keeper (rest & rumour)
# ---------------------------------------------------------------------------
def make_forsaken_innkeeper() -> Actor:
    def rest(engine):
        p = engine.player
        healed = p.fighter.heal(14)
        engine.message_log.add_message(
            f"You take a room and a hot meal at the Forsaken Inn; the road's ache "
            f"eases (+{healed} endurance).",
            color.health_recovered,
        )

    tree = {
        "root": {
            "text": "The keeper of the Forsaken Inn eyes you over a guttering "
                    "candle.\n\"Ferny's the name. We don't see many honest faces "
                    "this far out — nor many faces at all. Bed? Beer? Or are you "
                    "just here to drip on my floor?\"",
            "options": [
                opt("Take a room and let me rest.", goto="root", do=rest),
                opt("What news on the road east?", goto="rumour"),
                opt("Who's the Dwarf at the corner stall?", goto="dwarf"),
                opt("Nothing. Farewell.", goto=None),
            ],
        },
        "rumour": {
            "text": "\"East? Bad ground and worse company. Wargs off the moors have "
                    "grown bold — took one of the Dwarf's pack-ponies not three "
                    "nights gone, right off the Road. Folk don't walk to Weathertop "
                    "alone these days, and them that do don't always walk back.\"",
            "options": [opt("(step back)", goto="root")],
        },
        "dwarf": {
            "text": "\"Thulin? Blue-Mountain Dwarf, works the Road between the "
                    "Ered Luin and the east. Hard bargainer, close with his words, "
                    "but his steel's honest — which is more than I'll say for most "
                    "that stop here. Talk to him if you've coin.\"",
            "options": [opt("(step back)", goto="root")],
        },
    }
    return make_npc("@", (0xB0, 0x9A, 0x74), "Mat Ferny", "Keeper of the Forsaken Inn", tree)


# ---------------------------------------------------------------------------
# The Forsaken Inn — Thulin, Blue-Mountain Dwarf-trader (shop + road quest)
# ---------------------------------------------------------------------------
def make_dwarf_trader() -> Actor:
    def q(engine):
        return engine.quest_log

    def open_shop(engine):
        from lonelands import input_handlers
        stock = [
            content.dwarf_axe, content.mail_corslet, content.buckler,
            content.hunting_dagger, content.miruvor,
        ]
        return input_handlers.ShopHandler(engine, "Thulin's trading-stall", stock)

    tree = {
        "root": {
            "text": "A broad, iron-bearded Dwarf sits behind a stall of stacked "
                    "wares, arms folded.\n\"Thulin, of the Blue Mountains. You have "
                    "the look of one who breaks gear faster than he pays for it. "
                    "Still — coin is coin. Trade, or talk?\"",
            "options": [
                opt("Show me your wares.", handler=open_shop),
                opt("You've had trouble on the Road?", goto="quest_intro",
                    show=lambda e: q(e).get("road_east").state.name == "UNSTARTED"),
                opt("The wargs are fewer now.", goto="quest_done",
                    do=lambda e: q(e).turn_in("road_east", e),
                    show=lambda e: q(e).is_ready("road_east")),
                opt("What brings a Dwarf so far out?", goto="lore"),
                opt("Trade well, master Dwarf.", goto=None),
            ],
        },
        "quest_intro": {
            "text": "\"Trouble? Wargs. Great grey brutes off the moors — they took a "
                    "pony of mine and half its load with it, and I'll not cross to "
                    "the Fords until the Road's clear. Cut down three of them out "
                    "east, and I'll open my strongbox to you. A Dwarf pays his "
                    "debts.\"",
            "options": [
                opt("I'll clear the Road.", goto=None,
                    do=lambda e: q(e).start("road_east")),
                opt("(step back)", goto="root"),
            ],
        },
        "quest_done": {
            "text": "\"Three wargs the less. That is well done, and Dwarves do not "
                    "forget a good turn.\" He counts coin into your palm without a "
                    "word of haggling — a rare honour.",
            "options": [opt("(step back)", goto="root")],
        },
        "lore": {
            "text": "\"We have always walked this Road — the Blue Mountains to the "
                    "west, and kin and custom away east. Bree grows fat on our "
                    "passing trade and never thinks on who keeps the axes sharp. "
                    "No matter. The Road pays, when it is not trying to kill you.\"",
            "options": [opt("(step back)", goto="root")],
        },
    }
    return make_npc("@", (0xC8, 0x9A, 0x5A), "Thulin", "Dwarf-trader of the Blue Mountains", tree)


# ---------------------------------------------------------------------------
# Bystanders — colour, no shop or quest (single-sourced so make_npcs matches
# what procgen spawns, and savegame can rehydrate their trees by name).
# ---------------------------------------------------------------------------
def _flavor_npc(char, col, name, title, intro, lines) -> Actor:
    """A bystander with an intro node and a couple of throwaway remarks."""
    tree = {
        "root": {
            "text": intro,
            "options": [opt(prompt, goto=key) for key, (prompt, _) in lines.items()]
                       + [opt("Farewell.", goto=None)],
        },
    }
    for key, (_, said) in lines.items():
        tree[key] = {"text": said, "options": [opt("(step back)", goto="root")]}
    return make_npc(char, col, name, title, tree)


def make_bystanders() -> List[Actor]:
    return [
        _flavor_npc(
            "@", (0x8E, 0xB0, 0x6E), "Nib Sandheaver", "a hobbit of Staddle",
            "A round-faced hobbit-lass looks up from weeding a row of pipe-weed.\n"
            "\"Mind the plants, big person!\"",
            {
                "weed": ("What are you growing?",
                         "\"Southlinch, o' course — south slope's the only place it "
                         "takes proper. Da says the Bree market'd dry up without us. "
                         "I say they'd notice soon enough if the leaf stopped!\""),
                "quiet": ("Is it always so quiet here?",
                          "\"Staddle? Quiet's the whole point of Staddle. You want "
                          "noise, that's what Bree's for. We'll take our gardens and "
                          "our suppers, thank you kindly.\""),
            },
        ),
        _flavor_npc(
            "@", (0x9A, 0x8E, 0x60), "Mattock Mugwort", "a farmer of Combe",
            "A weather-beaten farmer straightens from a fence-line, eyeing the wood.\n"
            "\"Grim season, stranger. Grim season.\"",
            {
                "wood": ("Why do you watch the wood so?",
                         "\"Because things watch back, that's why. Wasn't always so. "
                         "The Chetwood kept its own and we kept ours. Now there's a "
                         "creeping in it that I don't like — spiders, and worse "
                         "talked of. You mind the trees, hear?\""),
                "archet": ("What of Archet, further in?",
                           "\"Archet-folk are woodwrights, born to the trees — but "
                           "even they've gone close-mouthed and careful. When Archet "
                           "gets nervous, a wise man locks his door.\""),
            },
        ),
        _flavor_npc(
            "@", (0xA6, 0x9C, 0x84), "a lean pedlar", "a road-worn traveller",
            "A thin, travel-stained man nurses a mug in the darkest corner of the "
            "inn.\n\"Sit, or don't. Road's no safer for company, but the ale's no "
            "worse.\"",
            {
                "road": ("How fares the road east?",
                         "\"Ill. I came through from the Last Bridge and I'll not go "
                         "back without a stouter escort than my own two feet. "
                         "Something's stirred up the wild between here and the "
                         "Weather Hills. Wolves that hunt like they're herded.\""),
                "rumour": ("Any other news?",
                           "\"Rangers on the move — grey shapes on the downs at "
                           "dusk, gone when you look twice. Whatever they're watching "
                           "for, I'd rather be behind a locked door when it comes.\""),
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Signposts — examinable wayfinding/flavor props (unique names so savegame
# rehydrates each one's text correctly by name).
# ---------------------------------------------------------------------------
def make_signposts() -> List[Actor]:
    return [
        make_signpost(
            "the Bree-land crossroads post",
            "A leaning fingerpost, its arms carved and re-carved over the years:\n"
            "  West - BREE, at the crossing\n"
            "  East - the Forsaken Inn, and WEATHERTOP beyond\n"
            "  North - COMBE, and the CHETWOOD and ARCHET past it\n"
            "  South - STADDLE",
        ),
        make_signpost(
            "the East Road milestone",
            "A worn stone half-sunk in the verge. Someone has scratched below the "
            "old Arnorian mark:\n  \"FORSAKEN INN AHEAD. BOLT THE DOOR.\"",
        ),
    ]


# The aggregate seam story/__init__.py fans across for savegame rehydration.
def make_npcs() -> List[Actor]:
    return [
        make_combe_woodsman(), make_staddle_provisioner(),
        make_forsaken_innkeeper(), make_dwarf_trader(),
    ] + make_bystanders() + make_signposts()
