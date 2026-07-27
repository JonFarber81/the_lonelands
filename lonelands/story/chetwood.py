"""Archet, in the eaves of the Chetwood (overworld cell (0,-1)): the northernmost
and deepest-set of the Bree-land hamlets, a village of woodwrights and coppicers
under the close-grown trees.

Setting: TA 2965. Archet-folk are Men of the old Bree-land stock, wary of the
wood and close-mouthed with strangers. No named canon individuals; no hard lore
invented. The quest here is a fetch (recover the woodwright's felling-axe lost in
the wood), riding the existing pickup-event machinery (see actions.PickupAction
and quests.notify_event); the item is placed by procgen.generate_chetwood.
"""
from __future__ import annotations

import copy
from typing import List

from lonelands import color, content
from lonelands.entity import Actor
from lonelands.quests import Quest
from lonelands.story._helpers import make_npc, make_signpost, opt


# ---------------------------------------------------------------------------
# Quest
# ---------------------------------------------------------------------------
def build_quests(engine) -> None:
    log = engine.quest_log

    def finish(eng):
        eng.message_log.add_message(
            "The old woodwright takes the felling-axe in both hands and bows his "
            "head over it a long moment.",
            color.welcome_text,
        )
        reward = copy.deepcopy(content.miruvor)
        reward.parent = eng.player.inventory
        eng.player.inventory.items.append(reward)
        eng.message_log.add_message(
            "He presses a stoppered draught upon you in thanks. (Added to your pack.)",
            color.item_c,
        )

    axe = Quest(
        "archet_axe",
        "The Woodwright's Axe",
        "Baldo the woodwright of Archet lost his father's felling-axe when fell "
        "things drove his gang from a coppice deep in the Chetwood. He would have "
        "it back — it is more to him than tools.",
        objective="recover the felling-axe from the Chetwood",
        target_count=1,
        on_complete=finish,
        xp_reward=22,
    )
    axe.event_tag = "archet_axe"
    log.register(axe)


# ---------------------------------------------------------------------------
# Archet — Baldo the woodwright, quest-giver
# ---------------------------------------------------------------------------
def make_archet_woodwright() -> Actor:
    def q(engine):
        return engine.quest_log

    tree = {
        "root": {
            "text": "Baldo, an old woodwright with hands like knotted oak, watches "
                    "you from the door of a long timber hall.\n\"Strangers keep to "
                    "the Road, mostly. You're either lost, or you're after "
                    "something. Which is it?\"",
            "options": [
                opt("Is there work for a wanderer here?", goto="quest_intro",
                    show=lambda e: q(e).get("archet_axe").state.name == "UNSTARTED"),
                opt("I found your father's felling-axe.", goto="quest_done",
                    do=lambda e: q(e).turn_in("archet_axe", e),
                    show=lambda e: q(e).is_ready("archet_axe")),
                opt("Tell me of Archet.", goto="lore"),
                opt("What lies deeper in the Chetwood?", goto="wood"),
                opt("I'll trouble you no further.", goto=None),
            ],
        },
        "quest_intro": {
            "text": "\"Work — aye, and grief with it. My gang was felling a coppice "
                    "north and east of here when the wood turned on us. Spiders, and "
                    "a cold that got into the bones. We ran, and I left my father's "
                    "axe lying in the leaf-mould. Bring it back to me and I'll not "
                    "see you go unthanked.\"",
            "options": [
                opt("I'll find your axe.", goto="quest_accept",
                    do=lambda e: q(e).start("archet_axe")),
                opt("(step back)", goto="root"),
            ],
        },
        "quest_accept": {
            "text": "\"Search the wood — deep in, where the trees grow close and the "
                    "light fails. It'll lie where we dropped our tools and ran. Go "
                    "armed, and go with your wits about you; that coppice is no "
                    "friend to the living now.\"",
            "options": [opt("I understand.", goto=None)],
        },
        "quest_done": {
            "text": "\"You went in after it. After all this... you went in.\" The "
                    "old man's voice is rough. \"That axe felled the timber that "
                    "raised half this hall. It's home now, and so, near enough, "
                    "am I in the telling of it. My thanks, wanderer — truly.\"",
            "options": [opt("It was rightly done.", goto=None)],
        },
        "lore": {
            "text": "\"Archet's the oldest of the Bree-land villages — we were "
                    "cutting these trees when Bree was three huts and a hedge. "
                    "Woodwrights, coopers, charcoal-burners. We take what the wood "
                    "gives and we give it its due. Or we did, before it soured.\"",
            "options": [opt("(step back)", goto="root")],
        },
        "wood": {
            "text": "\"The Chetwood runs on north for leagues, and it was never "
                    "wholly tame. But of late there's a watchfulness in it, and "
                    "spiders where there were none, and folk speak of a chill off "
                    "the old barrow-country to the west, as though the same shadow "
                    "reaches even here. I don't go deep any more. Nor should you, "
                    "unarmed.\"",
            "options": [opt("(step back)", goto="root")],
        },
    }
    return make_npc("@", (0x9A, 0x86, 0x5A), "Baldo the Woodwright", "Woodwright of Archet", tree)


# ---------------------------------------------------------------------------
# Bystander — colour, no shop or quest
# ---------------------------------------------------------------------------
def make_bystanders() -> List[Actor]:
    tree = {
        "root": {
            "text": "A young coppicer with a billhook eyes you from behind a "
                    "wood-stack, half-minded to bolt.\n\"You come up the Archet path "
                    "on your own? You're either brave or foolish, Road-walker.\"",
            "options": [
                opt("Why so wary?", goto="wary"),
                opt("Which way to the deep wood?", goto="deep"),
                opt("Peace to you.", goto=None),
            ],
        },
        "wary": {
            "text": "\"You'd be wary too, if you'd heard what comes out of the trees "
                    "after dark now. My uncle's gang lost their tools and near their "
                    "lives up in the north coppice. Baldo's not been the same since "
                    "— it was his old axe they left behind.\"",
            "options": [opt("(step back)", goto="root")],
        },
        "deep": {
            "text": "\"North and east, where the trees crowd close. But don't, "
                    "unless you must — the light dies in there before evening, and "
                    "the webs hang thick as washing. If you go, keep your blade "
                    "loose.\"",
            "options": [opt("(step back)", goto="root")],
        },
    }
    return [make_npc("@", (0x8A, 0x94, 0x66), "a young coppicer", "an Archet woodcutter", tree)]


# ---------------------------------------------------------------------------
# Signpost
# ---------------------------------------------------------------------------
def make_signposts() -> List[Actor]:
    return [
        make_signpost(
            "the Archet path-post",
            "A rough post at the wood's edge, an axe-blade nailed above the "
            "lettering:\n"
            "  South - COMBE, and the Bree-land\n"
            "  In - ARCHET (keep to the path)\n"
            "  Deeper - the CHETWOOD. Turn back.",
        ),
    ]


# The aggregate seam story/__init__.py fans across for savegame rehydration.
def make_npcs() -> List[Actor]:
    return [make_archet_woodwright()] + make_bystanders() + make_signposts()
