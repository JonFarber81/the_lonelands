# Our own system: a d20 core, perk-Paths, and legible loot

The game's rules were adapted closely from **The One Ring** (TOR): a d12 Feat
die + d6 Success-dice pool, the three TOR attributes (Strength/Heart/Wits) and
eighteen named skills, Hope/Shadow, and a quests-only XP economy. We are
**de-coupling from TOR** — keeping the Middle-earth *setting* but replacing the
*system* with our own, for two reasons: (1) to avoid leaning on TOR's
distinctive expression (its dice, its named skills, Hope/Shadow, Valour/Wisdom),
and (2) because the pool mechanic is structurally poor at the one thing we most
want a roguelike to deliver — **legible, frequent progression** you can *see* in
a level-up and read off a piece of gear.

Game *mechanics* are not copyrightable — only expression is — so this is driven
primarily by game-feel; the rename is what discharges the TOR association. (The
Tolkien *setting* — Bree, the Dúnedain, Eriador — is a separate, larger
copyright question we are knowingly setting aside.)

## Decisions

- **A d20 resolution core replaces the Feat+Success pool.** Every action is a
  **Check**: `d20 + attribute (+ perk/gear) vs a Target Number`. Combat is the
  same primitive: an **Attack roll** of `d20 + attack bonus vs the foe's
  Defence`; on a hit, roll **weapon damage − armour soak**. A **natural 20** is a
  **Critical** (auto-hit + bonus damage); a **natural 1** is a **Fumble**
  (auto-miss). **Advantage/Disadvantage** (roll 2d20, keep high/low) replaces
  favoured/ill-favoured. *Rejected:* keeping the pool and only renaming the faces
  — it stays illegible (one more d6 is an invisible shift in a distribution, not
  a number that "went up"); and a 3d6/percentile core — less swing but weaker
  crit moments, and no closer to the see-it-improve goal than a d20.
- **Three attributes, no skills, no proficiencies.** The eighteen-skill
  point-buy layer and the five weapon proficiencies are **deleted**. Attributes
  become small modifiers on the d20: **Brawn** (melee hit/damage, HP, athletics)
  · **Wits** (ranged, Defence, stealth, senses) · **Will** (morale, social,
  healing, path abilities). *Note:* "Wits" overlaps one of TOR's three attribute
  names; kept deliberately for readability. All specialisation moves into perks.
- **Advancement is perks bought from five Ranger Paths.** Levelling is
  **frequent and mostly automatic** (each level: +HP, periodic +to-hit) and
  **punctuated by a perk point every few levels**. Perk points are spent from
  five themed **Paths** — *The Long Watch* (endure/protect), *The Swift Wrath*
  (melee offence), *The Far Shot* (marksman), *The Hidden Path* (stealth/ambush),
  *The Kindled Heart* (spirit/defiance). A Ranger **blends freely** across Paths;
  deeper perks require prior investment *in that Path*, and capstones require
  real commitment. *Rejected:* a random draft (it is "pick", not "buy", and
  forbids build-planning); weapon-typed trees (less evocative than Ranger
  "styles"); one-Path-only (kills hybrid builds).
- **Kills grant XP again — supersedes the no-XP rule of ADR 0004.** Slaying foes
  grants XP; quests grant larger chunks. The material **loot/coin economy of ADR
  0004 stays intact** as a *parallel* reward — a kill can pay in both XP and
  goods. Only ADR 0004's "routine foes grant no experience" decision is
  reversed; its Value/loot-table/stacking machinery is untouched.
- **One HP pool; Wounds become a status, not a second death track.**
  **Endurance** is the single vitality pool, grows with level, and **0 = death**.
  The TOR two-Wound mortal track is dropped; a **Bleed/crippled status** (from
  Criticals or heavy foes) is the remaining "serious injury" texture.
- **Cut Hope, Shadow/Misery, Valour, Wisdom.** No spendable meta-currency and no
  corruption track. Perk actives run on **charges/cooldowns**. *The Kindled
  Heart* is therefore built from cooldown/charge/trigger abilities (daunt, a
  self-heal charge, a dread aura, rally-at-low-HP), not Hope regeneration.
  *Rejected:* keeping a renamed Hope+corruption pair (more bookkeeping, a
  punishing-feeling system against the arcade-roguelike direction).
- **Equipment is legible and procedurally affixed.** Gear shows its full stat
  line on pickup — **no identification**. Weapons carry **+hit, damage dice, and
  a property** (pierce / bonus-vs-type); armour is **soak** (heavy, subtracts
  from damage) *or* **+Defence** (light gear + shields, harder to hit), plus
  load; a new **accessory** slot (cloak/ring/token) carries non-combat pluses
  (+attribute, +stealth, Path synergy, ability charges). Items are generated as a
  **base item + affixes** in rarity bands — **Plain** (base), **Fine** (1 affix),
  **Rare** (prefix + suffix) — alongside hand-authored named **Uniques**.
  *Rejected:* an identification minigame (hides stats, against the see-it goal);
  combat-only stats (loot then can't touch the varied "pluses to different
  things" we want).

## Consequences

- This is a broad rewrite, to be **phased** (see `notes/system-redesign-plan.md`),
  not one change: `dice.py` (d20 core), `fighter.py` (attack/damage/soak/crit,
  Bleed), `hero.py`/`tor.py` (attributes, Paths/perks, XP/level curve, drop
  Hope/Shadow/Valour/Wisdom/skills/profs), `equippable.py`/`equipment_types.py`
  (soak vs Defence split, accessory slot, affixes), `content.py` (rebuild the
  hero, foes' attack/damage, named + affixable items), `input_handlers.py`
  (Character/Advancement screens → a Path/perk UI; the dice-tray shows a d20 line
  not Feat+Success), and the test-suite.
- **CONTEXT.md** is re-glossed: the "The One Ring dice / Test outcomes /
  Conditions / Combat" sections are replaced by a d20 core, a Character section,
  and a new combat/equipment vocabulary; the Trade & loot "no glory" note is
  updated for kill-XP.
- ADR 0004 is **superseded in part** (its no-XP decision only); its economy
  remains authoritative.

## Status

Accepted; not yet implemented (build plan: `notes/system-redesign-plan.md`).
Supersedes the "routine foes grant no experience" decision of ADR 0004. Terms
recorded in `CONTEXT.md`.
